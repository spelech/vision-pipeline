import logging
from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import pipelines
from database import get_db, PipelineDefinition
from schemas import PipelineListResponse
from app_helpers import (
    ensure_pipeline_catalog,
    list_pipeline_definitions,
    normalize_pipeline_list,
    normalize_pipeline_schema,
    _service_target_for_pipeline_id,
)

logger = logging.getLogger("VisionAPI.routes.pipeline")
router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.get("", response_model=PipelineListResponse)
async def list_pipelines(db: AsyncSession = Depends(get_db)) -> PipelineListResponse:
    try:
        await ensure_pipeline_catalog(db)
        all_pipelines = await list_pipeline_definitions(db, include_system=True)
        if not all_pipelines:
            all_pipelines = normalize_pipeline_list(pipelines.get_all_pipelines())
        return PipelineListResponse(success=True, pipelines=all_pipelines)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing DB pipelines: %s", e)
        fallback = normalize_pipeline_list(pipelines.get_all_pipelines())
        return PipelineListResponse(
            success=bool(fallback),
            pipelines=fallback,
            error=str(e),
        )


@router.put("/{pipeline_id}")
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


@router.delete("/{pipeline_id}")
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
