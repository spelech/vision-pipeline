import asyncio
import io
import json
import logging
import os
import uuid
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import requests
from PIL import Image, ImageOps
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import database
from database import get_db, Item, Batch, ServiceMapping
from schemas import (
    SearchResponse,
    ItemSearchInfo,
    ServiceMappingInfo,
    SessionLogsResponse,
)
from services.registry import SERVICES
from logger import session_logger
from app_helpers import (
    get_runtime_service_prompt_configs,
    get_pipeline,
    generate_service_output,
)
from image_utils import (
    build_review_image_data_uri,
    encode_image_bytes_to_data_uri,
)
from tasks import process_item_task_safe
from routes.service_routes import execute_services

logger = logging.getLogger("VisionAPI.routes.item")
router = APIRouter(tags=["item"])


@router.get("/queue")
async def get_queue(
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Item)
    if status != "all":
        stmt = stmt.where(Item.status == status)
    result = await db.execute(stmt.order_by(Item.created_at.desc()))
    items = result.scalars().all()
    return {"items": items}


@router.get("/items/{item_id}")
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Item).where(Item.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/items/{item_id}/update")
async def update_item_data(
    item_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    query = update(Item).where(Item.id == item_id).values(**data)
    await db.execute(query)
    await db.commit()
    return {"success": True}


@router.post("/items/{item_id}/rerun")
async def rerun_item(
    item_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(update(Item).where(Item.id == item_id).values(status="processing"))
    await db.commit()
    background_tasks.add_task(process_item_task_safe, item_id, "default", "{}")
    return {"success": True}


@router.delete("/items/{item_id}")
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if item:
        stored_paths = (
            getattr(item, "image_path", None),
            getattr(item, "raw_image_path", None),
        )
        for stored_path in stored_paths:
            if (
                not isinstance(stored_path, str)
                or not stored_path
                or stored_path.startswith("data:")
            ):
                continue

            candidate_path = Path("data/uploads") / Path(stored_path).name
            with suppress(FileNotFoundError):
                candidate_path.unlink()

        await db.delete(item)
        await db.commit()
    return {"success": True}


@router.post("/bulk-approve")
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


@router.post("/identify")
async def identify(
    file: UploadFile = File(...),
    text: Optional[str] = Form(None),
    rotation: int = Form(0),
    mirror: bool = Form(False),
    session_id: str = Form(None),
    pipeline_id: str = Form("default"),
    settings: str = Form("{}"),
    lasso_polygon: str = Form(None),
):
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-statements
    try:
        pipeline_settings = json.loads(settings)
    except json.JSONDecodeError:
        pipeline_settings = {}

    sid = session_id or f"ident-{uuid.uuid4()}"
    session_logger.start_session(sid)

    def log_it(msg):
        session_logger.log(sid, msg)

    log_it("🚀 Ingesting image for identification...")
    try:
        content = await file.read()
        img = Image.open(io.BytesIO(content))

        if rotation != 0:
            log_it(f"🔄 Rotating image by {rotation} degrees...")
            img = img.rotate(-rotation, expand=True)  # type: ignore
        if mirror:
            log_it("🪞 Mirroring image horizontally...")
            img = ImageOps.mirror(img)  # type: ignore

        img = ImageOps.exif_transpose(img)  # type: ignore

        review_image_data_uri = build_review_image_data_uri(img)
        raw_image_data_uri = encode_image_bytes_to_data_uri(content, mime=file.content_type or "image/jpeg")

        lasso_points = None
        if lasso_polygon and lasso_polygon.strip():
            with suppress(json.JSONDecodeError):
                lasso_points = json.loads(lasso_polygon)

        log_it("🧠 Querying vision pipeline...")
        has_db_pipeline = pipeline_id.startswith("custom_") or pipeline_id.startswith("service_")
        core_pipeline = get_pipeline(pipeline_id, db_pipeline_exists=has_db_pipeline)

        results = await run_in_threadpool(
            core_pipeline.run,
            img,
            text,
            pipeline_settings,
            log_it,
        )
        if text:
            results["helper_text"] = text

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

        async with database.async_session_local() as db:
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


@router.post("/batch-upload")
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


@router.post("/share-target")
async def share_target(
    background_tasks: BackgroundTasks,
    images: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db)
):
    new_batch = Batch(description="Shared from device")
    db.add(new_batch)
    await db.commit()
    await db.refresh(new_batch)

    for file in images:
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
            new_item.id), "default", "{}")  # type: ignore

    return RedirectResponse(url=f"/?shared_batch_id={new_batch.id}", status_code=303)


@router.get("/search", response_model=SearchResponse)
async def search_items(
    query: str,
    db: AsyncSession = Depends(get_db)
) -> SearchResponse:
    # pylint: disable=too-many-locals
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
            id=str(item.id),
            status=str(item.status),
            image_path=str(item.image_path),
            raw_image_path=str(item.raw_image_path) if item.raw_image_path else None,
            product_type=str(item.product_type) if item.product_type else "product",
            ai_output=ai_output,
            user_overrides=user_overrides,
            product_name=merged_data.get("product_name") if isinstance(
                merged_data, dict) else None,
            brand=merged_data.get("brand") if isinstance(
                merged_data, dict) else None,
            created_at=cast(datetime, item.created_at),
            mappings=[
                ServiceMappingInfo(
                    service=str(m.service_name),
                    external_id=str(m.external_id),
                    url=str(m.external_url) if m.external_url else None,
                )
                for m in mappings
            ],
        )
        res.append(item_data)
    return SearchResponse(items=res)


@router.get("/logs/{session_id}", response_model=SessionLogsResponse)
async def get_session_logs(
    session_id: str,
    db: AsyncSession = Depends(get_db)
) -> SessionLogsResponse:
    logs = session_logger.get_logs(session_id)
    if logs:
        return SessionLogsResponse(logs=[{"message": log} for log in logs])

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
