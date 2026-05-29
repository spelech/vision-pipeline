import json
import os
import io
import uuid
import base64
import logging
import asyncio
from datetime import datetime, UTC
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any, cast
import requests
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
from fastapi.responses import JSONResponse, RedirectResponse
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
    AppSetting,
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
from pipelines import (  # pylint: disable=wrong-import-position
    PIPELINE_REGISTRY,
    DefaultPipeline,
    ComposablePipeline,
)
import pipelines  # pylint: disable=wrong-import-position
from pipelines.nodes import data_refine  # pylint: disable=wrong-import-position
from services.homebox import HomeboxService  # pylint: disable=wrong-import-position
from services.mealie import MealieService  # pylint: disable=wrong-import-position
from services.enrichers import PriceBuddyService, ChangeDetectionService  # pylint: disable=wrong-import-position
from logger import session_logger  # pylint: disable=wrong-import-position


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


MODEL_ID_ALIASES: Dict[str, str] = {
    "qwen/qwen2.5-72b-instruct": "qwen/qwen3-235b-a22b-2507",
    "qwen/qwen2.5-32b-instruct": "qwen/qwen3-235b-a22b-2507",
}

SERVICE_NAMES = ["homebox", "mealie", "pricebuddy", "changedetection"]
DB_SETTING_KEYS = [
    "prompt_templates",
    "service_prompts",
    "model_favorites",
    "starred_models",
    "image_optimization",
]

DEFAULT_MODEL_CATALOG: List[Dict[str, str]] = [
    {
        "id": "qwen/qwen2.5-vl-72b-instruct",
        "name": "Qwen 2.5 VL 72B (OpenRouter)",
        "provider": "openrouter",
    },
    {
        "id": "google/gemini-2.0-flash-001",
        "name": "Gemini 2.0 Flash (OpenRouter)",
        "provider": "openrouter",
    },
    {
        "id": "anthropic/claude-3.5-sonnet",
        "name": "Claude 3.5 Sonnet (OpenRouter)",
        "provider": "openrouter",
    },
]


def get_pipeline(pipeline_id: str, db_pipeline_exists: bool = False):
    if pipeline_id in PIPELINE_REGISTRY:
        return PIPELINE_REGISTRY[pipeline_id]()
    if db_pipeline_exists:
        return ComposablePipeline()
    return DefaultPipeline()


def _service_target_for_pipeline_id(pipeline_id: str) -> Optional[str]:
    if pipeline_id.startswith("service_"):
        return pipeline_id.replace("service_", "", 1)
    return None


def _pipeline_row_to_dict(row: PipelineDefinition) -> Dict[str, Any]:
    schema: Dict[str, Any] = row.schema if isinstance(row.schema, dict) else {}
    return {
        "id": row.pipeline_id,
        "name": row.name,
        "schema": normalize_pipeline_schema(schema),
        "is_system": bool(row.is_system),
        "is_editable": bool(row.is_editable),
        "service_target": row.service_target,
    }


def infer_model_provider(model_id: str) -> str:
    owner = (
        model_id.split("/", 1)[0].strip().lower()
        if "/" in model_id
        else model_id.strip().lower()
    )
    if not owner:
        return "custom"
    if owner in {"google", "qwen", "anthropic", "openai", "meta", "mistralai", "x-ai", "deepseek"}:
        return "openrouter"
    return owner


def normalize_app_setting(key: str, value: Any) -> Any:
    if key == "prompt_templates":
        return normalize_prompt_templates(value)
    if key == "service_prompts":
        return normalize_service_prompts(value)
    if key in {"model_favorites", "starred_models"}:
        return merge_unique_str_lists(value)
    if key == "image_optimization" and isinstance(value, dict):
        return value
    return value


async def upsert_app_setting(db: AsyncSession, key: str, value: Any) -> None:
    normalized_value = normalize_app_setting(key, value)
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = normalized_value  # type: ignore
    else:
        db.add(AppSetting(key=key, value=normalized_value))


async def get_app_settings(db: AsyncSession) -> Dict[str, Any]:
    result = await db.execute(select(AppSetting))
    rows = result.scalars().all()
    settings: Dict[str, Any] = {}
    for row in rows:
        settings[str(row.key)] = row.value
    return settings


async def ensure_model_catalog(db: AsyncSession) -> None:
    result = await db.execute(select(ModelCatalog.model_id))
    existing_ids = {str(item[0]) for item in result.all()}
    created = False
    for model in DEFAULT_MODEL_CATALOG:
        model_id = str(model.get("id", "")).strip()
        if not model_id or model_id in existing_ids:
            continue
        db.add(
            ModelCatalog(
                model_id=model_id,
                provider=str(model.get("provider") or infer_model_provider(model_id)),
                name=str(model.get("name") or model_id),
                is_active=True,
                is_system=True,
            )
        )
        created = True

    if created:
        await db.commit()


async def ensure_app_settings_seed(db: AsyncSession) -> None:
    existing = await get_app_settings(db)
    if all(key in existing for key in DB_SETTING_KEYS):
        return

    defaults: Dict[str, Any] = {
        "prompt_templates": [],
        "service_prompts": default_service_prompt_configs(),
        "model_favorites": [],
        "starred_models": [],
        "image_optimization": {},
    }
    for key in DB_SETTING_KEYS:
        if key in existing:
            continue
        await upsert_app_setting(db, key, defaults.get(key))

    model_ids: set[str] = set()

    catalog_result = await db.execute(select(ModelCatalog.model_id))
    for item in catalog_result.all():
        model_ids.add(str(item[0]))
    await upsert_app_setting(db, "model_favorites", list(model_ids))

    await db.commit()


async def get_runtime_service_prompt_configs() -> Dict[str, Dict[str, Any]]:
    async with AsyncSessionLocal() as db:
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)
        return merge_service_prompt_configs(settings.get("service_prompts"))


async def ensure_pipeline_catalog(db: AsyncSession) -> None:
    try:
        registry_entries = normalize_pipeline_list(pipelines.get_all_pipelines())
        result = await db.execute(select(PipelineDefinition.pipeline_id))
        existing_ids = {str(item[0]) for item in result.all()}

        created = False
        for entry in registry_entries:
            pipeline_id = str(entry.get("id", "")).strip()
            if not pipeline_id or pipeline_id in existing_ids:
                continue
            db.add(
                PipelineDefinition(
                    pipeline_id=pipeline_id,
                    name=str(entry.get("name", pipeline_id)),
                    schema=normalize_pipeline_schema(entry.get("schema") or {}),
                    is_system=True,
                    is_editable=True,
                    service_target=_service_target_for_pipeline_id(pipeline_id),
                )
            )
            created = True

        if created:
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Skipping pipeline catalog sync because DB is unavailable")


async def pipeline_definition_exists(db: AsyncSession, pipeline_id: str) -> bool:
    try:
        result = await db.execute(
            select(PipelineDefinition.id).where(PipelineDefinition.pipeline_id == pipeline_id)
        )
        return result.first() is not None
    except SQLAlchemyError:
        return False


async def list_pipeline_definitions(
    db: AsyncSession,
    include_system: bool = True,
) -> List[Dict[str, Any]]:
    stmt = select(PipelineDefinition)
    if not include_system:
        stmt = stmt.where(PipelineDefinition.is_system.is_(False))

    try:
        result = await db.execute(
            stmt.order_by(PipelineDefinition.is_system.desc(), PipelineDefinition.pipeline_id.asc())
        )
        rows = result.scalars().all()
        return [_pipeline_row_to_dict(row) for row in rows]
    except SQLAlchemyError:
        return []


async def persist_custom_pipelines(
    db: AsyncSession,
    custom_pipelines: List[Dict[str, Any]],
) -> None:
    existing_result = await db.execute(
        select(PipelineDefinition).where(PipelineDefinition.is_system.is_(False))
    )
    for row in existing_result.scalars().all():
        await db.delete(row)

    for pipeline in custom_pipelines:
        pipeline_id = str(pipeline.get("id", "")).strip()
        if not pipeline_id:
            continue
        db.add(
            PipelineDefinition(
                pipeline_id=pipeline_id,
                name=str(pipeline.get("name", pipeline_id)),
                schema=normalize_pipeline_schema(pipeline.get("schema") or {}),
                is_system=False,
                is_editable=True,
                service_target=_service_target_for_pipeline_id(pipeline_id),
            )
        )

    await db.commit()


def default_service_prompt_configs() -> Dict[str, Dict[str, Any]]:
    return {
        "homebox": {
            "service": "homebox",
            "model": "qwen/qwen3-235b-a22b-2507",
            "enabled": True,
            "prompt": (
                "Create Homebox-ready inventory JSON from the provided product data and context. "
                "Prioritize product_name, brand, model_number, category, description, "
                "and technical_details. "
                "Prefer factual values supported by search/scrape context. Return strict JSON only."
            ),
            "feedback_enabled": False,
        },
        "mealie": {
            "service": "mealie",
            "model": "qwen/qwen3-235b-a22b-2507",
            "enabled": True,
            "prompt": (
                "Create Mealie-ready recipe JSON from the provided food data and context. "
                "Prioritize product_name, recipe_ingredients, and recipe_instructions. "
                "Include recipe_notes when available. "
                "If data is uncertain, preserve confidence in notes. Return strict JSON only."
            ),
            "feedback_enabled": False,
        },
        "pricebuddy": {
            "service": "pricebuddy",
            "model": "qwen/qwen3-235b-a22b-2507",
            "enabled": True,
            "prompt": (
                "Create PriceBuddy-ready product tracking JSON from the provided data and context. "
                "Prioritize product_name, barcode, product_url, and "
                "monitor_urls/comparable_urls from search evidence. "
                "Prefer retailer product pages over blogs or forums. "
                "Return strict JSON only."
            ),
            "feedback_enabled": True,
            "feedback_prompt": (
                "Revise the PriceBuddy JSON using feedback candidates from search results. "
                "Choose URLs that best match the same product across major retailers, "
                "remove irrelevant links, "
                "and keep only concise, valid JSON fields. Return strict JSON only."
            ),
        },
        "changedetection": {
            "service": "changedetection",
            "model": "qwen/qwen3-235b-a22b-2507",
            "enabled": True,
            "prompt": (
                "Create ChangeDetection-ready monitoring JSON from the provided data and context. "
                "Prioritize product_name, product_url, monitor_urls, and change_monitoring_notes. "
                "When possible, select multiple matching retailer product URLs for monitoring. "
                "Return strict JSON only."
            ),
            "feedback_enabled": True,
            "feedback_prompt": (
                "Revise the ChangeDetection JSON using feedback candidates from search results. "
                "Ensure product_url is the best primary URL and monitor_urls contains "
                "additional relevant retailers "
                "for the same product. Keep strict JSON only."
            ),
        },
    }


def normalize_service_prompts(value: Any) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    if not isinstance(value, dict):
        return normalized

    for service_name, config in value.items():
        if service_name not in SERVICE_NAMES:
            continue
        if isinstance(config, str):
            normalized[service_name] = {
                "service": service_name,
                "prompt": config,
                "model": None,
                "enabled": True,
                "feedback_enabled": True,
                "feedback_prompt": "",
            }
            continue

        if isinstance(config, dict):
            normalized[service_name] = {
                "service": service_name,
                "prompt": str(config.get("prompt", "")),
                "model": normalize_model_id(config.get("model")),
                "enabled": bool(config.get("enabled", True)),
                "feedback_enabled": bool(config.get("feedback_enabled", True)),
                "feedback_prompt": str(config.get("feedback_prompt", "")),
            }

    return normalized


def merge_service_prompt_configs(*values: Any) -> Dict[str, Dict[str, Any]]:
    merged = default_service_prompt_configs()
    for value in values:
        normalized = normalize_service_prompts(value)
        for service_name, config in normalized.items():
            merged[service_name] = {
                **merged.get(service_name, {}),
                **config,
                "service": service_name,
            }
    return merged


def get_service_prompt_config(
    service_name: str,
    service_prompt_configs: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        **default_service_prompt_configs().get(service_name, {}),
        **service_prompt_configs.get(service_name, {}),
        "service": service_name,
    }


def _extract_terms(value: Any) -> List[str]:
    if not isinstance(value, str):
        return []
    return [part.strip().lower() for part in value.split() if len(part.strip()) >= 3]


def extract_search_candidates(  # pylint: disable=too-many-locals
    search_results: Any,
    base_data: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not isinstance(search_results, list):
        return []

    common_retailer_tokens = [
        "amazon",
        "walmart",
        "target",
        "bestbuy",
        "costco",
        "homedepot",
        "lowes",
        "ebay",
        "newegg",
        "wayfair",
    ]
    product_terms = _extract_terms(
        str(base_data.get("product_name") or base_data.get("name") or "")
    )

    candidates: List[Dict[str, Any]] = []
    for result in search_results[:12]:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            continue
        title = str(result.get("title") or "").strip()
        snippet = str(result.get("content") or "").strip()
        domain = urlparse(url).netloc.lower()
        haystack = f"{title} {snippet}".lower()

        score = 0
        if any(token in domain for token in common_retailer_tokens):
            score += 2
        if any(term in haystack for term in product_terms):
            score += 1

        candidates.append(
            {
                "url": url,
                "title": title,
                "snippet": snippet,
                "domain": domain,
                "score": score,
                "is_retailer": any(token in domain for token in common_retailer_tokens),
            }
        )

    candidates.sort(
        key=lambda item: (
            int(item.get("score", 0)),
            bool(item.get("is_retailer")),
        ),
        reverse=True,
    )
    return candidates


def build_service_feedback_context(
    service_name: str,
    base_data: Dict[str, Any],
    context_data: Dict[str, Any],
) -> Dict[str, Any]:
    search_candidates = extract_search_candidates(context_data.get("search"), base_data)
    candidate_urls = [item["url"] for item in search_candidates if isinstance(item.get("url"), str)]
    retailer_urls = [
        item["url"]
        for item in search_candidates
        if item.get("is_retailer") and isinstance(item.get("url"), str)
    ]

    # Service-specific hints keep the feedback pass targeted.
    required_fields: List[str]
    if service_name == "changedetection":
        required_fields = [
            "product_name",
            "product_url",
            "monitor_urls",
            "change_monitoring_notes",
        ]
    elif service_name == "pricebuddy":
        required_fields = ["product_name", "barcode", "product_url", "monitor_urls"]
    else:
        required_fields = ["product_name"]

    return {
        "candidate_urls": candidate_urls[:8],
        "retailer_urls": retailer_urls[:6],
        "required_fields": required_fields,
        "top_candidates": search_candidates[:6],
    }


def should_run_service_feedback_pass(service_name: str, feedback_context: Dict[str, Any]) -> bool:
    if service_name not in {"pricebuddy", "changedetection"}:
        return False
    candidate_urls = feedback_context.get("candidate_urls")
    return isinstance(candidate_urls, list) and len(candidate_urls) > 0


def apply_service_output_feedback_fallbacks(
    service_name: str,
    refined: Dict[str, Any],
    feedback_context: Dict[str, Any],
) -> Dict[str, Any]:
    output = dict(refined)
    candidate_urls = [
        str(url).strip()
        for url in feedback_context.get("candidate_urls", [])
        if isinstance(url, str) and str(url).strip()
    ]
    retailer_urls = [
        str(url).strip()
        for url in feedback_context.get("retailer_urls", [])
        if isinstance(url, str) and str(url).strip()
    ]

    if service_name in {"pricebuddy", "changedetection"}:
        if not str(output.get("product_url") or "").strip():
            primary = (retailer_urls or candidate_urls or [""])[0]
            if primary:
                output["product_url"] = primary

        existing_monitor_urls = output.get("monitor_urls", [])
        monitor_urls: List[str] = []
        if isinstance(existing_monitor_urls, list):
            monitor_urls.extend(
                str(url).strip()
                for url in existing_monitor_urls
                if isinstance(url, str) and str(url).strip()
            )
        for url in retailer_urls + candidate_urls:
            if url not in monitor_urls:
                monitor_urls.append(url)
            if len(monitor_urls) >= 6:
                break
        if monitor_urls:
            output["monitor_urls"] = monitor_urls

    return output


def generate_service_output(
    service_name: str,
    base_data: Dict[str, Any],
    context_data: Dict[str, Any],
    service_prompt_configs: Dict[str, Dict[str, Any]],
    log_cb=None,
) -> Dict[str, Any]:
    # pylint: disable=too-many-locals
    prompt_config = get_service_prompt_config(service_name, service_prompt_configs)
    if not prompt_config.get("enabled", True):
        return {
            "status": "skipped",
            "error": "Service prompt disabled",
            "data": {},
        }

    model = prompt_config.get("model")
    prompt_template = str(prompt_config.get("prompt", "")).strip()
    feedback_enabled = bool(prompt_config.get("feedback_enabled", True))
    feedback_template = str(prompt_config.get("feedback_prompt", "")).strip()
    feedback_context = build_service_feedback_context(service_name, base_data, context_data)

    generation_context = {
        **context_data,
        "feedback_hints": feedback_context,
    }
    prompt = (
        f"{prompt_template}\n"
        f"Service: {service_name}\n"
        f"Current Data: {json.dumps(base_data)}\n"
        f"Context: {json.dumps(generation_context)}"
    )

    if log_cb:
        log_cb(f"🧩 [Service Prompt: {service_name}] Generating service-specific output...")

    refined = data_refine(base_data, generation_context, model=model, prompt=prompt, log_cb=log_cb)
    if not isinstance(refined, dict):
        return {
            "status": "error",
            "error": "Service prompt output was not JSON",
            "data": {},
        }

    feedback_applied = False
    if feedback_enabled and should_run_service_feedback_pass(service_name, feedback_context):
        feedback_applied = True
        if log_cb:
            log_cb(
                f"🔁 [Service Prompt: {service_name}] "
                "Applying search-feedback refinement pass..."
            )
        feedback_prompt = (
            f"{feedback_template or (
                'Revise JSON output using candidate URLs and service constraints.'
            )}\n"
            f"Service: {service_name}\n"
            f"Current Data: {json.dumps(base_data)}\n"
            f"Initial Output: {json.dumps(refined)}\n"
            f"Feedback Context: {json.dumps(feedback_context)}"
        )
        refined_feedback = data_refine(
            refined,
            {"feedback": feedback_context, **context_data},
            model=model,
            prompt=feedback_prompt,
            log_cb=log_cb,
        )
        if isinstance(refined_feedback, dict):
            refined = refined_feedback

    refined = apply_service_output_feedback_fallbacks(service_name, refined, feedback_context)

    return {
        "status": "ready",
        "error": None,
        "data": refined,
        "model": model,
        "feedback_applied": feedback_applied,
        "feedback_hints": {
            "candidate_urls": feedback_context.get("candidate_urls", [])[:3],
            "retailer_urls": feedback_context.get("retailer_urls", [])[:3],
        },
    }


def get_item_base_data(item: Any) -> Dict[str, Any]:
    user_overrides = item.user_overrides if isinstance(item.user_overrides, dict) else {}
    if user_overrides:
        return dict(user_overrides)

    ai_output: Dict[str, Any] = (
        cast(Dict[str, Any], item.ai_output)
        if isinstance(item.ai_output, dict)
        else {}
    )
    llm_output_raw = ai_output.get("llm_output")
    llm_output: Dict[str, Any] = llm_output_raw if isinstance(llm_output_raw, dict) else {}
    base_data: Dict[str, Any] = dict(llm_output.items())
    if isinstance(ai_output.get("searxng_results"), list):
        base_data["searxng_results"] = ai_output.get("searxng_results")
    if isinstance(ai_output.get("scraped_content"), str):
        base_data["scraped_content"] = ai_output.get("scraped_content")
    return base_data


def get_service_specific_item_data(item: Any, service_name: str) -> Dict[str, Any]:
    base_data = get_item_base_data(item)
    ai_output: Dict[str, Any] = (
        cast(Dict[str, Any], item.ai_output)
        if isinstance(item.ai_output, dict)
        else {}
    )
    service_outputs_raw = ai_output.get("service_outputs")
    service_outputs: Dict[str, Any] = (
        service_outputs_raw if isinstance(service_outputs_raw, dict) else {}
    )
    service_output_entry_raw = service_outputs.get(service_name)
    service_output_entry: Dict[str, Any] = (
        service_output_entry_raw if isinstance(service_output_entry_raw, dict) else {}
    )
    service_data_raw = service_output_entry.get("data")
    service_data: Dict[str, Any] = (
        service_data_raw if isinstance(service_data_raw, dict) else {}
    )
    return {**base_data, **service_data}


def get_service_context_from_item(item: Any, service_name: str) -> Dict[str, Any]:
    ai_output: Dict[str, Any] = (
        cast(Dict[str, Any], item.ai_output)
        if isinstance(item.ai_output, dict)
        else {}
    )
    service_enrichments_raw = ai_output.get("service_enrichments")
    service_enrichments: Dict[str, Any] = (
        service_enrichments_raw if isinstance(service_enrichments_raw, dict) else {}
    )
    return {
        "search": ai_output.get("searxng_results", []),
        "scrape": ai_output.get("scraped_content"),
        "service_enrichment": service_enrichments.get(service_name, {}),
    }


def normalize_model_id(value: Any) -> Any:
    if isinstance(value, str):
        return MODEL_ID_ALIASES.get(value, value)
    return value


def normalize_pipeline_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema

    normalized = dict(schema)
    for model_field in ["vision_model", "refine_model"]:
        model_config = normalized.get(model_field)
        if isinstance(model_config, dict) and "default" in model_config:
            updated_config = dict(model_config)
            updated_config["default"] = normalize_model_id(
                updated_config.get("default")
            )
            normalized[model_field] = updated_config

    return normalized


def normalize_pipeline_settings(settings: Any) -> Dict[str, Any]:
    if not isinstance(settings, dict):
        return {}

    normalized = dict(settings)
    for model_field in ["vision_model", "refine_model"]:
        if model_field in normalized:
            normalized[model_field] = normalize_model_id(normalized.get(model_field))
    return normalized


def normalize_pipeline_list(pipeline_list: Any) -> List[Dict[str, Any]]:
    if not isinstance(pipeline_list, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for pipeline_entry in pipeline_list:
        if not isinstance(pipeline_entry, dict):
            continue

        updated = dict(pipeline_entry)
        if "schema" in updated:
            updated["schema"] = normalize_pipeline_schema(updated.get("schema"))
        normalized.append(updated)

    return normalized


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
                    mapping.synced_at = datetime.now(UTC).replace(tzinfo=None)
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
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", "8460"))
    uvicorn.run(app, host="0.0.0.0", port=port)
