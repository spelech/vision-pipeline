import logging
import json
import uuid
from typing import Any, Dict, List, Optional, cast
from urllib.parse import urlparse

# pylint: disable=line-too-long,too-many-locals

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from database import AppSetting

import database
from database import (
    AppSetting,
    ModelCatalog,
    PipelineDefinition,
)
from pipelines import ComposablePipeline, DefaultPipeline, PIPELINE_REGISTRY, get_all_pipelines
import pipelines
from pipelines.nodes import data_refine

logger = logging.getLogger("VisionAPI")

MODEL_ID_ALIASES: Dict[str, str] = {
    "qwen/qwen2.5-72b-instruct": "qwen/qwen3-235b-a22b-2507",
    "qwen/qwen2.5-32b-instruct": "qwen/qwen3-235b-a22b-2507",
}

SERVICE_NAMES = ["homebox", "mealie", "pricebuddy", "changedetection"]
DB_SETTING_KEYS = [
    "llm_provider",
    "prompt_templates",
    "service_prompts",
    "model_favorites",
    "starred_models",
    "image_optimization",
    "gmail_auto_sync_enabled",
    "gmail_poll_interval_minutes",
    "gmail_auto_sync_query",
    "gmail_auto_sync_max_results",
]

DEFAULT_MODEL_CATALOG: List[Dict[str, str]] = [
    {
        "id": "qwen3-vl-235b-a22b-instruct",
        "name": "Qwen 3 VL 235B (OpenRouter)",
        "provider": "openrouter",
        "source_gateway": "openrouter",
    },
    {
        "id": "qwen3-235b-a22b-2507",
        "name": "Qwen 3 235B (OpenRouter)",
        "provider": "openrouter",
        "source_gateway": "openrouter",
    },
]


def normalize_prompt_templates(value: Any) -> List[Dict[str, str]]:
    if isinstance(value, list):
        normalized = []
        for template in value:
            if isinstance(template, dict):
                normalized.append(
                    {
                        "id": str(template.get("id", uuid.uuid4())),
                        "name": str(template.get("name", "Untitled Template")),
                        "prompt": str(template.get("prompt", "")),
                    }
                )
        return normalized

    if isinstance(value, dict):
        normalized = []
        for key, prompt in value.items():
            if isinstance(prompt, dict):
                normalized.append(
                    {
                        "id": str(prompt.get("id", key)),
                        "name": str(prompt.get("name", key.replace("_", " ").title())),
                        "prompt": str(prompt.get("prompt", "")),
                    }
                )
            else:
                normalized.append(
                    {
                        "id": str(key),
                        "name": key.replace("_", " ").title(),
                        "prompt": str(prompt),
                    }
                )
        return normalized

    return []


def derive_prompt_templates_from_pipelines(pipeline_entries: Any) -> List[Dict[str, str]]:
    if not isinstance(pipeline_entries, list):
        return []

    templates: List[Dict[str, str]] = []
    for pipeline in pipeline_entries:
        if not isinstance(pipeline, dict):
            continue

        pipeline_id = str(pipeline.get("id", "")).strip()
        pipeline_name = str(pipeline.get("name", pipeline_id or "Pipeline")).strip()
        schema = pipeline.get("schema")
        if not isinstance(schema, dict):
            continue

        for key, definition in schema.items():
            if "prompt" not in str(key).lower():
                continue
            prompt_default = ""
            if isinstance(definition, dict):
                raw_default = definition.get("default")
                if isinstance(raw_default, str):
                    prompt_default = raw_default

            templates.append(
                {
                    "id": f"{pipeline_id}-{key}" if pipeline_id else str(key),
                    "name": f"{pipeline_name} {str(key).replace('_', ' ')}".strip(),
                    "prompt": prompt_default,
                }
            )

    return templates


def merge_unique_str_lists(*values: Any) -> List[str]:
    merged: List[str] = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item and item not in merged:
                    merged.append(item)
    return merged


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


def normalize_model_id(value: Any) -> Any:
    if isinstance(value, str):
        return MODEL_ID_ALIASES.get(value, value)
    return value.get("value") if isinstance(value, dict) and "value" in value else value


def normalize_pipeline_schema(schema: Any) -> Any:
    if not isinstance(schema, dict):
        return schema

    normalized = dict(schema)
    for model_field in ["vision_model", "refine_model"]:
        model_config = normalized.get(model_field)
        if isinstance(model_config, dict) and "default" in model_config:
            updated_config = dict(model_config)
            updated_config["default"] = normalize_model_id(updated_config.get("default"))
            normalized[model_field] = updated_config

    return normalized


def normalize_pipeline_settings(settings: Any) -> Dict[str, Any]:
    if not isinstance(settings, dict):
        return {}

    normalized = dict(settings)
    for model_field in ["vision_model", "refine_model"]:
        if model_field in normalized:
            normalized[model_field] = normalize_model_id(normalized.get(model_field))

    if "search_results_limit" in normalized:
        raw_search_limit = normalized.get("search_results_limit")
        try:
            search_limit = int(raw_search_limit if raw_search_limit is not None else 7)
        except (TypeError, ValueError):
            search_limit = 7
        normalized["search_results_limit"] = max(1, min(search_limit, 50))
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
    owner = model_id.split("/", 1)[0].strip().lower() if "/" in model_id else model_id.strip().lower()
    if not owner:
        return "custom"
    if owner in {"google", "qwen", "anthropic", "openai", "meta", "mistralai", "x-ai", "deepseek"}:
        return "openrouter"
    return owner


def default_service_prompt_configs() -> Dict[str, Dict[str, Any]]:
    return {
        "homebox": {
            "service": "homebox",
            "model": None,
            "enabled": True,
            "prompt": (
                "You are an expert inventory cataloging assistant. Create a Homebox-ready JSON object from the provided product data and search/scrape context.\n"
                "Extract or infer the following keys:\n"
                "- product_name: The descriptive, clean name of the product.\n"
                "- brand: The manufacturer or brand name.\n"
                "- model_number: Specific model/part number if visible in the context or description.\n"
                "- serial_number: Serial number if specified by the user or visible.\n"
                "- category: The product category tag (e.g., Electronics, Tools, Kitchenware, Pantry).\n"
                "- description: A short, high-quality description of what the product is.\n"
                "- location: A logical storage location in a home environment (e.g., Garage, Pantry, Kitchen, closet, workbench, tool cabinet, laundry room) inferred from the product type and user notes.\n"
                "- quantity: Default to 1, or parse from user notes.\n"
                "- purchase_price: Inferred purchase price or MSRP as a decimal number (no currency signs).\n"
                "- notes: Additional context, including where it was bought or user instructions.\n"
                "- technical_details: A string or JSON block of detailed specs, dimensions, power requirements, etc.\n\n"
                "Return a valid JSON object with these exact keys, using null or defaults if unknown. Do not include markdown code block formatting, return raw JSON text only."
            ),
            "feedback_enabled": False,
        },
        "mealie": {
            "service": "mealie",
            "model": None,
            "enabled": True,
            "prompt": (
                "You are an expert culinary assistant. Create a Mealie-ready recipe JSON object from the provided food/recipe data and search/scrape context.\n"
                "Extract the following keys:\n"
                "- product_name: The name of the dish or recipe.\n"
                "- description: A brief summary of the recipe or food item.\n"
                "- recipe_ingredients_raw: A string containing the list of ingredients, with one ingredient per line.\n"
                "- recipe_instructions_raw: A string containing step-by-step cooking instructions, with one step/instruction per line.\n"
                "- yield: The number of servings or yield quantity (e.g., '4 servings', '1 loaf').\n\n"
                "Return a valid JSON object with these exact keys, using null or defaults if unknown. Do not include markdown code block formatting, return raw JSON text only."
            ),
            "feedback_enabled": False,
        },
        "pricebuddy": {
            "service": "pricebuddy",
            "model": None,
            "enabled": True,
            "prompt": (
                "You are a price comparison and tracking assistant. Create a PriceBuddy-ready JSON object from the provided data and search/scrape context.\n"
                "Extract or locate the following keys:\n"
                "- product_name: The clean name of the product.\n"
                "- barcode: UPC/EAN barcode string if available.\n"
                "- category: Product category tag (e.g., Groceries, Electronics).\n"
                "- product_url: The official or main retailer product page URL (e.g., Amazon, Walmart, Target, Home Depot).\n"
                "- monitor_urls: A list of alternative retailer product page URLs for the exact same item.\n"
                "- target_price: The target price to track or current lowest price found, as a decimal number or string.\n"
                "- currency: The ISO currency code (e.g., 'USD', 'EUR').\n"
                "- retailer: The name of the primary retailer.\n\n"
                "Prefer direct retailer product pages over blogs, news sites, or general directories. "
                "Return a valid JSON object with these exact keys, using null or defaults if unknown. Do not include markdown code block formatting, return raw JSON text only."
            ),
            "feedback_enabled": True,
            "feedback_prompt": (
                "You are revising the PriceBuddy tracking JSON. Review the initial output and the search/scrape context.\n"
                "Ensure that:\n"
                "- product_url is a high-quality primary retailer link.\n"
                "- monitor_urls contains valid, alternative retailer links for the exact same product.\n"
                "- target_price, currency, and retailer are correctly populated based on candidates.\n"
                "Return a valid JSON object with the final updated keys. Do not include markdown code block formatting, return raw JSON text only."
            ),
        },
        "changedetection": {
            "service": "changedetection",
            "model": None,
            "enabled": True,
            "prompt": (
                "You are an automated price and page monitoring assistant. Create a ChangeDetection-ready JSON object from the provided data and search/scrape context.\n"
                "Extract the following keys:\n"
                "- product_name: The clean name of the product.\n"
                "- product_url: The primary product URL to monitor for price/stock changes.\n"
                "- category: Tag or category name for grouping the watch (e.g., Electronics, Grocery).\n"
                "- check_every_hours: The check frequency as an integer (e.g., 12, 24).\n"
                "- fetch_backend: Set to 'html_requests' or 'playwright'. Use 'playwright' if the target retailer uses heavy JavaScript (e.g. Amazon, BestBuy), else 'html_requests'.\n"
                "- monitor_urls: A list of alternative retailer URLs to monitor for the same product.\n\n"
                "Return a valid JSON object with these exact keys. Do not include markdown code block formatting, return raw JSON text only."
            ),
            "feedback_enabled": True,
            "feedback_prompt": (
                "You are revising the ChangeDetection monitoring JSON. Review the initial output and the search/scrape context.\n"
                "Refine the product_url, check_every_hours, and fetch_backend settings. Ensure fetch_backend is set to 'playwright' for sites with heavy JavaScript.\n"
                "Ensure monitor_urls lists additional high-quality product pages from alternative retailers.\n"
                "Return a valid JSON object with the final updated keys. Do not include markdown code block formatting, return raw JSON text only."
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


def normalize_app_setting(key: str, value: Any) -> Any:
    if key == "prompt_templates":
        return normalize_prompt_templates(value)
    if key == "service_prompts":
        return normalize_service_prompts(value)
    return value.get("value") if isinstance(value, dict) and "value" in value else value


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
                source_gateway=str(model.get("source_gateway") or "litellm"),
                is_system=True,
            )
        )
        created = True

    if created:
        await db.commit()


async def ensure_app_settings_seed(db: AsyncSession) -> None:
    existing = await get_app_settings(db)
    
    defaults: Dict[str, Any] = {
        "prompt_templates": [],
        "service_prompts": default_service_prompt_configs(),
        "model_favorites": [],
        "starred_models": [],
        "image_optimization": {},
        "gmail_auto_sync_enabled": False,
        "gmail_poll_interval_minutes": 30,
        "gmail_auto_sync_query": (
            'has:attachment (subject:receipt OR subject:"order confirmation" OR subject:invoice)'
        ),
        "gmail_auto_sync_max_results": 25,
    }

    # Smart Prompt Migration logic
    changed = False

    # 1. System Prompts (service_prompts)
    db_service_prompts = normalize_service_prompts(existing.get("service_prompts", {}))
    default_service_prompts = defaults["service_prompts"]
    
    final_service_prompts = dict(db_service_prompts)
    
    for service_id, default_cfg in default_service_prompts.items():
        if service_id not in db_service_prompts:
            final_service_prompts[service_id] = default_cfg
            changed = True
            continue
            
        db_cfg = db_service_prompts[service_id]
        # Compare prompts
        db_prompt = str(db_cfg.get("prompt", "")).strip()
        def_prompt = str(default_cfg.get("prompt", "")).strip()
        
        if db_prompt != def_prompt and def_prompt:
            logger.info("System prompt for %s has changed in codebase. Preserving user version.", service_id)
            # Create a backup ID for the user's custom prompt
            custom_id = f"{service_id}_custom"
            
            # Save user prompt as a regular prompt template (since service_prompts are fixed keys)
            # Or just let them keep it as f"{service_id}_custom" if we had a registry.
            # Decision: Add to prompt_templates as a backup.
            user_prompt_template = {
                "id": custom_id,
                "name": f"Legacy {service_id.title()} Prompt (User)",
                "prompt": db_prompt
            }
            
            # Add to prompt_templates if not already there
            current_templates = normalize_prompt_templates(existing.get("prompt_templates", []))
            if not any(t["id"] == custom_id for t in current_templates):
                current_templates.append(user_prompt_template)
                await upsert_app_setting(db, "prompt_templates", current_templates)
                existing["prompt_templates"] = current_templates # Update local cache
            
            # Update any custom pipelines that were using this service (if they explicitly refer to it)
            # Note: custom pipelines usually have their own prompt fields in schema, 
            # but they might reference system prompts in some future implementation.
            # For now, we update the service prompt to the new default.
            final_service_prompts[service_id] = default_cfg
            changed = True

    if changed:
        await upsert_app_setting(db, "service_prompts", final_service_prompts)
        existing["service_prompts"] = final_service_prompts

    # 2. General Settings Seed
    for key in DB_SETTING_KEYS:
        if key in existing:
            continue
        await upsert_app_setting(db, key, defaults.get(key))

    # 3. Model Favorites Sync
    model_ids: set[str] = set()
    catalog_result = await db.execute(select(ModelCatalog.model_id))
    for item in catalog_result.all():
        model_ids.add(str(item[0]))
    
    db_favorites = set(merge_unique_str_lists(existing.get("model_favorites", [])))
    if not model_ids.issubset(db_favorites):
        await upsert_app_setting(db, "model_favorites", list(model_ids | db_favorites))

    await db.commit()


async def get_runtime_service_prompt_configs() -> Dict[str, Dict[str, Any]]:
    async with database.async_session_local() as db:
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)
        return merge_service_prompt_configs(settings.get("service_prompts"))


async def ensure_pipeline_catalog(db: AsyncSession) -> None:
    try:
        registry_entries = normalize_pipeline_list(pipelines.get_all_pipelines())
        result = await db.execute(select(PipelineDefinition))
        existing_rows = {str(row.pipeline_id): row for row in result.scalars().all()}

        changed = False
        for entry in registry_entries:
            pipeline_id = str(entry.get("id", "")).strip()
            if not pipeline_id:
                continue

            name = str(entry.get("name", pipeline_id))
            schema = normalize_pipeline_schema(entry.get("schema") or {})
            service_target = _service_target_for_pipeline_id(pipeline_id)

            if pipeline_id in existing_rows:
                row = existing_rows[pipeline_id]
                if not row.is_system:
                    continue  # Don't touch user-created pipelines with same ID (unlikely)

                # Force sync system pipelines
                if (row.name != name or
                        row.schema != schema or
                        row.service_target != service_target):
                    row.name = name  # type: ignore
                    row.schema = schema
                    row.service_target = service_target  # type: ignore
                    changed = True
            else:
                db.add(
                    PipelineDefinition(
                        pipeline_id=pipeline_id,
                        name=name,
                        schema=schema,
                        is_system=True,
                        is_editable=True,
                        service_target=service_target,
                    )
                )
                changed = True

        if changed:
            await db.commit()
    except SQLAlchemyError:
        logger.warning("Skipping pipeline catalog sync because DB is unavailable")


async def pipeline_definition_exists(db: AsyncSession, pipeline_id: str) -> bool:
    try:
        result = await db.execute(select(PipelineDefinition.id).where(PipelineDefinition.pipeline_id == pipeline_id))
        return result.first() is not None
    except SQLAlchemyError:
        return False


async def list_pipeline_definitions(db: AsyncSession, include_system: bool = True) -> List[Dict[str, Any]]:
    stmt = select(PipelineDefinition)
    if not include_system:
        stmt = stmt.where(PipelineDefinition.is_system.is_(False))

    try:
        result = await db.execute(stmt.order_by(PipelineDefinition.is_system.desc(), PipelineDefinition.pipeline_id.asc()))
        rows = result.scalars().all()
        return [_pipeline_row_to_dict(row) for row in rows]
    except SQLAlchemyError:
        return []


async def persist_custom_pipelines(db: AsyncSession, custom_pipelines: List[Dict[str, Any]]) -> None:
    existing_result = await db.execute(select(PipelineDefinition).where(PipelineDefinition.is_system.is_(False)))
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


def _extract_terms(value: Any) -> List[str]:
    if not isinstance(value, str):
        return []
    return [part.strip().lower() for part in value.split() if len(part.strip()) >= 3]


def extract_search_candidates(search_results: Any, base_data: Dict[str, Any]) -> List[Dict[str, Any]]:
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
    product_terms = _extract_terms(str(base_data.get("product_name") or base_data.get("name") or ""))

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

    candidates.sort(key=lambda item: (int(item.get("score", 0)), bool(item.get("is_retailer"))), reverse=True)
    return candidates


def build_service_feedback_context(service_name: str, base_data: Dict[str, Any], context_data: Dict[str, Any]) -> Dict[str, Any]:
    search_candidates = extract_search_candidates(context_data.get("search"), base_data)
    candidate_urls = [item["url"] for item in search_candidates if isinstance(item.get("url"), str)]
    retailer_urls = [
        item["url"] for item in search_candidates if item.get("is_retailer") and isinstance(item.get("url"), str)
    ]

    required_fields: List[str]
    if service_name == "changedetection":
        required_fields = ["product_name", "product_url", "monitor_urls", "change_monitoring_notes"]
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
                str(url).strip() for url in existing_monitor_urls if isinstance(url, str) and str(url).strip()
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
        feedback_template_text = feedback_template or "Revise JSON output using candidate URLs and service constraints."
        feedback_prompt = (
            f"{feedback_template_text}\n"
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
        base_with_overrides = dict(user_overrides)
        ai_output_for_receipt: Dict[str, Any] = (
            cast(Dict[str, Any], item.ai_output)
            if isinstance(item.ai_output, dict)
            else {}
        )
        for key in (
            "receipt_attachment_data_uri",
            "receipt_image_data_uri",
            "receipt_filename",
            "source_receipt_id",
            "helper_text",
            "barcode",
        ):
            value = ai_output_for_receipt.get(key)
            if isinstance(value, str) and value.strip():
                base_with_overrides[key] = value
        return base_with_overrides

    ai_output: Dict[str, Any] = cast(Dict[str, Any], item.ai_output) if isinstance(item.ai_output, dict) else {}
    llm_output_raw = ai_output.get("llm_output")
    llm_output: Dict[str, Any] = llm_output_raw if isinstance(llm_output_raw, dict) else {}
    base_data: Dict[str, Any] = dict(llm_output.items())
    if isinstance(ai_output.get("searxng_results"), list):
        base_data["searxng_results"] = ai_output.get("searxng_results")
    if isinstance(ai_output.get("scraped_content"), str):
        base_data["scraped_content"] = ai_output.get("scraped_content")
    for key in (
        "receipt_attachment_data_uri",
        "receipt_image_data_uri",
        "receipt_filename",
        "source_receipt_id",
        "helper_text",
        "barcode",
    ):
        value = ai_output.get(key)
        if isinstance(value, str) and value.strip():
            base_data[key] = value
    return base_data


def get_service_specific_item_data(item: Any, service_name: str) -> Dict[str, Any]:
    base_data = get_item_base_data(item)
    ai_output: Dict[str, Any] = cast(Dict[str, Any], item.ai_output) if isinstance(item.ai_output, dict) else {}
    service_outputs_raw = ai_output.get("service_outputs")
    service_outputs: Dict[str, Any] = service_outputs_raw if isinstance(service_outputs_raw, dict) else {}
    service_output_entry_raw = service_outputs.get(service_name)
    service_output_entry: Dict[str, Any] = service_output_entry_raw if isinstance(service_output_entry_raw, dict) else {}
    service_data_raw = service_output_entry.get("data")
    service_data: Dict[str, Any] = service_data_raw if isinstance(service_data_raw, dict) else {}
    return {**base_data, **service_data}


def get_service_context_from_item(item: Any, service_name: str) -> Dict[str, Any]:
    ai_output: Dict[str, Any] = cast(Dict[str, Any], item.ai_output) if isinstance(item.ai_output, dict) else {}
    service_enrichments_raw = ai_output.get("service_enrichments")
    service_enrichments: Dict[str, Any] = service_enrichments_raw if isinstance(service_enrichments_raw, dict) else {}
    return {
        "search": ai_output.get("searxng_results", []),
        "scrape": ai_output.get("scraped_content"),
        "service_enrichment": service_enrichments.get(service_name, {}),
    }

async def get_config_setting(db: AsyncSession, key: str, default: Any = None) -> Any:
    """
    Retrieves a single configuration setting from the app_settings table.
    """
    try:
        from database import AppSetting
        result = await db.execute(select(AppSetting.value).where(AppSetting.key == key))
        val = result.scalar_one_or_none()
        if val is None:
            return default
        return val.get("value") if isinstance(val, dict) and "value" in val else val
    except Exception:
        return default
