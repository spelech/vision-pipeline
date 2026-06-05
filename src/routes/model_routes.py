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
                is_system=bool(row.is_system),
            )
            for row in rows
        ]
        return ModelListResponse(success=True, models=models)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing model catalog: %s", e)
        return ModelListResponse(success=False, models=[])
