import json
import os
import io
import uuid
import base64
import logging
import asyncio
import importlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, cast
import requests
from pydantic import BaseModel
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    Depends,
    APIRouter,
    HTTPException,
)
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from sqlalchemy.exc import SQLAlchemyError
from PIL import Image, ImageOps

from cryptography.fernet import Fernet
from dotenv import load_dotenv

# pylint: disable=too-many-lines

# Load environment variables FIRST before other imports
# Search for .env in current or parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# These imports rely on environment variables being loaded above.
from database import (  # pylint: disable=wrong-import-position
    init_db,
    async_session_local as AsyncSessionLocal,
    Batch,
    Item,
    ServiceMapping,
    ConfigSecret,
    ModelCatalog,
    PipelineDefinition,
)
from schemas import (  # pylint: disable=wrong-import-position
    PipelineListResponse,
    ModelListResponse,
    ModelInfo,
    ConfigResponse,
    ConfigUpdateRequest,
    ItemSearchInfo,
    ServiceMappingInfo,
    SearchResponse,
    HealthResponse,
    LocationsResponse,
    SessionLogsResponse,
    ServicePreviewResponse,
    ServiceOutputGenerateRequest,
    ServiceOutputGenerateResponse,
)
from services.homebox import HomeboxService  # pylint: disable=wrong-import-position
from services.mealie import MealieService  # pylint: disable=wrong-import-position
from services.enrichers import PriceBuddyService, ChangeDetectionService  # pylint: disable=wrong-import-position
from logger import session_logger  # pylint: disable=wrong-import-position
from app_helpers import (  # pylint: disable=wrong-import-position,unused-import
    normalize_prompt_templates,
    merge_unique_str_lists,
    get_pipeline,
    _service_target_for_pipeline_id,
    infer_model_provider,
    normalize_app_setting,
    upsert_app_setting,
    get_app_settings,
    ensure_model_catalog,
    ensure_app_settings_seed,
    get_runtime_service_prompt_configs,
    ensure_pipeline_catalog,
    list_pipeline_definitions,
    persist_custom_pipelines,
    normalize_service_prompts,
    merge_service_prompt_configs,
    get_service_prompt_config,
    extract_search_candidates,
    build_service_feedback_context,
    should_run_service_feedback_pass,
    apply_service_output_feedback_fallbacks,
    generate_service_output,
    get_item_base_data,
    get_service_specific_item_data,
    get_service_context_from_item,
    normalize_pipeline_schema,
    normalize_pipeline_settings,
    normalize_pipeline_list,
)


# Get or create encryption key
MASTER_KEY = os.getenv("ENCRYPTION_KEY")
if not MASTER_KEY:
    MASTER_KEY = Fernet.generate_key().decode()
    ENV_PATH = ".env" if os.path.exists(".env") else "../.env"
    with open(ENV_PATH, "a", encoding="utf-8") as f:
        f.write(f"\nENCRYPTION_KEY={MASTER_KEY}\n")
    os.environ["ENCRYPTION_KEY"] = MASTER_KEY

cipher = Fernet(MASTER_KEY.encode())


def encrypt_secret(val: str) -> str:
    return cipher.encrypt(val.encode()).decode()


def decrypt_secret(val: str) -> str:
    return cipher.decrypt(val.encode()).decode()

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
    return os.getenv(key) or ""


def set_secret_value(key: str, val: str) -> None:
    os.environ[key] = val


# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionAPI")

# --- Lifespan ---


async def lifespan(_app: FastAPI):
    await init_db()
    async with AsyncSessionLocal() as db:
        await ensure_pipeline_catalog(db)
        await ensure_model_catalog(db)
        await ensure_app_settings_seed(db)
        res = await db.execute(select(ConfigSecret))
        secrets = res.scalars().all()
        for secret in secrets:
            try:
                os.environ[secret.key] = decrypt_secret(secret.encrypted_value)
                logger.info("Loaded encrypted secret: %s", secret.key)
            except ValueError as e:  # Fernet InvalidToken extends ValueError
                logger.error("Failed to decrypt secret %s: %s", secret.key, e)
    yield

# --- Setup ---
app = FastAPI(
    lifespan=lifespan,
    title="Vision Pipeline API",
    version="3.4.0",
    redoc_url=None,
)
api_router = APIRouter(prefix="/api")

# Registry of available services
SERVICES = {
    "homebox": HomeboxService(),
    "mealie": MealieService(),
    "pricebuddy": PriceBuddyService(),
    "changedetection": ChangeDetectionService()
}

REVIEW_IMAGE_MAX_DIM = int(os.getenv("REVIEW_IMAGE_MAX_DIM", "1280"))
REVIEW_IMAGE_JPEG_QUALITY = int(os.getenv("REVIEW_IMAGE_JPEG_QUALITY", "72"))
WEB_DIST_DIR = Path(os.getenv("WEB_DIST_DIR", "/app/web_dist"))
WEB_INDEX_FILE = WEB_DIST_DIR / "index.html"

# Ensure directories exist
os.makedirs("data/uploads", exist_ok=True)

# Mount uploads for serving review images
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

# DB Dependency


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def encode_image_bytes_to_data_uri(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"


def decode_data_uri_to_bytes(data_uri: str) -> bytes:
    if not isinstance(data_uri, str) or "," not in data_uri:
        raise ValueError("Invalid data URI")
    encoded = data_uri.split(",", 1)[1]
    return base64.b64decode(encoded)


def build_review_image_data_uri(img: Image.Image) -> str:
    preview_img = img.copy()
    if preview_img.mode in ("RGBA", "P"):
        preview_img = preview_img.convert("RGB")
    preview_img.thumbnail((REVIEW_IMAGE_MAX_DIM, REVIEW_IMAGE_MAX_DIM))

    out = io.BytesIO()
    preview_img.save(
        out,
        format="JPEG",
        quality=REVIEW_IMAGE_JPEG_QUALITY,
        optimize=True,
    )
    return encode_image_bytes_to_data_uri(out.getvalue(), mime="image/jpeg")


def item_source_image_data_uri(item: Any) -> Optional[str]:
    raw_value = getattr(item, "raw_image_path", None)
    preview_value = getattr(item, "image_path", None)
    candidates = [raw_value, preview_value]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("data:image"):
            return candidate
    return None


class ScrapeRequest(BaseModel):
    url: str
    wait_time: int = 2000


@app.post("/internal/scrape", include_in_schema=False)
async def scrape_url(req: ScrapeRequest):
    try:
        # pylint: disable=import-outside-toplevel
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Playwright is unavailable: {e}",
        ) from e

    stealth = None
    try:
        stealth_module = importlib.import_module("playwright_stealth")
        stealth_cls = getattr(stealth_module, "Stealth", None)
        if stealth_cls is not None:
            stealth = stealth_cls()
    except ImportError:
        stealth = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        if stealth is not None:
            await stealth.apply_stealth_async(page)

        try:
            await page.goto(req.url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(req.wait_time / 1000.0)
            text_content = await page.evaluate("document.body.innerText")
            return {"success": True, "url": req.url, "text": text_content}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        finally:
            await browser.close()

# --- Endpoints ---

@api_router.get("/pipelines", response_model=PipelineListResponse)
async def list_pipelines(db: AsyncSession = Depends(get_db)) -> PipelineListResponse:
    try:
        await ensure_pipeline_catalog(db)
        all_pipelines = await list_pipeline_definitions(db, include_system=True)
        return PipelineListResponse(success=True, pipelines=all_pipelines)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing DB pipelines: %s", e)
        return PipelineListResponse(success=False, pipelines=[], error=str(e))


@api_router.put("/pipelines/{pipeline_id}")
async def upsert_pipeline(
    pipeline_id: str,
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    await ensure_pipeline_catalog(db)
    name = str(data.get("name") or pipeline_id)
    schema = normalize_pipeline_schema(data.get("schema") or {})
    is_system = bool(data.get("is_system", False))
    is_editable = bool(data.get("is_editable", True))
    service_target = data.get("service_target")
    service_target_value = (
        str(service_target)
        if isinstance(service_target, str)
        else _service_target_for_pipeline_id(pipeline_id)
    )

    result = await db.execute(
        select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id)
    )
    row = result.scalar_one_or_none()
    if row:
        row.name = name  # type: ignore
        row.schema = schema  # type: ignore
        row.is_system = is_system  # type: ignore
        row.is_editable = is_editable  # type: ignore
        row.service_target = service_target_value  # type: ignore
    else:
        db.add(
            PipelineDefinition(
                pipeline_id=pipeline_id,
                name=name,
                schema=schema,
                is_system=is_system,
                is_editable=is_editable,
                service_target=service_target_value,
            )
        )

    await db.commit()
    return {"success": True, "pipeline_id": pipeline_id}


@api_router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(
    pipeline_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        return {"success": False, "error": "Pipeline not found"}

    await db.delete(row)
    await db.commit()
    return {"success": True}


@api_router.get("/models", response_model=ModelListResponse)
async def list_models(db: AsyncSession = Depends(get_db)) -> ModelListResponse:
    try:
        await ensure_model_catalog(db)
        result = await db.execute(
            select(ModelCatalog)
            .where(ModelCatalog.is_active.is_(True))
            .order_by(ModelCatalog.is_system.desc(), ModelCatalog.model_id.asc())
        )
        rows = result.scalars().all()
        models = [
            ModelInfo(
                id=str(row.model_id),
                name=str(row.name),
                provider=str(row.provider),
                is_system=bool(row.is_system),
            )
            for row in rows
        ]
        return ModelListResponse(success=True, models=models)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing model catalog: %s", e)
        return ModelListResponse(success=False, models=[])


@api_router.get("/config", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)) -> ConfigResponse:
    await ensure_app_settings_seed(db)
    settings = await get_app_settings(db)
    data: Dict[str, Any] = {
        "prompt_templates": normalize_prompt_templates(settings.get("prompt_templates")),
        "service_prompts": merge_service_prompt_configs(settings.get("service_prompts")),
        "model_favorites": merge_unique_str_lists(settings.get("model_favorites")),
        "starred_models": merge_unique_str_lists(settings.get("starred_models")),
        "image_optimization": settings.get("image_optimization"),
    }
    try:
        await ensure_pipeline_catalog(db)
        data["custom_pipelines"] = await list_pipeline_definitions(
            db,
            include_system=False,
        )
    except SQLAlchemyError:
        data["custom_pipelines"] = []

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
async def update_config(
        data: ConfigUpdateRequest,
        db: AsyncSession = Depends(get_db)):
    # pylint: disable=too-many-locals,too-many-branches
    # Separate secrets from general config
    keys_to_persist = [
        "prompt_templates",
        "service_prompts",
        "model_favorites",
        "starred_models",
        "image_optimization",
    ]
    data_dict = data.model_dump(exclude_unset=True)
    if "prompt_templates" in data_dict:
        data_dict["prompt_templates"] = normalize_prompt_templates(
            data_dict.get("prompt_templates"))
    if "custom_pipelines" in data_dict:
        normalized_custom_pipelines = normalize_pipeline_list(
            data_dict.get("custom_pipelines", [])
        )
        await ensure_pipeline_catalog(db)
        await persist_custom_pipelines(db, normalized_custom_pipelines)
    if "service_prompts" in data_dict:
        data_dict["service_prompts"] = normalize_service_prompts(
            data_dict.get("service_prompts")
        )

    await ensure_app_settings_seed(db)
    for key in keys_to_persist:
        if key not in data_dict:
            continue
        await upsert_app_setting(db, key, data_dict.get(key))
        if key == "model_favorites":
            favorites = merge_unique_str_lists(data_dict.get("model_favorites"))
            for model_id in favorites:
                model_result = await db.execute(
                    select(ModelCatalog).where(ModelCatalog.model_id == model_id)
                )
                if model_result.scalar_one_or_none() is None:
                    db.add(
                        ModelCatalog(
                            model_id=model_id,
                            provider=infer_model_provider(model_id),
                            name=model_id,
                            is_active=True,
                            is_system=False,
                        )
                    )

    for key in CONFIG_SECRET_KEYS:
        val = getattr(data, key, None)
        if val and val != "********":
            set_secret_value(key, val)
            encrypted = encrypt_secret(val)

            # Upsert into database
            res = await db.execute(select(ConfigSecret).where(ConfigSecret.key == key))
            secret_obj = res.scalar_one_or_none()
            if secret_obj:
                secret_obj.encrypted_value = encrypted  # type: ignore
            else:
                db.add(ConfigSecret(key=key, encrypted_value=encrypted))

    await db.commit()

    return {"success": True}


@api_router.get("/search", response_model=SearchResponse)
async def search_items(
        query: str,
    db: AsyncSession = Depends(get_db)) -> SearchResponse:
    # pylint: disable=too-many-locals
    # Simple JSON search for product name and brand
    stmt = select(Item).where(
        or_(
            Item.user_overrides['product_name'].astext.ilike(
                f'%{query}%'),
            Item.ai_output['llm_output']['product_name'].astext.ilike(
                f'%{query}%'),
            Item.user_overrides['brand'].astext.ilike(
                f'%{query}%'),
            Item.ai_output['llm_output']['brand'].astext.ilike(
                f'%{query}%'))).order_by(
        Item.created_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()

    res = []
    for item in items:
        stmt_map = select(ServiceMapping).where(
            ServiceMapping.item_id == item.id)
        map_res = await db.execute(stmt_map)
        mappings = map_res.scalars().all()

        user_overrides: Dict[str, Any] = item.user_overrides if isinstance(
            item.user_overrides, dict) else {}
        ai_output: Dict[str, Any] = item.ai_output if isinstance(
            item.ai_output, dict) else {}
        llm_output = ai_output.get("llm_output") if isinstance(
            ai_output.get("llm_output"), dict) else {}
        merged_data = user_overrides or llm_output

        item_data = ItemSearchInfo(
            id=str(item.id),  # type: ignore
            status=item.status,  # type: ignore
            image_path=item.image_path,  # type: ignore
            raw_image_path=item.raw_image_path,  # type: ignore
            product_type=item.product_type,  # type: ignore
            ai_output=ai_output,
            user_overrides=user_overrides,
            product_name=merged_data.get("product_name") if isinstance(
                merged_data, dict) else None,
            brand=merged_data.get("brand") if isinstance(
                merged_data, dict) else None,
            created_at=item.created_at,  # type: ignore
            mappings=[
                ServiceMappingInfo(
                    service=str(m.service_name),
                    external_id=str(m.external_id),
                    url=str(m.external_url) if m.external_url else None,
                )  # type: ignore
                for m in mappings
            ],
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
        if not hasattr(
                homebox,
            "get_headers") or not hasattr(
                homebox,
                "api_url"):
            return LocationsResponse(
                success=False, error="Homebox service misconfigured")

        headers = homebox.get_headers()  # type: ignore
        if not headers:
            return LocationsResponse(success=False, error="No API Key")
        resp = requests.get(f"{homebox.api_url}/locations",
                            headers=headers, timeout=5)  # type: ignore
        return LocationsResponse(success=True, locations=resp.json())
    except requests.RequestException as e:
        return LocationsResponse(success=False, error=str(e))


@api_router.get("/logs/{session_id}", response_model=SessionLogsResponse)
async def get_session_logs(
        session_id: str,
        db: AsyncSession = Depends(get_db)) -> SessionLogsResponse:
    # 1. Try from in-memory session logger
    logs = session_logger.get_logs(session_id)
    if logs:
        return SessionLogsResponse(logs=[{"message": log} for log in logs])

    # 2. Try from database items (looking for matching session_id in JSONB)
    try:
        stmt = select(Item).where(
            Item.ai_output['session_id'].astext == session_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()

        if item and isinstance(
                item.ai_output,
                dict) and "logs" in item.ai_output:
            db_logs = item.ai_output["logs"]
            if isinstance(db_logs, list):
                return SessionLogsResponse(
                    logs=[{"message": str(log)} for log in db_logs])

        # Also support querying by f"batch-item-{item_id}"
        if session_id.startswith("batch-item-"):
            item_id_str = session_id.replace("batch-item-", "")
            if item_id_str.isdigit():
                stmt_batch = select(Item).where(Item.id == int(item_id_str))
                result_batch = await db.execute(stmt_batch)
                item_batch = result_batch.scalar_one_or_none()
                if item_batch and isinstance(
                        item_batch.ai_output,
                        dict) and "logs" in item_batch.ai_output:
                    db_logs = item_batch.ai_output["logs"]
                    if isinstance(db_logs, list):
                        return SessionLogsResponse(
                            logs=[{"message": str(log)} for log in db_logs])
    except (SQLAlchemyError, TypeError, ValueError, AttributeError) as e:
        logger.error(
            "Error querying logs from DB for session %s: %s",
            session_id,
            e)

    return SessionLogsResponse(logs=[])


@api_router.get("/preview/{service_name}",
                response_model=ServicePreviewResponse)
async def get_service_preview(
        service_name: str,
        item_id: int) -> ServicePreviewResponse:
    if service_name not in SERVICES:
        return JSONResponse(
            status_code=404, content={
                "error": "Service not found"})  # type: ignore

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Item).where(Item.id == item_id))
        item = res.scalar_one_or_none()
        if not item:
            return JSONResponse(
                status_code=404, content={
                    "error": "Item not found"})  # type: ignore

        data = get_service_specific_item_data(item, service_name)

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
    # Endpoint signatures are intentionally explicit for multipart/form fields.
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-statements
    try:
        pipeline_settings = json.loads(settings)
    except json.JSONDecodeError:
        pipeline_settings = {}

    pipeline_settings = normalize_pipeline_settings(pipeline_settings)

    try:
        lasso_points = json.loads(lasso_polygon) if lasso_polygon else None
    except json.JSONDecodeError:
        lasso_points = None

    # Reserved for future image transform options from UI.
    _ = (rotation, mirror)

    has_db_pipeline = pipeline_id.startswith("custom_") or pipeline_id.startswith("service_")
    core_pipeline = get_pipeline(pipeline_id, db_pipeline_exists=has_db_pipeline)
    sid = session_id or str(uuid.uuid4())
    session_logger.start_session(sid)

    def log_it(msg):
        session_logger.log(sid, msg)

    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)  # type: ignore
        review_image_data_uri = build_review_image_data_uri(img)
        raw_image_data_uri = encode_image_bytes_to_data_uri(content, mime="image/jpeg")

        # type: ignore
        results = await run_in_threadpool(core_pipeline.run, img, text, pipeline_settings, log_it)

        llm_output = results.get("llm_output") or {}
        service_prompt_configs = await get_runtime_service_prompt_configs()
        enrich_all_services = os.getenv("ENRICH_ALL_SERVICES", "false").lower() in {
            "1", "true", "yes", "on"
        }
        if enrich_all_services:
            target_service_names = list(SERVICES.keys())
        else:
            default_target = "mealie" if llm_output.get("is_food") else "homebox"
            target_service_names = [default_target]

        log_it(
            "🔌 Checking for existing entries in services: "
            + ", ".join(target_service_names)
        )
        enrichment_tasks = [
            SERVICES[name].get_pre_enrichment(llm_output) for name in target_service_names
        ]
        enrichments = await asyncio.gather(*enrichment_tasks, return_exceptions=True)
        service_enrichments: Dict[str, Any] = {}
        for index, service_name in enumerate(target_service_names):
            enrichment = enrichments[index]
            if isinstance(enrichment, Exception):
                log_it(f"⚠️ [Enrichment: {service_name}] Failed: {str(enrichment)}")
                service_enrichments[service_name] = {}
            elif isinstance(enrichment, dict):
                service_enrichments[service_name] = enrichment
            else:
                log_it(
                    f"⚠️ [Enrichment: {service_name}] Unexpected result type: "
                    f"{type(enrichment).__name__}"
                )
                service_enrichments[service_name] = {}

        service_outputs: Dict[str, Dict[str, Any]] = {}
        for service_name in target_service_names:
            context_data = {
                "search": results.get("searxng_results", []),
                "scrape": results.get("scraped_content"),
                "service_enrichment": service_enrichments.get(service_name, {}),
            }
            service_outputs[service_name] = generate_service_output(
                service_name,
                llm_output,
                context_data,
                service_prompt_configs,
                log_cb=log_it,
            )

        results["service_enrichments"] = service_enrichments
        results["service_outputs"] = service_outputs
        results["session_id"] = sid
        results["logs"] = session_logger.get_logs(sid)
        results["review_image_data_uri"] = review_image_data_uri

        async with AsyncSessionLocal() as db:
            stmt = select(Batch).where(Batch.name == "Single Captures")
            res = await db.execute(stmt)
            batch = res.scalar_one_or_none()
            if not batch:
                batch = Batch(name="Single Captures", status="completed")
                db.add(batch)
                await db.commit()
                await db.refresh(batch)

            new_item = Item(
                batch_id=batch.id,
                image_path=review_image_data_uri,
                raw_image_path=raw_image_data_uri,
                lasso_polygon=lasso_points,
                status="pending",
                ai_output=results,
                product_type="food" if results.get(
                    "llm_output",
                    {}).get("is_food") else "product")
            db.add(new_item)
            await db.commit()
            await db.refresh(new_item)
            item_id = new_item.id

        log_it("✨ UI updating with findings.")
        session_logger.end_session(sid)
        return {
            "success": True,
            "session_id": sid,
            "item_id": item_id,
            "results": results,
            "ai_preview": review_image_data_uri,
        }
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        SQLAlchemyError,
        requests.RequestException,
    ) as e:
        log_it(f"❌ Fatal Error: {str(e)}")
        logger.error("Identification failed: %s", e, exc_info=True)
        session_logger.end_session(sid)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "session_id": sid})


@api_router.post("/execute")
async def execute_services(data: Dict):  # pylint: disable=too-many-locals
    item_id = data.get("item_id")
    service_names = data.get("service_names", [])
    overrides = data.get("overrides", {})

    final_data = overrides
    image_path = None
    existing_mappings = {}
    item_obj: Optional[Item] = None

    async with AsyncSessionLocal() as db:
        if item_id:
            res = await db.execute(select(Item).where(Item.id == item_id))
            item = res.scalar_one_or_none()
            if item:
                item_obj = item
                image_path = item.image_path
                if not final_data:
                    final_data = get_item_base_data(item)

                map_res = await db.execute(
                    select(ServiceMapping).where(ServiceMapping.item_id == item_id)
                )
                for m in map_res.scalars().all():
                    existing_mappings[m.service_name] = m.external_id

    if not final_data:
        return {"success": False, "error": "No data to process"}

    results_map = {}
    for name in service_names:
        if name not in SERVICES:
            continue
        svc = SERVICES[name]
        ext_id = existing_mappings.get(name)
        service_data = final_data
        if item_obj and not overrides:
            service_data = get_service_specific_item_data(item_obj, name)

        res = await svc.execute(service_data, image_path=image_path, external_id=ext_id)
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
                    mapping.last_sync_payload = service_data
                    mapping.synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    mapping = ServiceMapping(
                        item_id=item_id,
                        service_name=name,
                        external_id=new_ext_id,
                        external_url=ext_url,
                        last_sync_payload=service_data
                    )
                    db.add(mapping)

                await db.execute(update(Item).where(Item.id == item_id).values(status="uploaded"))
                await db.commit()

    return {"success": True, "results": results_map}


@app.post(
    "/service-output/generate",
    response_model=ServiceOutputGenerateResponse,
    include_in_schema=False,
)
@api_router.post(
    "/service-output/generate",
    response_model=ServiceOutputGenerateResponse,
)
async def generate_service_output_for_item(
    request: ServiceOutputGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ServiceOutputGenerateResponse:
    service_name = request.service_name
    if service_name not in SERVICES:
        return ServiceOutputGenerateResponse(
            success=False,
            service_name=service_name,
            error="Service not found",
        )

    res = await db.execute(select(Item).where(Item.id == request.item_id))
    item = res.scalar_one_or_none()
    if not item:
        return ServiceOutputGenerateResponse(
            success=False,
            service_name=service_name,
            error="Item not found",
        )

    ai_output: Dict[str, Any] = (
        cast(Dict[str, Any], item.ai_output)
        if isinstance(item.ai_output, dict)
        else {}
    )
    service_outputs_raw = ai_output.get("service_outputs")
    service_outputs: Dict[str, Any] = (
        service_outputs_raw if isinstance(service_outputs_raw, dict) else {}
    )
    existing_output_raw = service_outputs.get(service_name)
    existing_output: Dict[str, Any] = (
        existing_output_raw if isinstance(existing_output_raw, dict) else {}
    )
    if (
        not request.force
        and existing_output.get("status") == "ready"
        and isinstance(existing_output.get("data"), dict)
    ):
        return ServiceOutputGenerateResponse(
            success=True,
            service_name=service_name,
            cached=True,
            output=existing_output,
        )

    service_prompt_configs = await get_runtime_service_prompt_configs()
    base_data = get_item_base_data(item)
    context_data = get_service_context_from_item(item, service_name)
    output = generate_service_output(
        service_name,
        base_data,
        context_data,
        service_prompt_configs,
    )

    service_outputs[service_name] = output
    ai_output["service_outputs"] = service_outputs
    setattr(item, "ai_output", ai_output)
    await db.commit()

    return ServiceOutputGenerateResponse(
        success=output.get("status") == "ready",
        service_name=service_name,
        cached=False,
        output=output,
        error=output.get("error"),
    )

# --- Batch Processing ---


@api_router.post("/batch-upload")
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    text: Optional[str] = Form(None),
    pipeline_id: str = Form("default"),
    settings: str = Form("{}"),
    db: AsyncSession = Depends(get_db)
):  # pylint: disable=too-many-arguments,too-many-positional-arguments
    new_batch = Batch(description=text)
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)

    for file in files:
        if file.content_type and not file.content_type.startswith("image/"):
            continue
        content = await file.read()
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)  # type: ignore
        review_image_data_uri = build_review_image_data_uri(img)
        raw_image_data_uri = encode_image_bytes_to_data_uri(content, mime="image/jpeg")

        new_item = Item(
            batch_id=new_batch.id,
            image_path=review_image_data_uri,
            raw_image_path=raw_image_data_uri,
            status="processing")
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        background_tasks.add_task(process_item_task_safe, int(
            new_item.id), pipeline_id, settings)  # type: ignore

    return {"success": True, "batch_id": new_batch.id}


async def process_item_task(
        item_id: int,
        pipeline_id: str = "default",
        settings_str: str = "{}"):
    # pylint: disable=too-many-locals
    try:
        settings = json.loads(settings_str)
    except json.JSONDecodeError:
        settings = {}
    has_db_pipeline = pipeline_id.startswith("custom_") or pipeline_id.startswith("service_")
    core_pipeline = get_pipeline(pipeline_id, db_pipeline_exists=has_db_pipeline)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Item).where(Item.id == item_id))
        item = result.scalar_one_or_none()
        if not item:
            return

        sid = f"batch-item-{item_id}"
        session_logger.start_session(sid)

        def log_it(msg):
            session_logger.log(sid, msg)

        res = await db.execute(select(Batch).where(Batch.id == item.batch_id))
        batch = res.scalar_one_or_none()
        batch_text = batch.description if batch else None

        try:
            image_data_uri = item_source_image_data_uri(item)
            if not image_data_uri:
                raise ValueError("No image data found on item")

            image_bytes = decode_data_uri_to_bytes(image_data_uri)
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)  # type: ignore
            results = await run_in_threadpool(core_pipeline.run, img, batch_text, settings, log_it)
            results["review_image_data_uri"] = build_review_image_data_uri(img)

            enrichment_tasks = [
                s.get_pre_enrichment(
                    results['llm_output']) for s in SERVICES.values()]
            enrichments = await asyncio.gather(*enrichment_tasks)
            results["service_enrichments"] = {
                list(
                    SERVICES.keys())[i]: enrichments[i] for i in range(
                    len(enrichments))}

            service_prompt_configs = await get_runtime_service_prompt_configs()
            llm_output_raw = results.get("llm_output")
            llm_output: Dict[str, Any] = llm_output_raw if isinstance(llm_output_raw, dict) else {}
            default_target = "mealie" if llm_output.get("is_food") else "homebox"
            context_data = {
                "search": results.get("searxng_results", []),
                "scrape": results.get("scraped_content"),
                "service_enrichment": results["service_enrichments"].get(default_target, {}),
            }
            results["service_outputs"] = {
                default_target: generate_service_output(
                    default_target,
                    llm_output,
                    context_data,
                    service_prompt_configs,
                    log_cb=log_it,
                )
            }
            results["session_id"] = sid
            results["logs"] = session_logger.get_logs(sid)

            item.ai_output = results
            item.image_path = results["review_image_data_uri"]
            item.product_type = "food" if results.get(
                "llm_output", {}).get("is_food") else "product"
            item.status = "pending"
        except (
            OSError,
            ValueError,
            TypeError,
            RuntimeError,
            SQLAlchemyError,
            requests.RequestException,
        ) as e:
            log_it(f"❌ Error: {str(e)}")
            logger.error("Processing failed for item %s: %s", item_id, e)
            item.status = "error"
            item.error = str(e)
            item.ai_output = {
                "session_id": sid,
                "logs": session_logger.get_logs(sid),
                "error": str(e)
            }

        session_logger.end_session(sid)
        await db.commit()


async def process_item_task_safe(
        item_id: int,
        pipeline_id: str = "default",
        settings_str: str = "{}"):
    """Run background processing and swallow task-level failures.

    This prevents background task exceptions from bubbling into response handling.
    """
    try:
        await process_item_task(item_id, pipeline_id, settings_str)
    except (
        OSError,
        ValueError,
        TypeError,
        RuntimeError,
        SQLAlchemyError,
        requests.RequestException,
    ) as e:
        logger.error(
            "Background processing failed for item %s: %s",
            item_id,
            e,
            exc_info=True)


@api_router.get("/queue")
async def get_queue(
        status: str = "pending",
        db: AsyncSession = Depends(get_db)):
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
async def update_item_data(
        item_id: int,
        data: dict,
        db: AsyncSession = Depends(get_db)):
    query = update(Item).where(Item.id == item_id).values(**data)
    await db.execute(query)
    await db.commit()
    return {"success": True}


@api_router.post("/items/{item_id}/rerun")
async def rerun_item(
        item_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db)):
    await db.execute(update(Item).where(Item.id == item_id).values(status="processing"))
    await db.commit()
    background_tasks.add_task(process_item_task_safe, item_id, "default", "{}")
    return {"success": True}


@api_router.delete("/items/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item:
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
        if not item:
            continue
        svc = "mealie" if item.product_type == "food" else "homebox"
        exec_res = await execute_services({"item_id": iid, "service_names": [svc]})
        if exec_res.get("success"):
            results["success"].append(iid)
        else:
            results["failed"].append(
                {"id": iid, "error": exec_res.get("error")})
    return results

app.include_router(api_router)

@app.get("/")
async def root():
    if WEB_INDEX_FILE.exists():
        return FileResponse(str(WEB_INDEX_FILE))
    return RedirectResponse(url="/docs")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if not full_path:
        if WEB_INDEX_FILE.exists():
            return FileResponse(str(WEB_INDEX_FILE))
        return RedirectResponse(url="/docs")

    excluded_prefixes = ("api/", "docs", "openapi.json", "uploads/", "internal/")
    if full_path.startswith(excluded_prefixes):
        raise HTTPException(status_code=404, detail="Not found")

    candidate = (WEB_DIST_DIR / full_path).resolve()
    try:
        candidate.relative_to(WEB_DIST_DIR.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if candidate.is_file():
        return FileResponse(str(candidate))

    if WEB_INDEX_FILE.exists():
        return FileResponse(str(WEB_INDEX_FILE))

    raise HTTPException(status_code=404, detail="Not found")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", "8460"))
    uvicorn.run(app, host="0.0.0.0", port=port)
