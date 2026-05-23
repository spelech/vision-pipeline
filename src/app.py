import os
import io
import uuid
import base64
import logging
import asyncio
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Request, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from PIL import Image, ImageOps

from pipeline import VisionPipeline
from database import init_db, AsyncSessionLocal, Batch, Item

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionAPI")

# --- Lifespan ---
async def lifespan(app: FastAPI):
    await init_db()
    yield

# --- Setup ---
app = FastAPI(lifespan=lifespan)
pipeline = VisionPipeline()

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
    try:
        locations = pipeline.homebox.list_locations()
        return {"success": True, "locations": locations}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- Single Identity (Existing) ---

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
            
        results = pipeline.run_pipeline(img, text)
        
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

# --- Batch Processing Endpoints ---

@app.post("/batch-upload")
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    text: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # 1. Create a new batch
    new_batch = Batch(description=text)
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)
    
    # 2. Save files and create items
    for file in files:
        if not file.content_type.startswith("image/"):
            continue
            
        file_ext = os.path.splitext(file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = f"data/uploads/{file_name}"
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        new_item = Item(
            batch_id=new_batch.id,
            image_path=file_name,
            status="processing"
        )
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        
        # 3. Queue for processing
        background_tasks.add_task(process_item_task, new_item.id)
        
    return {"success": True, "batch_id": new_batch.id}

async def process_item_task(item_id: int):
    # This task runs in the background to avoid blocking the upload response
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Item).where(Item.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            return

        # Get batch description
        res = await db.execute(select(Batch).where(Batch.id == item.batch_id))
        batch = res.scalar_one_or_none()
        batch_text = batch.description if batch else None

        try:
            full_path = f"data/uploads/{item.image_path}"
            img = Image.open(full_path)
            
            # Run pipeline
            results = pipeline.run_pipeline(img, text_description=batch_text)
            
            # Update item
            item.ai_output = results
            item.product_type = "food" if results.get("llm_output", {}).get("is_food") else "product"
            item.status = "pending"
            item.error = None
        except Exception as e:
            logger.error(f"Background processing failed for item {item_id}: {e}")
            item.status = "error"
            item.error = str(e)
            
        await db.commit()

@app.get("/queue")
async def get_queue(status: str = "pending", db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.status == status).order_by(Item.created_at.desc()))
    items = result.scalars().all()
    return {"items": items}

@app.post("/items/{item_id}/update")
async def update_item_status(item_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    # Used for edit, accept, discard
    # data can contain status, user_overrides
    query = update(Item).where(Item.id == item_id).values(**data)
    await db.execute(query)
    await db.commit()
    return {"success": True}

@app.post("/items/{item_id}/rerun")
async def rerun_item(item_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    query = update(Item).where(Item.id == item_id).values(status="processing")
    await db.execute(query)
    await db.commit()
    background_tasks.add_task(process_item_task, item_id)
    return {"success": True}

@app.delete("/items/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    # Discard item
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item:
        if os.path.exists(f"data/uploads/{item.image_path}"):
            os.remove(f"data/uploads/{item.image_path}")
        await db.delete(item)
        await db.commit()
    return {"success": True}

@app.post("/bulk-approve")
async def bulk_approve(data: dict, db: AsyncSession = Depends(get_db)):
    item_ids = data.get("item_ids", [])
    results = {"success": [], "failed": []}
    
    for item_id in item_ids:
        res = await db.execute(select(Item).where(Item.id == item_id))
        item = res.scalar_one_or_none()
        if not item or not item.ai_output:
            results["failed"].append({"id": item_id, "error": "Item not found or not processed"})
            continue
            
        # Determine data (prefer user overrides)
        final_data = item.user_overrides if item.user_overrides else item.ai_output.get("llm_output", {})
        
        try:
            if item.product_type == "food":
                # Push to Mealie Food
                success = pipeline.mealie.create_food(final_data)
            else:
                # Push to Homebox
                location_id = None
                if final_data.get('location'):
                    location_id = pipeline.homebox.find_or_create_location(final_data['location'])
                
                success = pipeline.homebox.create_item(
                    final_data.get('product_name') or final_data.get('name'),
                    final_data.get('description', ''),
                    location_id=location_id,
                    quantity=final_data.get('quantity', 1),
                    unit=final_data.get('unit'),
                    msrp=final_data.get('msrp'),
                    product_url=final_data.get('product_url'),
                    manufacturer=final_data.get('manufacturer') or final_data.get('brand'),
                    model_number=final_data.get('model_number'),
                    serial_number=final_data.get('serial_number'),
                    purchase_price=final_data.get('purchase_price', 0),
                    notes=final_data.get('notes'),
                    technical_details=final_data.get('technical_details')
                )
            
            if success:
                item.status = "uploaded"
                results["success"].append(item_id)
            else:
                results["failed"].append({"id": item_id, "error": "Service rejected creation"})
        except Exception as e:
            results["failed"].append({"id": item_id, "error": str(e)})
            
    await db.commit()
    return results

# --- Service Interaction Endpoints (Already implemented) ---

@app.post("/add-to-homebox")
async def add_to_homebox(data: dict):
    try:
        location_id = None
        if data.get('location'):
            location_id = pipeline.homebox.find_or_create_location(data['location'])

        success = pipeline.homebox.create_item(
            data.get('product_name') or data.get('name'),
            data.get('description', ''),
            location_id=location_id,
            quantity=data.get('quantity', 1),
            unit=data.get('unit'),
            msrp=data.get('msrp'),
            product_url=data.get('product_url'),
            manufacturer=data.get('manufacturer') or data.get('brand'),
            model_number=data.get('model_number'),
            serial_number=data.get('serial_number'),
            purchase_price=data.get('purchase_price', 0),
            notes=data.get('notes'),
            technical_details=data.get('technical_details')
        )
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/add-food-to-mealie")
async def add_food_to_mealie(data: dict):
    try:
        food_id = data.get("id")
        if food_id:
            success = pipeline.mealie.update_food(food_id, data)
        else:
            success = pipeline.mealie.create_food(data)
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/add-to-mealie-shopping-list")
async def add_to_mealie_shopping_list(data: dict):
    try:
        success = pipeline.mealie.add_shopping_list_item(
            data['name'],
            data.get('quantity', 1),
            data.get('note')
        )
        return {"success": success}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
