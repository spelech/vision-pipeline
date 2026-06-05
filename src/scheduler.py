import logging
from datetime import datetime, timezone
from typing import Any, Dict
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from fastapi.concurrency import run_in_threadpool

import database
from app_helpers import (
    ensure_app_settings_seed,
    get_app_settings,
    upsert_app_setting,
)
from services.registry import gmail_ingestor

logger = logging.getLogger("VisionAPI.scheduler")

RUNTIME_STATE: Dict[str, Any] = {"gmail_scheduler": None}
GMAIL_AUTO_SYNC_JOB_ID = "gmail-auto-sync"
GMAIL_AUTO_SYNC_DEFAULT_QUERY = (
    'has:attachment (subject:receipt OR subject:"order confirmation" OR subject:invoice)'
)


def _parse_int_setting(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(parsed, max_value))


async def run_gmail_auto_sync_once() -> None:
    async with database.async_session_local() as db:
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)

        enabled = bool(settings.get("gmail_auto_sync_enabled", False))
        if not enabled:
            return

        query = str(
            settings.get("gmail_auto_sync_query") or GMAIL_AUTO_SYNC_DEFAULT_QUERY
        ).strip()
        max_results = _parse_int_setting(
            settings.get("gmail_auto_sync_max_results"),
            default=25,
            min_value=1,
            max_value=100,
        )

        if not gmail_ingestor.oauth_configured() or not gmail_ingestor.connected():
            await upsert_app_setting(
                db,
                "gmail_last_error",
                "Gmail auto-sync skipped: OAuth not configured or connected",
            )
            await db.commit()
            return

        try:
            result = await run_in_threadpool(
                gmail_ingestor.search_receipts,
                query,
                max_results,
                set(),
            )
            await upsert_app_setting(
                db,
                "gmail_last_sync_at",
                datetime.now(timezone.utc).isoformat(),
            )
            await upsert_app_setting(db, "gmail_last_error", "")
            await upsert_app_setting(
                db,
                "gmail_last_auto_sync_count",
                int(result.get("message_count") or 0),
            )
        except (requests.RequestException, ValueError) as exc:
            await upsert_app_setting(db, "gmail_last_error", str(exc))

        await db.commit()


async def configure_gmail_auto_sync_scheduler() -> None:
    async with database.async_session_local() as db:
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)

    interval_minutes = _parse_int_setting(
        settings.get("gmail_poll_interval_minutes"),
        default=30,
        min_value=1,
        max_value=1440,
    )
    enabled = bool(settings.get("gmail_auto_sync_enabled", False))

    scheduler_raw = RUNTIME_STATE.get("gmail_scheduler")
    scheduler = (
        scheduler_raw
        if scheduler_raw and hasattr(scheduler_raw, "add_job") and hasattr(scheduler_raw, "get_job")
        else None
    )
    if scheduler is None:
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.start()
        RUNTIME_STATE["gmail_scheduler"] = scheduler

    if scheduler.get_job(GMAIL_AUTO_SYNC_JOB_ID):
        scheduler.remove_job(GMAIL_AUTO_SYNC_JOB_ID)

    if enabled:
        scheduler.add_job(
            run_gmail_auto_sync_once,
            trigger="interval",
            minutes=interval_minutes,
            id=GMAIL_AUTO_SYNC_JOB_ID,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
