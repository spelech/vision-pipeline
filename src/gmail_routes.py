from datetime import datetime, timezone
from typing import Any, Callable, List, Optional, Set

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_helpers import ensure_app_settings_seed, get_app_settings, upsert_app_setting

GMAIL_DEFAULT_RECEIPT_QUERY = (
    'has:attachment (subject:receipt OR subject:"order confirmation" OR subject:invoice)'
)
GMAIL_PROCESSED_IDS_KEY = "gmail_processed_message_ids"
GMAIL_LAST_SYNC_AT_KEY = "gmail_last_sync_at"
GMAIL_LAST_ERROR_KEY = "gmail_last_error"


class GmailAuthUrlRequest(BaseModel):
    redirect_uri: str
    state: Optional[str] = None


class GmailAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


class GmailSearchRequest(BaseModel):
    query: Optional[str] = None
    max_results: int = 25
    only_uningested: bool = True


class GmailSyncRequest(BaseModel):
    query: Optional[str] = None
    max_results: int = 25
    mark_processed: bool = False


class GmailMarkProcessedRequest(BaseModel):
    message_ids: List[str]


class GmailReceiptWranglerSyncRequest(BaseModel):
    message_ids: List[str]


def _coerce_processed_ids(raw_value: Any) -> List[str]:
    if not isinstance(raw_value, list):
        return []

    deduped: List[str] = []
    for value in raw_value:
        if not isinstance(value, str):
            continue
        message_id = value.strip()
        if not message_id or message_id in deduped:
            continue
        deduped.append(message_id)
    return deduped


def _merge_processed_ids(existing_ids: List[str], incoming_ids: List[str]) -> List[str]:
    return list(dict.fromkeys(existing_ids + incoming_ids))


def build_gmail_router(
    get_db: Callable[[], Any],
    gmail_ingestor: Any,
    upsert_secret: Callable[[AsyncSession, str, str], Any],
) -> APIRouter:
    # pylint: disable=too-many-statements
    router = APIRouter(prefix="/gmail", tags=["gmail"])

    @router.get("/status")
    async def gmail_status(db: AsyncSession = Depends(get_db)):
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)
        processed_ids = _coerce_processed_ids(settings.get(GMAIL_PROCESSED_IDS_KEY))
        return {
            "success": True,
            "oauth_configured": gmail_ingestor.oauth_configured(),
            "connected": gmail_ingestor.connected(),
            "last_sync_at": settings.get(GMAIL_LAST_SYNC_AT_KEY),
            "last_error": settings.get(GMAIL_LAST_ERROR_KEY),
            "processed_message_count": len(processed_ids),
        }

    @router.post("/auth-url")
    async def gmail_auth_url(data: GmailAuthUrlRequest):
        try:
            auth_url = gmail_ingestor.build_auth_url(
                redirect_uri=data.redirect_uri,
                state=data.state,
            )
            return {"success": True, "auth_url": auth_url}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/callback")
    async def gmail_callback(
        data: GmailAuthCallbackRequest,
        db: AsyncSession = Depends(get_db),
    ):
        try:
            token_payload = await run_in_threadpool(
                gmail_ingestor.exchange_code_for_tokens,
                data.code,
                data.redirect_uri,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Google token exchange failed: {exc}",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        refresh_token = token_payload.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token.strip():
            await upsert_secret(db, "GWS_REFRESH_TOKEN", refresh_token.strip())
            await db.commit()
            return {"success": True, "connected": True}

        return {
            "success": False,
            "connected": gmail_ingestor.connected(),
            "error": "No refresh token returned by Google. Re-auth with consent prompt.",
        }

    @router.post("/search")
    async def gmail_search(
        data: GmailSearchRequest,
        db: AsyncSession = Depends(get_db),
    ):
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)
        processed_ids = _coerce_processed_ids(settings.get(GMAIL_PROCESSED_IDS_KEY))
        exclude_ids: Set[str] = set(processed_ids) if data.only_uningested else set()
        query = data.query or GMAIL_DEFAULT_RECEIPT_QUERY

        try:
            result = await run_in_threadpool(
                gmail_ingestor.search_receipts,
                query,
                data.max_results,
                exclude_ids,
            )
            return {"success": True, **result}
        except requests.RequestException as exc:
            raise HTTPException(status_code=502, detail=f"Gmail search failed: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/receipt-wrangler-sync")
    async def gmail_receipt_wrangler_sync(data: GmailReceiptWranglerSyncRequest):
        selected_message_ids = _coerce_processed_ids(data.message_ids)
        if not selected_message_ids:
            raise HTTPException(
                status_code=400,
                detail="At least one Gmail message must be selected",
            )

        raise HTTPException(
            status_code=501,
            detail=(
                "Selective Receipt Wrangler sync is not implemented yet. "
                "Use this route from the UI once the Receipt Wrangler client is added."
            ),
        )

    @router.post("/sync")
    async def gmail_sync(
        data: GmailSyncRequest,
        db: AsyncSession = Depends(get_db),
    ):
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)
        processed_ids = _coerce_processed_ids(settings.get(GMAIL_PROCESSED_IDS_KEY))
        query = data.query or GMAIL_DEFAULT_RECEIPT_QUERY

        try:
            result = await run_in_threadpool(
                gmail_ingestor.search_receipts,
                query,
                data.max_results,
                set(processed_ids),
            )
        except requests.RequestException as exc:
            await upsert_app_setting(db, GMAIL_LAST_ERROR_KEY, str(exc))
            await db.commit()
            raise HTTPException(status_code=502, detail=f"Gmail sync failed: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        message_ids = [
            str(message.get("message_id"))
            for message in result.get("messages", [])
            if isinstance(message, dict) and message.get("message_id")
        ]

        if data.mark_processed:
            merged_ids = _merge_processed_ids(processed_ids, message_ids)
            await upsert_app_setting(db, GMAIL_PROCESSED_IDS_KEY, merged_ids)

        await upsert_app_setting(
            db,
            GMAIL_LAST_SYNC_AT_KEY,
            datetime.now(timezone.utc).isoformat(),
        )
        await upsert_app_setting(db, GMAIL_LAST_ERROR_KEY, "")
        await db.commit()

        return {
            "success": True,
            "query": result.get("query"),
            "message_count": result.get("message_count", 0),
            "messages": result.get("messages", []),
            "marked_processed": data.mark_processed,
        }

    @router.post("/mark-processed")
    async def gmail_mark_processed(
        data: GmailMarkProcessedRequest,
        db: AsyncSession = Depends(get_db),
    ):
        await ensure_app_settings_seed(db)
        settings = await get_app_settings(db)
        existing_ids = _coerce_processed_ids(settings.get(GMAIL_PROCESSED_IDS_KEY))
        incoming_ids = _coerce_processed_ids(data.message_ids)
        merged_ids = _merge_processed_ids(existing_ids, incoming_ids)
        await upsert_app_setting(db, GMAIL_PROCESSED_IDS_KEY, merged_ids)
        await db.commit()
        return {
            "success": True,
            "processed_message_count": len(merged_ids),
        }

    return router
