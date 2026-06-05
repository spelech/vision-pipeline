import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, cast
import requests
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import database
from database import get_db, Item, ServiceMapping
from schemas import (
    ServiceOutputGenerateRequest,
    ServiceOutputGenerateResponse,
    ServicePreviewResponse,
    LocationsResponse,
    HealthResponse,
)
from services.registry import SERVICES
from app_helpers import (
    get_runtime_service_prompt_configs,
    generate_service_output,
    get_item_base_data,
    get_service_specific_item_data,
    get_service_context_from_item,
)

logger = logging.getLogger("VisionAPI.routes.service")
router = APIRouter(tags=["service"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/execute")
async def execute_services(data: Dict):  # pylint: disable=too-many-locals
    item_id = data.get("item_id")
    service_names = data.get("service_names", [])
    overrides = data.get("overrides", {})

    final_data = overrides
    image_path = None
    existing_mappings = {}
    item_obj: Optional[Item] = None

    async with database.async_session_local() as db:
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
            async with database.async_session_local() as db:
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


@router.post(
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


@router.get("/preview/{service_name}", response_model=ServicePreviewResponse)
async def get_service_preview(
    service_name: str,
    item_id: int,
) -> ServicePreviewResponse:
    if service_name not in SERVICES:
        return JSONResponse(
            status_code=404,
            content={"error": "Service not found"},
        )  # type: ignore

    async with database.async_session_local() as db:
        res = await db.execute(select(Item).where(Item.id == item_id))
        item = res.scalar_one_or_none()
        if not item:
            return JSONResponse(
                status_code=404,
                content={"error": "Item not found"},
            )  # type: ignore

        data = get_service_specific_item_data(item, service_name)

    payload = SERVICES[service_name].get_payload(data)
    return ServicePreviewResponse(service=service_name, payload=payload)


@router.get("/locations", response_model=LocationsResponse)
async def get_locations() -> LocationsResponse:
    try:
        homebox = SERVICES["homebox"]
        if not hasattr(homebox, "get_headers") or not hasattr(homebox, "api_url"):
            return LocationsResponse(
                success=False,
                error="Homebox service misconfigured",
            )

        headers = homebox.get_headers()  # type: ignore
        if not headers:
            return LocationsResponse(success=False, error="No API Key")
        resp = requests.get(
            f"{homebox.api_url}/locations",
            headers=headers,
            timeout=5,
        )  # type: ignore
        return LocationsResponse(success=True, locations=resp.json())
    except requests.RequestException as e:
        return LocationsResponse(success=False, error=str(e))
