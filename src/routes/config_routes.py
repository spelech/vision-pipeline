import os
import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import pipelines
from database import get_db, ConfigSecret, ModelCatalog
from schemas import ConfigResponse, ConfigUpdateRequest
from services.discovery import DiscoveryResult, run_autodiscovery
from secrets_manager import (
    CONFIG_SECRET_KEYS,
    ORIGINAL_ENV,
    get_secret_value,
    decrypt_secret,
    upsert_secret,
)
from scheduler import (
    configure_gmail_auto_sync_scheduler,
    GMAIL_AUTO_SYNC_DEFAULT_QUERY,
    _parse_int_setting,
)
from app_helpers import (
    ensure_app_settings_seed,
    get_app_settings,
    normalize_prompt_templates,
    derive_prompt_templates_from_pipelines,
    merge_service_prompt_configs,
    merge_unique_str_lists,
    ensure_pipeline_catalog,
    list_pipeline_definitions,
    normalize_service_prompts,
    persist_custom_pipelines,
    upsert_app_setting,
    infer_model_provider,
    normalize_pipeline_list,
)

logger = logging.getLogger("VisionAPI.routes.config")
router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigResponse)
async def get_config(
    db: AsyncSession = Depends(get_db),
    reveal_secrets: bool = False,
) -> ConfigResponse:
    await ensure_app_settings_seed(db)
    from secrets_manager import refresh_secrets_from_db
    await refresh_secrets_from_db(db)
    settings = await get_app_settings(db)
    prompt_templates = normalize_prompt_templates(settings.get("prompt_templates"))
    if not prompt_templates:
        prompt_templates = derive_prompt_templates_from_pipelines(
            normalize_pipeline_list(pipelines.get_all_pipelines())
        )
    data: Dict[str, Any] = {
        "prompt_templates": prompt_templates,
        "service_prompts": merge_service_prompt_configs(settings.get("service_prompts")),
        "model_favorites": merge_unique_str_lists(settings.get("model_favorites")),
        "starred_models": merge_unique_str_lists(settings.get("starred_models")),
        "image_optimization": settings.get("image_optimization"),
        "gmail_auto_sync_enabled": bool(settings.get("gmail_auto_sync_enabled", False)),
        "gmail_poll_interval_minutes": _parse_int_setting(
            settings.get("gmail_poll_interval_minutes"),
            default=30,
            min_value=1,
            max_value=1440,
        ),
        "gmail_auto_sync_query": str(
            settings.get("gmail_auto_sync_query") or GMAIL_AUTO_SYNC_DEFAULT_QUERY
        ),
        "gmail_auto_sync_max_results": _parse_int_setting(
            settings.get("gmail_auto_sync_max_results"),
            default=25,
            min_value=1,
            max_value=100,
        ),
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
    res = await db.execute(select(ConfigSecret))
    db_secrets = {s.key for s in res.scalars().all() if s.encrypted_value}

    secrets_status = {}
    secrets_sources = {}
    for key in CONFIG_SECRET_KEYS:
        val = get_secret_value(key)
        if val:
            if reveal_secrets or "URL" in key or "MODEL" in key:
                secrets_status[key] = val
            else:
                secrets_status[key] = "********"
        else:
            secrets_status[key] = ""

        if key in db_secrets:
            secrets_sources[key] = "database"
        elif ORIGINAL_ENV.get(key):
            secrets_sources[key] = "environment"
        else:
            secrets_sources[key] = "none"

    return ConfigResponse(**data, secrets_status=secrets_status, secrets_sources=secrets_sources)


@router.post("")
async def update_config(
    data: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Updating config with payload: %s", data.model_dump(exclude_unset=True))
    # Separate secrets
    keys_to_persist = [
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
    from secrets_manager import refresh_secrets_from_db
    await refresh_secrets_from_db(db)
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
        if val == "":
            result = await db.execute(select(ConfigSecret).where(ConfigSecret.key == key))
            secret_obj = result.scalar_one_or_none()
            if secret_obj:
                await db.delete(secret_obj)
            orig_val = ORIGINAL_ENV.get(key)
            if orig_val:
                os.environ[key] = orig_val
            elif key in os.environ:
                del os.environ[key]
        elif val and val != "********":
            await upsert_secret(db, key, val)

    await db.commit()

    scheduler_setting_keys = {
        "gmail_auto_sync_enabled",
        "gmail_poll_interval_minutes",
        "gmail_auto_sync_query",
        "gmail_auto_sync_max_results",
    }
    if scheduler_setting_keys.intersection(data_dict.keys()):
        await configure_gmail_auto_sync_scheduler()

    return {"success": True}


@router.get("/export")
async def export_config(db: AsyncSession = Depends(get_db)):
    """Export all non-system configuration as a JSON file."""
    config_resp = await get_config(db)
    config_data = config_resp.model_dump()
    
    # Include the encrypted secrets so Import can restore them.
    res = await db.execute(select(ConfigSecret))
    secrets = res.scalars().all()
    config_data["encrypted_secrets"] = {s.key: s.encrypted_value for s in secrets}
    
    return config_data


@router.post("/import")
async def import_config(
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Import configuration from a JSON dump."""
    try:
        # 1. Update general settings
        keys_to_persist = [
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
        
        for key in keys_to_persist:
            if key in data:
                await upsert_app_setting(db, key, data[key])
        
        # 2. Update custom pipelines
        if "custom_pipelines" in data:
            normalized = normalize_pipeline_list(data["custom_pipelines"])
            await persist_custom_pipelines(db, normalized)
            
        # 3. Update secrets
        encrypted_secrets = data.get("encrypted_secrets", {})
        for key, enc_val in encrypted_secrets.items():
            if key in CONFIG_SECRET_KEYS:
                result = await db.execute(select(ConfigSecret).where(ConfigSecret.key == key))
                secret_obj = result.scalar_one_or_none()
                if secret_obj:
                    secret_obj.encrypted_value = enc_val  # type: ignore
                else:
                    db.add(ConfigSecret(key=key, encrypted_value=enc_val))
                
                try:
                    os.environ[key] = decrypt_secret(enc_val)
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

        await db.commit()
        
        await configure_gmail_auto_sync_scheduler()
        
        return {"success": True}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Import failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/discover", response_model=DiscoveryResult)
async def autodiscover_settings() -> DiscoveryResult:
    """Scan the network and local filesystem for settings and GWS credentials."""
    return await run_autodiscovery()
