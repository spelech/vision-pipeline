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
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from PIL import Image, ImageOps

from pipelines import get_pipeline, get_all_pipelines
from database import init_db, AsyncSessionLocal, Batch, Item, ServiceMapping
from services.homebox import HomeboxService
from services.mealie import MealieService
from services.enrichers import PriceBuddyService, ChangeDetectionService
from logger import session_logger

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionAPI")

# --- Lifespan ---
async def lifespan(app: FastAPI):
    await init_db()
    yield

# --- Setup ---
app = FastAPI(lifespan=lifespan)


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


@app.get("/pipelines")

def get_pipeline(pipeline_id: str):
    from pipelines import PIPELINE_REGISTRY, DefaultPipeline, ComposablePipeline
    
    # Check registry first
    if pipeline_id in PIPELINE_REGISTRY:
        return PIPELINE_REGISTRY[pipeline_id]()
        
    # Check for custom composable pipeline in config
    try:
        config_path = "config/user_config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                for cp in config.get("custom_pipelines", []):
                    if cp["id"] == pipeline_id:
                        # Instantiate a ComposablePipeline and set its name/schema?
                        # Actually, we can just return a custom instance
                        p = ComposablePipeline()
                        return p
    except:
        pass
        
    return DefaultPipeline()

@app.get("/pipelines")
async def list_pipelines():
    from pipelines import get_all_pipelines
    base = get_all_pipelines()
    
    config_path = "config/user_config.json"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            custom = config.get("custom_pipelines", [])
            return {"success": True, "pipelines": base + custom}
            
    return {"success": True, "pipelines": base}


@app.get("/models")
async def list_models():
    # Placeholder for dynamic model fetching if needed
    return {"success": True, "models": [
        {"id": "qwen/qwen2.5-vl-72b-instruct", "name": "Qwen 2.5 VL 72B (OpenRouter)"},
        {"id": "anthropic/gpt-4o-mini", "name": "GPT-4o Mini (Placeholder)"},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet (Placeholder)"}
    ]}



@app.get("/config")
async def get_config():
    config_path = "config/user_config.json"
    if not os.path.exists(config_path):
        return {"success": False, "error": "Config not found"}
    with open(config_path, "r") as f:
        return json.load(f)

@app.post("/config")
async def update_config(data: Dict):
    config_path = "config/user_config.json"
    with open(config_path, "w") as f:
        json.dump(data, f, indent=4)
    return {"success": True}

@app.get("/search")
async def search_items(query: str, db: AsyncSession = Depends(get_db)):
    # Simple search for now, Postgres full-text would use plainto_tsquery
    # We'll search product_name and brand in user_overrides or ai_output
    # Using sqlalchemy ILIKE on the JSONB fields
    from sqlalchemy import or_
    stmt = select(Item).where(
        or_(
            Item.user_overrides['product_name'].astext.ilike(f'%{query}%'),
            Item.ai_output['llm_output']['product_name'].astext.ilike(f'%{query}%'),
            Item.user_overrides['brand'].astext.ilike(f'%{query}%'),
            Item.ai_output['llm_output']['brand'].astext.ilike(f'%{query}%')
        )
    ).order_by(Item.created_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    # Include mappings in results
    res = []
    for item in items:
        # Load mappings manually since we didn't use joinedload
        stmt_map = select(ServiceMapping).where(ServiceMapping.item_id == item.id)
        map_res = await db.execute(stmt_map)
        mappings = map_res.scalars().all()
        
        item_dict = {
            "id": item.id,
            "status": item.status,
            "image_path": item.image_path,
            "product_name": (item.user_overrides or item.ai_output.get("llm_output", {})).get("product_name"),
            "brand": (item.user_overrides or item.ai_output.get("llm_output", {})).get("brand"),
            "created_at": item.created_at,
            "mappings": [{"service": m.service_name, "external_id": m.external_id, "url": m.external_url} for m in mappings]
        }
        res.append(item_dict)
    return {"items": res}

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

@app.get("/logs/{session_id}")
async def get_session_logs(session_id: str):
    return {"logs": session_logger.get_logs(session_id)}

@app.post("/preview/{service_name}")
async def get_service_preview(service_name: str, data: Dict):
    """Return the formatted payload for a specific service."""
    if service_name not in SERVICES:
        return JSONResponse(status_code=404, content={"error": "Service not found"})
    
    payload = SERVICES[service_name].get_payload(data)
    return {"service": service_name, "payload": payload}

# --- Single Identity ---


@app.post("/identify")
async def identify(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None),
    rotation: int = Form(0),
    mirror: bool = Form(False),
    session_id: str = Form(None),
    pipeline_id: str = Form("default"),
    settings: str = Form("{}"),
    lasso_polygon: str = Form(None)
):
    import json
    try:
        pipeline_settings = json.loads(settings)
    except:
        pipeline_settings = {}
    
    try:
        lasso_points = json.loads(lasso_polygon) if lasso_polygon else None
    except:
        lasso_points = None
        
    core_pipeline = get_pipeline(pipeline_id)
    sid = session_id or str(uuid.uuid4())
    session_logger.start_session(sid)
    def log_it(msg): session_logger.log(sid, msg)

    try:
        content = await file.read()
        raw_filename = f"raw_{uuid.uuid4()}.jpg"
        masked_filename = f"masked_{uuid.uuid4()}.png"
        
        # Save raw image
        with open(f"data/uploads/{raw_filename}", "wb") as f:
            f.write(content)
            
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        # Note: Lasso is already applied on frontend, 'file' IS the masked image if lasso was used.
        # However, we'll store the 'raw' for future re-edits.
        
        # Run blocking pipeline
        results = await run_in_threadpool(core_pipeline.run, img, text, pipeline_settings, log_it)
        
        # Service-specific pre-enrichment
        log_it("🔌 Checking for existing entries in services...")
        enrichment_tasks = [s.get_pre_enrichment(results['llm_output']) for s in SERVICES.values()]
        enrichments = await asyncio.gather(*enrichment_tasks)
        results["service_enrichments"] = {list(SERVICES.keys())[i]: enrichments[i] for i in range(len(enrichments))}
        
        # Save to DB so it's searchable and manageable
        async with AsyncSessionLocal() as db:
            # Create a 'Single Capture' batch if none exists? Or just a default one.
            stmt = select(Batch).where(Batch.name == "Single Captures")
            res = await db.execute(stmt)
            batch = res.scalar_one_or_none()
            if not batch:
                batch = Batch(name="Single Captures", status="completed")
                db.add(batch)
                await db.commit()
                await db.refresh(batch)
            
            # Save masked image
            img.save(f"data/uploads/{masked_filename}")
            
            new_item = Item(
                batch_id=batch.id,
                image_path=masked_filename,
                raw_image_path=raw_filename,
                lasso_polygon=lasso_points,
                status="pending",
                ai_output=results,
                product_type="food" if results.get("llm_output", {}).get("is_food") else "product"
            )
            db.add(new_item)
            await db.commit()
            await db.refresh(new_item)
            item_id = new_item.id

        log_it("✨ UI updating with findings.")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64_img = base64.b64encode(buf.getvalue()).decode()
        
        session_logger.end_session(sid)
        return {
            "success": True,
            "session_id": sid,
            "item_id": item_id,
            "results": results,
            "ai_preview": f"data:image/png;base64,{b64_img}"
        }
    except Exception as e:
        log_it(f"❌ Fatal Error: {str(e)}")
        logger.error(f"Identification failed: {e}", exc_info=True)
        session_logger.end_session(sid)
        return JSONResponse(status_code=500, content={"success": False, "error": str(e), "session_id": sid})


# --- Execution Endpoints ---


@app.post("/execute")
async def execute_services(data: Dict):
    item_id = data.get("item_id")
    service_names = data.get("service_names", [])
    overrides = data.get("overrides", {})

    final_data = overrides
    image_path = None
    existing_mappings = {}

    async with AsyncSessionLocal() as db:
        if item_id:
            res = await db.execute(select(Item).where(Item.id == item_id))
            item = res.scalar_one_or_none()
            if item:
                image_path = item.image_path
                if not final_data:
                    final_data = item.user_overrides or item.ai_output.get("llm_output", {})
                    if "searxng_results" in item.ai_output:
                        final_data["searxng_results"] = item.ai_output["searxng_results"]
                
                # Fetch existing mappings for upsert
                map_res = await db.execute(select(ServiceMapping).where(ServiceMapping.item_id == item_id))
                for m in map_res.scalars().all():
                    existing_mappings[m.service_name] = m.external_id

    if not final_data:
        return {"success": False, "error": "No data to process"}

    results_map = {}
    for name in service_names:
        if name not in SERVICES: continue
        svc = SERVICES[name]
        ext_id = existing_mappings.get(name)
        
        # Execute (Create or Update)
        res = await svc.execute(final_data, image_path=image_path, external_id=ext_id)
        results_map[name] = res
        
        if res.get("success") and item_id:
            async with AsyncSessionLocal() as db:
                new_ext_id = str(res.get("item_id"))
                ext_url = res.get("url")
                
                # Update existing mapping or create new
                stmt = select(ServiceMapping).where(
                    ServiceMapping.item_id == item_id, 
                    ServiceMapping.service_name == name
                )
                m_res = await db.execute(stmt)
                mapping = m_res.scalar_one_or_none()
                
                if mapping:
                    mapping.external_id = new_ext_id
                    mapping.external_url = ext_url
                    mapping.last_sync_payload = final_data
                    mapping.synced_at = datetime.utcnow()
                else:
                    mapping = ServiceMapping(
                        item_id=item_id,
                        service_name=name,
                        external_id=new_ext_id,
                        external_url=ext_url,
                        last_sync_payload=final_data
                    )
                    db.add(mapping)
                
                await db.execute(update(Item).where(Item.id == item_id).values(status="uploaded"))
                await db.commit()

    return {"success": True, "results": results_map}


# --- Batch Processing ---

@app.post("/batch-upload")
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    text: Optional[str] = Form(None),
    pipeline_id: str = Form("default"),
    settings: str = Form("{}"),
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
        background_tasks.add_task(process_item_task, new_item.id, pipeline_id, settings)
        
    return {"success": True, "batch_id": new_batch.id}

async def process_item_task(item_id: int, pipeline_id: str = "default", settings_str: str = "{}"):
    import json
    try:
        settings = json.loads(settings_str)
    except:
        settings = {}
    core_pipeline = get_pipeline(pipeline_id)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Item).where(Item.id == item_id))
        item = result.scalar_one_or_none()
        if not item: return

        sid = f"batch-item-{item_id}"
        session_logger.start_session(sid)
        def log_it(msg): session_logger.log(sid, msg)

        res = await db.execute(select(Batch).where(Batch.id == item.batch_id))
        batch = res.scalar_one_or_none()
        batch_text = batch.description if batch else None

        try:
            full_path = f"data/uploads/{item.image_path}"
            img = Image.open(full_path)
            results = await run_in_threadpool(core_pipeline.run, img, batch_text, settings, log_it)
            
            # Service-specific pre-enrichment
            enrichment_tasks = [s.get_pre_enrichment(results['llm_output']) for s in SERVICES.values()]
            enrichments = await asyncio.gather(*enrichment_tasks)
            results["service_enrichments"] = {list(SERVICES.keys())[i]: enrichments[i] for i in range(len(enrichments))}

            item.ai_output = results
            item.product_type = "food" if results.get("llm_output", {}).get("is_food") else "product"
            item.status = "pending"
        except Exception as e:
            log_it(f"❌ Error: {str(e)}")
            logger.error(f"Processing failed for item {item_id}: {e}")
            item.status = "error"
            item.error = str(e)
        
        session_logger.end_session(sid)
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
    background_tasks.add_task(process_item_task, item_id, "default", "{}")
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

@app.post("/bulk-approve")
async def bulk_approve(data: dict, db: AsyncSession = Depends(get_db)):
    item_ids = data.get("item_ids", [])
    results = {"success": [], "failed": []}
    for iid in item_ids:
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
