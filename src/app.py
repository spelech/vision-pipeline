import os
import io
import uuid
import base64
import logging
import asyncio
from typing import Optional, List, Dict
from fastapi import FastAPI, UploadFile, File, Form, Request, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from PIL import Image, ImageOps

from pipeline import VisionPipeline
from database import init_db, AsyncSessionLocal, Batch, Item
from services.homebox import HomeboxService
from services.mealie import MealieService
from services.enrichers import PriceBuddyService, ChangeDetectionService

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionAPI")

# --- Lifespan ---
async def lifespan(app: FastAPI):
    await init_db()
    yield

# --- Setup ---
app = FastAPI(lifespan=lifespan)
core_pipeline = VisionPipeline()

# Registry of available services
SERVICES = {
    "homebox": HomeboxService(),
    "mealie": MealieService(),
    "pricebuddy": PriceBuddyService(),
    "changedetection": ChangeDetectionService()
}

# Ensure directories exist
os.makedirs("templates", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)

# Mount uploads for serving review images
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

# DB Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# --- Core Endpoints ---

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/locations")
async def get_locations():
    """Proxy for Homebox locations."""
    try:
        headers = SERVICES["homebox"]._get_headers()
        if not headers: return {"success": False, "error": "No API Key"}
        import requests
        resp = requests.get(f"{SERVICES['homebox'].api_url}/locations", headers=headers, timeout=5)
        return {"success": True, "locations": resp.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Single Identity ---

@app.post("/identify")
async def identify(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None),
    rotation: int = Form(0),
    mirror: bool = Form(False)
):
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        if rotation != 0:
            img = img.rotate(-rotation, expand=True)
        if mirror:
            img = ImageOps.mirror(img)
            
        results = core_pipeline.run_pipeline(img, text)
        
        # Service-specific pre-enrichment (duplicates, etc.)
        enrichment_tasks = [s.get_pre_enrichment(results['llm_output']) for s in SERVICES.values()]
        enrichments = await asyncio.gather(*enrichment_tasks)
        results["service_enrichments"] = {list(SERVICES.keys())[i]: enrichments[i] for i in range(len(enrichments))}

        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        b64_img = base64.b64encode(buf.getvalue()).decode()
        
        return {
            "success": True,
            "results": results,
            "ai_preview": f"data:image/jpeg;base64,{b64_img}"
        }
    except Exception as e:
        logger.error(f"Identification failed: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

# --- Execution Endpoints ---

@app.post("/execute")
async def execute_services(data: Dict):
    """
    Trigger multiple services concurrently for a given item or data object.
    Payload: {"item_id": int, "service_names": ["homebox", "mealie"], "overrides": {}}
    """
    item_id = data.get("item_id")
    service_names = data.get("service_names", [])
    overrides = data.get("overrides", {})

    final_data = overrides
    image_path = None

    if item_id:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Item).where(Item.id == item_id))
            item = res.scalar_one_or_none()
            if item:
                image_path = item.image_path
                if not final_data:
                    final_data = item.user_overrides or item.ai_output.get("llm_output", {})

    if not final_data:
        return {"success": False, "error": "No data to process"}

    # Filter requested services
    active_services = [SERVICES[name] for name in service_names if name in SERVICES]
    
    # Run concurrently
    tasks = [s.execute(final_data, image_path=image_path) for s in active_services]
    results = await asyncio.gather(*tasks)

    # Map back to names
    response = {service_names[i]: results[i] for i in range(len(results))}
    
    if item_id:
        async with AsyncSessionLocal() as db:
            await db.execute(update(Item).where(Item.id == item_id).values(status="uploaded"))
            await db.commit()

    return {"success": True, "results": response}

# --- Batch Processing ---

@app.post("/batch-upload")
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    new_batch = Batch(description=text)
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)
    
    for file in files:
        if not file.content_type.startswith("image/"): continue
        file_ext = os.path.splitext(file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = f"data/uploads/{file_name}"
        content = await file.read()
        with open(file_path, "wb") as f: f.write(content)
            
        new_item = Item(batch_id=new_batch.id, image_path=file_name, status="processing")
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        background_tasks.add_task(process_item_task, new_item.id)
        
    return {"success": True, "batch_id": new_batch.id}

async def process_item_task(item_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Item).where(Item.id == item_id))
        item = result.scalar_one_or_none()
        if not item: return

        res = await db.execute(select(Batch).where(Batch.id == item.batch_id))
        batch = res.scalar_one_or_none()
        batch_text = batch.description if batch else None

        try:
            full_path = f"data/uploads/{item.image_path}"
            img = Image.open(full_path)
            results = core_pipeline.run_pipeline(img, text_description=batch_text)
            
            # Service-specific pre-enrichment
            enrichment_tasks = [s.get_pre_enrichment(results['llm_output']) for s in SERVICES.values()]
            enrichments = await asyncio.gather(*enrichment_tasks)
            results["service_enrichments"] = {list(SERVICES.keys())[i]: enrichments[i] for i in range(len(enrichments))}

            item.ai_output = results
            item.product_type = "food" if results.get("llm_output", {}).get("is_food") else "product"
            item.status = "pending"
        except Exception as e:
            logger.error(f"Processing failed for item {item_id}: {e}")
            item.status = "error"
            item.error = str(e)
        await db.commit()

@app.get("/queue")
async def get_queue(status: str = "pending", db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.status == status).order_by(Item.created_at.desc()))
    items = result.scalars().all()
    return {"items": items}

@app.post("/items/{item_id}/update")
async def update_item_data(item_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    query = update(Item).where(Item.id == item_id).values(**data)
    await db.execute(query)
    await db.commit()
    return {"success": True}

@app.post("/items/{item_id}/rerun")
async def rerun_item(item_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    await db.execute(update(Item).where(Item.id == item_id).values(status="processing"))
    await db.commit()
    background_tasks.add_task(process_item_task, item_id)
    return {"success": True}

@app.delete("/items/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item:
        if os.path.exists(f"data/uploads/{item.image_path}"): os.remove(f"data/uploads/{item.image_path}")
        await db.delete(item)
        await db.commit()
    return {"success": True}

# --- Legacy Compatibility ---
# These will be deprecated in favor of /execute but kept for now.

@app.post("/bulk-approve")
async def bulk_approve(data: dict, db: AsyncSession = Depends(get_db)):
    item_ids = data.get("item_ids", [])
    # Defaulting to Homebox for product, Mealie for food in legacy mode
    results = {"success": [], "failed": []}
    for iid in item_ids:
        # Simple redirect to execute logic for each
        res = await db.execute(select(Item).where(Item.id == iid))
        item = res.scalar_one_or_none()
        if not item: continue
        svc = "mealie" if item.product_type == "food" else "homebox"
        exec_res = await execute_services({"item_id": iid, "service_names": [svc]})
        if exec_res.get("success"): results["success"].append(iid)
        else: results["failed"].append({"id": iid, "error": exec_res.get("error")})
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
