# pylint: disable=unused-import
import os
import io
import logging
import importlib
import asyncio
from contextlib import suppress
from pathlib import Path
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

# Load environment variables FIRST before other imports
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import database
from database import (
    init_db,
    get_db,
    ConfigSecret,
    ModelCatalog,
    PipelineDefinition,
    Batch,
    Item,
    ServiceMapping,
)
from secrets_manager import (
    encrypt_secret,
    decrypt_secret,
    get_secret_value,
    set_secret_value,
    CONFIG_SECRET_KEYS,
    upsert_secret,
    ORIGINAL_ENV,
)
from image_utils import (
    encode_image_bytes_to_data_uri,
    decode_data_uri_to_bytes,
    build_review_image_data_uri,
    build_seed_image_data_uri,
    item_source_image_data_uri,
)
from services.registry import SERVICES, gmail_ingestor, receipt_wrangler_client
from tasks import (
    process_item_task,
    process_item_task_safe,
    ingest_receipt_jobs_direct,
    ingest_gmail_receipts_direct,
)
from scheduler import configure_gmail_auto_sync_scheduler, RUNTIME_STATE
from app_helpers import (
    ensure_pipeline_catalog,
    ensure_model_catalog,
    ensure_app_settings_seed,
    get_runtime_service_prompt_configs,
    get_app_settings,
    normalize_prompt_templates,
    apply_service_output_feedback_fallbacks,
    upsert_app_setting,
    get_pipeline,
    list_pipeline_definitions,
    persist_custom_pipelines,
    build_service_feedback_context,
    extract_search_candidates,
    get_item_base_data,
    get_service_context_from_item,
    get_service_prompt_config,
    get_service_specific_item_data,
    infer_model_provider,
    merge_service_prompt_configs,
    merge_unique_str_lists,
    normalize_app_setting,
    normalize_pipeline_list,
    normalize_pipeline_schema,
    normalize_pipeline_settings,
    normalize_service_prompts,
    should_run_service_feedback_pass,
)
from schemas import (
    ServiceOutputGenerateRequest,
    ServiceOutputGenerateResponse,
    ConfigUpdateRequest,
)

# Import new decoupled routes
from routes.config_routes import (
    router as config_router,
    get_config,
    update_config,
    export_config,
    import_config,
    autodiscover_settings,
)
from routes.pipeline_routes import (
    router as pipeline_router,
    list_pipelines,
    upsert_pipeline,
    delete_pipeline,
)
from routes.model_routes import (
    router as model_router,
    list_models,
)
from routes.gmail_routes import router as gmail_router
from routes.item_routes import (
    router as item_router,
    get_queue,
    get_item,
    update_item_data,
    rerun_item,
    delete_item,
    bulk_approve,
    identify,
    batch_upload,
    share_target,
    get_session_logs,
)
from routes.service_routes import (
    router as service_router,
    execute_services,
    generate_service_output_for_item,
    get_service_preview,
    get_locations,
)

# --- Logging ---
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)
root_logger.addHandler(handler)
logger = logging.getLogger("VisionAPI")


# --- Lifespan ---
async def lifespan(_app: FastAPI):
    await init_db()
    async with database.async_session_local() as db:
        await ensure_pipeline_catalog(db)
        await ensure_model_catalog(db)
        await ensure_app_settings_seed(db)
        
        # Load db secrets into environments
        from sqlalchemy import select
        res = await db.execute(select(ConfigSecret))
        secrets = res.scalars().all()
        for secret in secrets:
            try:
                os.environ[secret.key] = decrypt_secret(secret.encrypted_value)
                logger.info("Loaded encrypted secret: %s", secret.key)
            except ValueError as e:
                logger.error("Failed to decrypt secret %s: %s", secret.key, e)
                
    await configure_gmail_auto_sync_scheduler()
    try:
        yield
    finally:
        scheduler = RUNTIME_STATE.get("gmail_scheduler")
        if isinstance(scheduler, AsyncIOScheduler) and scheduler.running:
            scheduler.shutdown(wait=False)


# --- Setup ---
app = FastAPI(
    lifespan=lifespan,
    title="Vision Pipeline API",
    version="3.6.12",
    redoc_url=None,
)

WEB_DIST_DIR = Path(os.getenv("WEB_DIST_DIR", "/app/web_dist"))
WEB_INDEX_FILE = WEB_DIST_DIR / "index.html"
WEB_DIST_FALLBACKS = [
    Path("/app/dist"),
    Path("/app/web/dist"),
    Path("/app/frontend/dist"),
    Path("web_dist"),
    Path("dist"),
]

# Ensure directories exist
os.makedirs("data/uploads", exist_ok=True)

# Mount uploads for serving review images
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")


def resolve_web_dist_dir() -> Path:
    candidates = [WEB_DIST_DIR, *WEB_DIST_FALLBACKS]
    for candidate in candidates:
        if (candidate / "index.html").exists():
            return candidate
    return WEB_DIST_DIR


def resolve_web_index_file() -> Optional[Path]:
    candidates = [WEB_INDEX_FILE]
    for directory in WEB_DIST_FALLBACKS:
        candidates.append(directory / "index.html")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# --- Register Decoupled Routers ---
api_router = APIRouter(prefix="/api")
api_router.include_router(config_router)
api_router.include_router(pipeline_router)
api_router.include_router(model_router)
api_router.include_router(gmail_router)
api_router.include_router(item_router)
api_router.include_router(service_router)
app.include_router(api_router)


# --- Root / Scrape API ---
class ScrapeRequest(BaseModel):
    url: str
    wait_time: int = 2000


@app.post("/internal/scrape", include_in_schema=False)
async def scrape_url(req: ScrapeRequest):
    try:
        from playwright.async_api import async_playwright  # type: ignore[import-not-found]
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


# --- Preserve Root Service Output Alias ---
@app.post(
    "/service-output/generate",
    response_model=ServiceOutputGenerateResponse,
    include_in_schema=False,
)
async def generate_service_output_for_item_alias(
    request: ServiceOutputGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ServiceOutputGenerateResponse:
    return await generate_service_output_for_item(request, db)


# --- Root / Static File Serving ---
@app.get("/")
async def root():
    index_file = resolve_web_index_file()
    if index_file is not None:
        return FileResponse(str(index_file))
    return RedirectResponse(url="/docs")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    dist_dir = resolve_web_dist_dir()
    index_file = dist_dir / "index.html"

    if not full_path:
        if index_file.exists():
            return FileResponse(str(index_file))
        return RedirectResponse(url="/docs")

    excluded_prefixes = ("api/", "docs", "openapi.json", "uploads/", "internal/")
    if full_path.startswith(excluded_prefixes):
        raise HTTPException(status_code=404, detail="Not found")

    candidate = (dist_dir / full_path).resolve()
    try:
        candidate.relative_to(dist_dir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc

    if candidate.is_file():
        return FileResponse(str(candidate))

    if index_file.exists():
        return FileResponse(str(index_file))

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", "8460"))
    uvicorn.run(app, host="0.0.0.0", port=port)
