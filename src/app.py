import json
import os
import io
import uuid
import base64
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, Depends, APIRouter, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from PIL import Image, ImageOps

from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables FIRST before other imports
# Search for .env in current or parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from database import init_db, AsyncSessionLocal, Batch, Item, ServiceMapping, ConfigSecret
from schemas import (
    PipelineListResponse, ModelListResponse, ConfigResponse, ConfigUpdateRequest,
    SearchResponse, HealthResponse, LocationsResponse, SessionLogsResponse,
    ServicePreviewResponse
)
from services.homebox import HomeboxService
from services.mealie import MealieService
from services.enrichers import PriceBuddyService, ChangeDetectionService
from logger import session_logger

# Get or create encryption key
MASTER_KEY = os.getenv("ENCRYPTION_KEY")
if not MASTER_KEY:
    MASTER_KEY = Fernet.generate_key().decode()
    env_path = ".env" if os.path.exists(".env") else "../.env"
    with open(env_path, "a") as f:
        f.write(f"\nENCRYPTION_KEY={MASTER_KEY}\n")
    os.environ["ENCRYPTION_KEY"] = MASTER_KEY

cipher = Fernet(MASTER_KEY.encode())

def encrypt_secret(val: str) -> str:
    return cipher.encrypt(val.encode()).decode()

def decrypt_secret(val: str) -> str:
    return cipher.decrypt(val.encode()).decode()


def normalize_prompt_templates(value: Any) -> List[Dict[str, str]]:
    if isinstance(value, list):
        normalized = []
        for template in value:
            if isinstance(template, dict):
                normalized.append({
                    "id": str(template.get("id", uuid.uuid4())),
                    "name": str(template.get("name", "Untitled Template")),
                    "prompt": str(template.get("prompt", ""))
                })
        return normalized

    if isinstance(value, dict):
        normalized = []
        for key, prompt in value.items():
            if isinstance(prompt, dict):
                normalized.append({
                    "id": str(prompt.get("id", key)),
                    "name": str(prompt.get("name", key.replace("_", " ").title())),
                    "prompt": str(prompt.get("prompt", ""))
                })
            else:
                normalized.append({
                    "id": str(key),
                    "name": key.replace("_", " ").title(),
                    "prompt": str(prompt)
                })
        return normalized

    return []


def merge_unique_str_lists(*values: Any) -> List[str]:
    merged: List[str] = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item and item not in merged:
                    merged.append(item)
    return merged


def extract_model_favorites(config_data: Dict[str, Any]) -> List[str]:
    nested_registry = []
    model_registry = config_data.get("model_registry")
    if isinstance(model_registry, list):
        nested_registry = [
            model.get("id") for model in model_registry
            if isinstance(model, dict) and isinstance(model.get("id"), str)
        ]

    return merge_unique_str_lists(
        config_data.get("model_favorites"),
        config_data.get("favorite_models"),
        config_data.get("configured_models"),
        config_data.get("models"),
        nested_registry,
    )


def load_json_file(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r") as f:
            loaded = json.load(f)
            return loaded if isinstance(loaded, dict) else {}
    except Exception as exc:
        logger.warning("Failed to read config file %s: %s", path, exc)
        return {}


def load_merged_user_config() -> Dict[str, Any]:
    legacy_path = "config/user_settings.json"
    current_path = "config/user_config.json"

    legacy = load_json_file(legacy_path)
    current = load_json_file(current_path)

    merged = {**legacy, **current}

    merged["model_favorites"] = merge_unique_str_lists(
        extract_model_favorites(legacy),
        extract_model_favorites(current),
    )
    merged["starred_models"] = merge_unique_str_lists(
        legacy.get("starred_models"),
        current.get("starred_models"),
    )
    merged["prompt_templates"] = normalize_prompt_templates(
        (legacy.get("prompt_templates") or legacy.get("prompts") or legacy.get("templates"))
    ) + normalize_prompt_templates(
        (current.get("prompt_templates") or current.get("prompts") or current.get("templates"))
    )

    if merged["prompt_templates"]:
        deduped: Dict[str, Dict[str, str]] = {}
        for template in merged["prompt_templates"]:
            deduped[str(template.get("id", uuid.uuid4()))] = {
                "id": str(template.get("id", uuid.uuid4())),
                "name": str(template.get("name", "Untitled Template")),
                "prompt": str(template.get("prompt", "")),
            }
        merged["prompt_templates"] = list(deduped.values())

    if not merged.get("image_optimization") and isinstance(legacy.get("image_optimization"), dict):
        merged["image_optimization"] = legacy.get("image_optimization")

    merged["custom_pipelines"] = (current.get("custom_pipelines") if isinstance(current.get("custom_pipelines"), list) else legacy.get("custom_pipelines")) or []

    return merged


CONFIG_SECRET_KEYS = [
    "OPENROUTER_API_KEY",
    "SEARXNG_URL",
    "HOMEBOX_URL",
    "MEALIE_URL",
    "PRICEBUDDY_URL",
    "CHANGEDETECTION_URL",
    "HOMEBOX_USERNAME",
    "HOMEBOX_PASSWORD",
    "MEALIE_API_TOKEN",
    "PRICEBUDDY_API_KEY",
    "CHANGEDETECTION_API_KEY"
]


def get_secret_value(key: str) -> str:
    if key == "HOMEBOX_USERNAME":
        return os.getenv("HOMEBOX_USERNAME") or os.getenv("HOMEBOX_EMAIL") or ""
    return os.getenv(key) or ""


def set_secret_value(key: str, val: str) -> None:
    if key == "HOMEBOX_USERNAME":
        os.environ["HOMEBOX_USERNAME"] = val
        # Keep compatibility with existing Homebox email-based setups.
        os.environ["HOMEBOX_EMAIL"] = val
    else:
        os.environ[key] = val

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionAPI")

# --- Lifespan ---
async def lifespan(app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(ConfigSecret))
        secrets = res.scalars().all()
        for secret in secrets:
            try:
                os.environ[secret.key] = decrypt_secret(secret.encrypted_value)
                logger.info(f"Loaded encrypted secret: {secret.key}")
            except Exception as e:
                logger.error(f"Failed to decrypt secret {secret.key}: {e}")
    yield

# --- Setup ---
app = FastAPI(lifespan=lifespan, title="Vision Pipeline API", version="3.3.0")
api_router = APIRouter(prefix="/api")

# Registry of available services
SERVICES = {
    "homebox": HomeboxService(),
    "mealie": MealieService(),
    "pricebuddy": PriceBuddyService(),
    "changedetection": ChangeDetectionService()
}

# Ensure directories exist
os.makedirs("data/uploads", exist_ok=True)

# Mount uploads for serving review images
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# DB Dependency
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# --- Pipeline Helpers ---


def get_pipeline(pipeline_id: str):
    from pipelines import PIPELINE_REGISTRY, DefaultPipeline, ComposablePipeline
    import json
    
    # Check for custom composable pipeline in config first
    try:
        config_path = "config/user_config.json"
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                for cp in config.get("custom_pipelines", []):
                    if cp["id"] == pipeline_id:
                        # Return a ComposablePipeline
                        return ComposablePipeline()
    except:
        pass

    # Check registry
    if pipeline_id in PIPELINE_REGISTRY:
        return PIPELINE_REGISTRY[pipeline_id]()
        
    return DefaultPipeline()


# --- Endpoints ---

@api_router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines() -> PipelineListResponse:
    from pipelines import get_all_pipelines
    try:
        base = get_all_pipelines()
        config_path = "config/user_config.json"
        custom = []
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                custom = config.get("custom_pipelines", [])
        
        return PipelineListResponse(success=True, pipelines=base + custom)
    except Exception as e:
        logger.error(f"Error listing pipelines: {e}")
        return PipelineListResponse(success=False, error=str(e), pipelines=[])

@api_router.get("/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    from schemas import ModelInfo
    return ModelListResponse(success=True, models=[
        ModelInfo(id="qwen/qwen2.5-vl-72b-instruct", name="Qwen 2.5 VL 72B (OpenRouter)"),
        ModelInfo(id="google/gemini-2.0-flash-001", name="Gemini 2.0 Flash (OpenRouter)"),
        ModelInfo(id="anthropic/claude-3.5-sonnet", name="Claude 3.5 Sonnet (OpenRouter)")
    ])

@api_router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    data = load_merged_user_config()
    data["prompt_templates"] = normalize_prompt_templates(data.get("prompt_templates"))

    # Mask secrets - return only presence status
    secrets_status = {}
    for key in CONFIG_SECRET_KEYS:
        val = get_secret_value(key)
        if val:
            if "URL" in key:
                secrets_status[key] = val
            else:
                secrets_status[key] = "********"
        else:
            secrets_status[key] = ""

    return ConfigResponse(**data, secrets_status=secrets_status)

@api_router.post("/config")
async def update_config(data: ConfigUpdateRequest, db: AsyncSession = Depends(get_db)):
    # Separate secrets from general config
    keys_to_persist = ["prompt_templates", "model_favorites", "starred_models", "image_optimization", "custom_pipelines"]
    data_dict = data.model_dump(exclude_unset=True)
    if "prompt_templates" in data_dict:
        data_dict["prompt_templates"] = normalize_prompt_templates(data_dict.get("prompt_templates"))
    current_config_path = "config/user_config.json"
    existing_config = load_json_file(current_config_path)
    config_to_save = {**existing_config, **{k: data_dict[k] for k in keys_to_persist if k in data_dict}}

    for key in CONFIG_SECRET_KEYS:
        val = getattr(data, key, None)
        if val and val != "********":
            set_secret_value(key, val)
            encrypted = encrypt_secret(val)
            
            # Upsert into database
            res = await db.execute(select(ConfigSecret).where(ConfigSecret.key == key))
            secret_obj = res.scalar_one_or_none()
            if secret_obj:
                secret_obj.encrypted_value = encrypted # type: ignore
            else:
                db.add(ConfigSecret(key=key, encrypted_value=encrypted))

    # Backward compatibility for older payloads.
    legacy_homebox_email = getattr(data, "HOMEBOX_EMAIL", None)
    if legacy_homebox_email and legacy_homebox_email != "********":
        set_secret_value("HOMEBOX_USERNAME", legacy_homebox_email)
        encrypted = encrypt_secret(legacy_homebox_email)
        for legacy_key in ["HOMEBOX_USERNAME", "HOMEBOX_EMAIL"]:
            res = await db.execute(select(ConfigSecret).where(ConfigSecret.key == legacy_key))
            secret_obj = res.scalar_one_or_none()
            if secret_obj:
                secret_obj.encrypted_value = encrypted # type: ignore
            else:
                db.add(ConfigSecret(key=legacy_key, encrypted_value=encrypted))
    await db.commit()

    config_path = "config/user_config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config_to_save, f, indent=4)

    return {"success": True}

@api_router.get("/search", response_model=SearchResponse)
async def search_items(query: str, db: AsyncSession = Depends(get_db)) -> SearchResponse:
    from sqlalchemy import or_
    from schemas import ItemSearchInfo, ServiceMappingInfo
    # Simple JSON search for product name and brand
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
    
    res = []
    for item in items:
        stmt_map = select(ServiceMapping).where(ServiceMapping.item_id == item.id)
        map_res = await db.execute(stmt_map)
        mappings = map_res.scalars().all()

        user_overrides: Dict[str, Any] = item.user_overrides if isinstance(item.user_overrides, dict) else {}
        ai_output: Dict[str, Any] = item.ai_output if isinstance(item.ai_output, dict) else {}
        llm_output = ai_output.get("llm_output") if isinstance(ai_output.get("llm_output"), dict) else {}
        merged_data = user_overrides or llm_output
        
        item_data = ItemSearchInfo(
            id=str(item.id), # type: ignore
            status=item.status, # type: ignore
            image_path=item.image_path, # type: ignore
            raw_image_path=item.raw_image_path, # type: ignore
            product_type=item.product_type, # type: ignore
            ai_output=ai_output,
            user_overrides=user_overrides,
            product_name=merged_data.get("product_name") if isinstance(merged_data, dict) else None,
            brand=merged_data.get("brand") if isinstance(merged_data, dict) else None,
            created_at=item.created_at, # type: ignore
            mappings=[ServiceMappingInfo(service=m.service_name, external_id=m.external_id, url=m.external_url)  # type: ignore
                      for m in mappings]
        )
        res.append(item_data)
    return SearchResponse(items=res)

@api_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@api_router.get("/locations", response_model=LocationsResponse)
async def get_locations() -> LocationsResponse:
    try:
        homebox = SERVICES["homebox"]
        # Type narrowing for mypy
        if not hasattr(homebox, "_get_headers") or not hasattr(homebox, "api_url"):
            return LocationsResponse(success=False, error="Homebox service misconfigured")
            
        headers = homebox._get_headers() # type: ignore
        if not headers: return LocationsResponse(success=False, error="No API Key")
        import requests
        resp = requests.get(f"{homebox.api_url}/locations", headers=headers, timeout=5) # type: ignore
        return LocationsResponse(success=True, locations=resp.json())
    except Exception as e:
        return LocationsResponse(success=False, error=str(e))

@api_router.get("/logs/{session_id}", response_model=SessionLogsResponse)
async def get_session_logs(session_id: str) -> SessionLogsResponse:
    logs = session_logger.get_logs(session_id)
    # Convert list of strings to list of dicts for Pydantic
    return SessionLogsResponse(logs=[{"message": log} for log in logs])

@api_router.get("/preview/{service_name}", response_model=ServicePreviewResponse)
async def get_service_preview(service_name: str, item_id: int) -> ServicePreviewResponse:
    if service_name not in SERVICES:
        return JSONResponse(status_code=404, content={"error": "Service not found"}) # type: ignore
    
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Item).where(Item.id == item_id))
        item = res.scalar_one_or_none()
        if not item:
            return JSONResponse(status_code=404, content={"error": "Item not found"}) # type: ignore
        
        data = item.user_overrides or item.ai_output.get("llm_output", {})
    
    payload = SERVICES[service_name].get_payload(data)
    return ServicePreviewResponse(service=service_name, payload=payload)

# --- Core Processing ---

@api_router.post("/identify")
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
        
        with open(f"data/uploads/{raw_filename}", "wb") as f:
            f.write(content)
            
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img) # type: ignore
        
        results = await run_in_threadpool(core_pipeline.run, img, text, pipeline_settings, log_it) # type: ignore
        
        log_it("🔌 Checking for existing entries in services...")
        enrichment_tasks = [s.get_pre_enrichment(results['llm_output']) for s in SERVICES.values()]
        enrichments = await asyncio.gather(*enrichment_tasks)
        results["service_enrichments"] = {list(SERVICES.keys())[i]: enrichments[i] for i in range(len(enrichments))}
        
        async with AsyncSessionLocal() as db:
            stmt = select(Batch).where(Batch.name == "Single Captures")
            res = await db.execute(stmt)
            batch = res.scalar_one_or_none()
            if not batch:
                batch = Batch(name="Single Captures", status="completed")
                db.add(batch)
                await db.commit()
                await db.refresh(batch)
            
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

@api_router.post("/execute")
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
        
        res = await svc.execute(final_data, image_path=image_path, external_id=ext_id)
        results_map[name] = res
        
        if res.get("success") and item_id:
            async with AsyncSessionLocal() as db:
                new_ext_id = str(res.get("item_id"))
                ext_url = res.get("url")
                
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

@api_router.post("/batch-upload")
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
        if file.content_type and not file.content_type.startswith("image/"): continue
        file_ext = os.path.splitext(file.filename or "")[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = f"data/uploads/{file_name}"
        content = await file.read()
        with open(file_path, "wb") as f: f.write(content)
            
        new_item = Item(batch_id=new_batch.id, image_path=file_name, status="processing")
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        background_tasks.add_task(process_item_task, int(new_item.id), pipeline_id, settings) # type: ignore
        
    return {"success": True, "batch_id": new_batch.id}

async def process_item_task(item_id: int, pipeline_id: str = "default", settings_str: str = "{}"):
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

@api_router.get("/queue")
async def get_queue(status: str = "pending", db: AsyncSession = Depends(get_db)):
    stmt = select(Item)
    if status != "all":
        stmt = stmt.where(Item.status == status)
    result = await db.execute(stmt.order_by(Item.created_at.desc()))
    items = result.scalars().all()
    return {"items": items}

@api_router.get("/items/{item_id}")
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Item).where(Item.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@api_router.post("/items/{item_id}/update")
async def update_item_data(item_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    query = update(Item).where(Item.id == item_id).values(**data)
    await db.execute(query)
    await db.commit()
    return {"success": True}

@api_router.post("/items/{item_id}/rerun")
async def rerun_item(item_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    await db.execute(update(Item).where(Item.id == item_id).values(status="processing"))
    await db.commit()
    background_tasks.add_task(process_item_task, item_id, "default", "{}")
    return {"success": True}

@api_router.delete("/items/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item:
        if os.path.exists(f"data/uploads/{item.image_path}"): os.remove(f"data/uploads/{item.image_path}")
        if item.raw_image_path and os.path.exists(f"data/uploads/{item.raw_image_path}"): 
            os.remove(f"data/uploads/{item.raw_image_path}")
        await db.delete(item)
        await db.commit()
    return {"success": True}

@api_router.post("/bulk-approve")
async def bulk_approve(data: dict, db: AsyncSession = Depends(get_db)):
    item_ids = data.get("item_ids", [])
    results: Dict[str, Any] = {"success": [], "failed": []}
    for iid in item_ids:
        res = await db.execute(select(Item).where(Item.id == iid))
        item = res.scalar_one_or_none()
        if not item: continue
        svc = "mealie" if item.product_type == "food" else "homebox"
        exec_res = await execute_services({"item_id": iid, "service_names": [svc]})
        if exec_res.get("success"): results["success"].append(iid)
        else: results["failed"].append({"id": iid, "error": exec_res.get("error")})
    return results

app.include_router(api_router)

# Serve built frontend if available
UI_DIR = os.path.join(os.path.dirname(__file__), "..", "web", "dist")

@app.exception_handler(StarletteHTTPException)
async def spa_fallback(request, exc):
    if exc.status_code == 404 and os.path.exists(os.path.join(UI_DIR, "index.html")):
        return FileResponse(os.path.join(UI_DIR, "index.html"))
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

if os.path.exists(UI_DIR):
    app.mount("/", StaticFiles(directory=UI_DIR, html=True), name="ui")
else:
    @app.get("/")
    async def root():
        return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)

