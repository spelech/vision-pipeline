import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, ModelCatalog
from schemas import ModelListResponse, ModelInfo
from app_helpers import ensure_model_catalog, infer_model_provider, get_config_setting
from secrets_manager import get_secret_value, refresh_secrets_from_db
from llm_client import fetch_models_from_gateway

logger = logging.getLogger("VisionAPI.routes.model")
router = APIRouter(prefix="/models", tags=["models"])

class SyncRequest(BaseModel):
    llm_provider: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None

@router.get("", response_model=ModelListResponse)
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
                owned_by=str(row.owned_by) if hasattr(row, "owned_by") else None,
                mode=str(row.mode) if hasattr(row, "mode") else None,
                is_system=bool(row.is_system),
                source_gateway=str(row.source_gateway) if hasattr(row, "source_gateway") else None,
            )
            for row in rows
        ]
        return ModelListResponse(success=True, models=models)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing model catalog: %s", e)
        return ModelListResponse(success=False, models=[])

@router.post("/sync", response_model=ModelListResponse)
async def sync_models(
    request: Optional[SyncRequest] = None,
    db: AsyncSession = Depends(get_db)
) -> ModelListResponse:
    try:
        await refresh_secrets_from_db(db)
    except Exception as e:
        logger.warning("Could not refresh secrets from DB: %s", e)

    try:
        # 1. Determine provider & credentials
        # Priority: request payload > app_settings DB > fallback to secrets_manager (env/secrets table)
        
        provider = (request.llm_provider if request else None) or \
                   await get_config_setting(db, "llm_provider") or \
                   "litellm"
        
        # Create a temporary secret getter that prioritizes the request
        def sync_secret_getter(key: str) -> str:
            if request:
                if key == "LLM_BASE_URL" and request.LLM_BASE_URL:
                    return request.LLM_BASE_URL
                if key == "LLM_API_KEY" and request.LLM_API_KEY:
                    return request.LLM_API_KEY
            return get_secret_value(key)

        # Fetch models from the gateway
        gateway_models = await fetch_models_from_gateway(sync_secret_getter)
        
        if not gateway_models:
            return ModelListResponse(success=False, models=[], error="No models found on gateway")
            
        # Get existing models to update them if they already exist
        result = await db.execute(select(ModelCatalog))
        existing_models = {row.model_id: row for row in result.scalars().all()}
        
        created_count = 0
        updated_count = 0
        
        source_label = provider # e.g. "litellm", "openrouter", "ollama"
        
        for m in gateway_models:
            m_id = m.get("id")
            if not m_id:
                continue
                
            info = m.get("model_info", {})
            provider_name = str(info.get("owned_by") or infer_model_provider(m_id))
            owned_by = str(info.get("owned_by") or "")
            mode = str(info.get("mode") or "")
            
            if m_id in existing_models:
                # Update existing model
                row = existing_models[m_id]
                
                # Update source_gateway as a comma-separated list
                current_gateways = [g.strip() for g in (row.source_gateway or "").split(",") if g.strip()]
                if source_label not in current_gateways:
                    current_gateways.append(source_label)
                    row.source_gateway = ",".join(current_gateways)
                    updated_count += 1
                
                # Optionally update other fields if they are missing or system models
                if not row.owned_by and owned_by:
                    row.owned_by = owned_by
                if not row.mode and mode:
                    row.mode = mode
            else:
                # Add new model
                db.add(ModelCatalog(
                    model_id=m_id,
                    name=m_id.split("/")[-1],
                    provider=provider_name,
                    owned_by=owned_by,
                    mode=mode,
                    is_active=True,
                    is_system=False,
                    source_gateway=source_label
                ))
                created_count += 1
        
        if created_count > 0 or updated_count > 0:
            await db.commit()
            
        logger.info("Sync complete. Created: %d, Updated: %d", created_count, updated_count)
        
        # Return the updated list
        return await list_models(db)
    except Exception as e:
        logger.error("Error syncing models: %s", e)
        return ModelListResponse(success=False, models=[], error=str(e))
