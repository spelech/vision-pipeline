import logging
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, ModelCatalog
from schemas import ModelListResponse, ModelInfo
from app_helpers import ensure_model_catalog

logger = logging.getLogger("VisionAPI.routes.model")
router = APIRouter(prefix="/models", tags=["models"])


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
            )
            for row in rows
        ]
        return ModelListResponse(success=True, models=models)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing model catalog: %s", e)
        return ModelListResponse(success=False, models=[])

from llm_client import fetch_models_from_gateway
from secrets_manager import get_secret_value

@router.post("/sync", response_model=ModelListResponse)
async def sync_models(db: AsyncSession = Depends(get_db)) -> ModelListResponse:
    try:
        from secrets_manager import refresh_secrets_from_db
        await refresh_secrets_from_db(db)
    except Exception: pass
    try:
        # Fetch models from the gateway
        gateway_models = await fetch_models_from_gateway(get_secret_value)
        
        if not gateway_models:
            return ModelListResponse(success=False, models=[], error="No models found on gateway")
            
        # Get existing IDs to avoid duplicates
        result = await db.execute(select(ModelCatalog.model_id))
        existing_ids = {str(item[0]) for item in result.all()}
        
        created_count = 0
        for m in gateway_models:
            m_id = m.get("id")
            if m_id and m_id not in existing_ids:
                # Parse metadata from LiteLLM model_info if available
                info = m.get("model_info", {})
                db.add(ModelCatalog(
                    model_id=m_id,
                    name=m_id.split("/")[-1],
                    provider=str(info.get("owned_by") or infer_model_provider(m_id)),
                    owned_by=str(info.get("owned_by") or ""),
                    mode=str(info.get("mode") or ""),
                    is_active=True,
                    is_system=False
                ))
                created_count += 1
                existing_ids.add(m_id)
        
        if created_count > 0:
            await db.commit()
            
        # Return the updated list
        return await list_models(db)
    except Exception as e:
        logger.error("Error syncing models: %s", e)
        return ModelListResponse(success=False, models=[], error=str(e))
