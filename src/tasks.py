import asyncio
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests
from PIL import Image, ImageOps
from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

import database
from database import (
    Batch,
    Item,
)
from image_utils import (
    build_review_image_data_uri,
    build_seed_image_data_uri,
    decode_data_uri_to_bytes,
    encode_image_bytes_to_data_uri,
    item_source_image_data_uri,
)
from logger import session_logger
from services.registry import SERVICES
from app_helpers import (
    get_pipeline,
    get_runtime_service_prompt_configs,
    generate_service_output,
    get_item_base_data,
    get_service_specific_item_data,
    get_service_context_from_item,
)

logger = logging.getLogger("VisionAPI.tasks")


async def process_item_task(
    item_id: int,
    pipeline_id: str = "default",
    settings_str: str = "{}",
) -> None:
    # pylint: disable=too-many-locals,too-many-statements
    try:
        settings = json.loads(settings_str)
    except json.JSONDecodeError:
        settings = {}
    has_db_pipeline = pipeline_id.startswith("custom_") or pipeline_id.startswith("service_")
    core_pipeline = get_pipeline(pipeline_id, db_pipeline_exists=has_db_pipeline)
    async with database.async_session_local() as db:
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
        item_seed_text = ""
        if isinstance(item.ai_output, dict):
            item_seed_text = str(
                item.ai_output.get("receipt_seed_text")
                or item.ai_output.get("gmail_seed_text")
                or ""
            ).strip()
        combined_text = "\n".join(
            [part for part in [batch_text or "", item_seed_text] if part]
        ).strip()

        try:
            image_data_uri = item_source_image_data_uri(item)
            if not image_data_uri:
                raise ValueError("No image data found on item")

            image_bytes = decode_data_uri_to_bytes(image_data_uri)
            img = Image.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)  # type: ignore
            results = await run_in_threadpool(
                core_pipeline.run,
                img,
                combined_text or None,
                settings,
                log_it,
            )
            results["review_image_data_uri"] = build_review_image_data_uri(img)
            if combined_text:
                results["helper_text"] = combined_text

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
    settings_str: str = "{}",
) -> None:
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


async def ingest_receipt_jobs_direct(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    receipts_payload: List[Dict[str, Any]],
    pipeline_id: str,
    settings: Dict[str, Any],
    batch_name_prefix: str = "Receipts",
    batch_description: str = "Direct receipt ingestion",
) -> Dict[str, Any]:
    # pylint: disable=too-many-locals,too-many-statements,too-many-branches,too-many-arguments,too-many-positional-arguments
    if not receipts_payload:
        return {"batch_id": None, "created_items": 0, "receipt_count": 0}

    batch = Batch(
        name=f"{batch_name_prefix} {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        description=batch_description,
        status="processing",
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    fallback_seed_image_uri = build_seed_image_data_uri()
    settings_str = json.dumps(settings if isinstance(settings, dict) else {})
    created_items = 0

    for receipt in receipts_payload:
        source = str(receipt.get("source") or "receipt").strip() or "receipt"
        source_receipt_id = str(
            receipt.get("source_receipt_id")
            or receipt.get("receipt_id")
            or receipt.get("message_id")
            or ""
        ).strip()
        subject = str(receipt.get("subject") or "").strip()
        sender = str(receipt.get("sender") or receipt.get("from") or "").strip()
        snippet = str(receipt.get("snippet") or "").strip()
        receipt_filename = (
            str(receipt.get("receipt_filename") or "receipt.jpg").strip()
            or "receipt.jpg"
        )
        receipt_image_data_uri = str(receipt.get("image_data_uri") or "").strip()
        if not receipt_image_data_uri.startswith("data:image"):
            receipt_image_data_uri = ""

        line_items_raw = receipt.get("line_items")
        line_items: List[Any] = line_items_raw if isinstance(line_items_raw, list) else []
        if not line_items:
            fallback_name = subject or snippet or "Receipt Item"
            line_items = [{"name": fallback_name, "line_text": fallback_name, "price": None}]

        for line_item in line_items:
            if not isinstance(line_item, dict):
                continue

            item_name = (
                str(line_item.get("name") or "Receipt Item").strip()
                or "Receipt Item"
            )
            line_text_value = str(
                line_item.get("line_text") or line_item.get("description") or ""
            ).strip()
            price_value = str(line_item.get("price") or line_item.get("amount") or "").strip()
            barcode_value = str(line_item.get("barcode") or "").strip()
            quantity_raw = line_item.get("quantity")
            quantity = (
                int(quantity_raw)
                if isinstance(quantity_raw, int) and quantity_raw > 0
                else 1
            )

            seed_text = "\n".join(
                [
                    f"Source: {source}",
                    f"Receipt ID: {source_receipt_id}",
                    f"Subject: {subject}",
                    f"Sender: {sender}",
                    f"Snippet: {snippet}",
                    f"Line Item: {item_name}",
                    f"Line Text: {line_text_value}",
                    f"Price: {price_value}",
                    f"Barcode: {barcode_value}",
                ]
            ).strip()

            ai_seed: Dict[str, Any] = {
                "source": source,
                "source_receipt_id": source_receipt_id,
                "receipt_subject": subject,
                "receipt_sender": sender,
                "receipt_line_item": line_item,
                "receipt_seed_text": seed_text,
                "receipt_filename": receipt_filename,
            }
            if source == "gmail_direct":
                ai_seed["gmail_seed_text"] = seed_text
                ai_seed["gmail_message_id"] = source_receipt_id
                ai_seed["gmail_subject"] = subject
                ai_seed["gmail_sender"] = sender
            if receipt_image_data_uri:
                ai_seed["receipt_image_data_uri"] = receipt_image_data_uri
                ai_seed["receipt_attachment_data_uri"] = receipt_image_data_uri

            item = Item(
                batch_id=batch.id,
                image_path=receipt_image_data_uri or fallback_seed_image_uri,
                raw_image_path=receipt_image_data_uri or fallback_seed_image_uri,
                status="processing",
                ai_output=ai_seed,
                user_overrides={
                    "product_name": item_name,
                    "quantity": quantity,
                },
                product_type="product",
            )
            db.add(item)
            await db.commit()
            await db.refresh(item)
            background_tasks.add_task(
                process_item_task_safe,
                int(item.id),
                pipeline_id,
                settings_str,
            )
            created_items += 1

    await db.execute(
        update(Batch).where(Batch.id == batch.id).values(status="completed")
    )
    await db.commit()
    return {
        "batch_id": batch.id,
        "created_items": created_items,
        "receipt_count": len(receipts_payload),
    }


async def ingest_gmail_receipts_direct(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    receipts_payload: List[Dict[str, Any]],
    pipeline_id: str,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_payload: List[Dict[str, Any]] = []
    for entry in receipts_payload:
        if not isinstance(entry, dict):
            continue
        message_raw = entry.get("message")
        message: Dict[str, Any] = message_raw if isinstance(message_raw, dict) else {}
        normalized_payload.append(
            {
                "source": "gmail_direct",
                "source_receipt_id": str(message.get("message_id") or "").strip(),
                "subject": str(message.get("subject") or "").strip(),
                "sender": str(message.get("from") or "").strip(),
                "snippet": str(message.get("snippet") or "").strip(),
                "line_items": (
                    entry.get("line_items")
                    if isinstance(entry.get("line_items"), list)
                    else []
                ),
                "image_data_uri": str(entry.get("image_data_uri") or "").strip(),
                "receipt_filename": (
                    str(entry.get("receipt_filename") or "receipt.jpg").strip()
                    or "receipt.jpg"
                ),
            }
        )

    return await ingest_receipt_jobs_direct(
        db=db,
        background_tasks=background_tasks,
        receipts_payload=normalized_payload,
        pipeline_id=pipeline_id,
        settings=settings,
        batch_name_prefix="Gmail Receipts",
        batch_description="Gmail direct receipt ingestion",
    )
