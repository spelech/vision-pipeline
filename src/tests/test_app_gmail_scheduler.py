from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

import scheduler


@pytest.mark.asyncio
async def test_run_gmail_auto_sync_once_skips_when_disabled():
    db = SimpleNamespace(commit=AsyncMock())
    cm = AsyncMock()
    cm.__aenter__.return_value = db
    cm.__aexit__.return_value = None

    with patch("database.async_session_local", return_value=cm), patch(
        "scheduler.ensure_app_settings_seed", AsyncMock()
    ), patch(
        "scheduler.get_app_settings", AsyncMock(return_value={"gmail_auto_sync_enabled": False})
    ):
        await scheduler.run_gmail_auto_sync_once()

    assert db.commit.await_count == 0


@pytest.mark.asyncio
async def test_run_gmail_auto_sync_once_sets_error_when_not_connected():
    db = SimpleNamespace(commit=AsyncMock())
    cm = AsyncMock()
    cm.__aenter__.return_value = db
    cm.__aexit__.return_value = None

    with patch("database.async_session_local", return_value=cm), patch(
        "scheduler.ensure_app_settings_seed", AsyncMock()
    ), patch(
        "scheduler.get_app_settings", AsyncMock(return_value={"gmail_auto_sync_enabled": True})
    ), patch("scheduler.gmail_ingestor.oauth_configured", return_value=False), patch(
        "scheduler.upsert_app_setting", AsyncMock()
    ) as upsert:
        await scheduler.run_gmail_auto_sync_once()

    assert upsert.await_count >= 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_gmail_auto_sync_once_success_and_error_paths():
    settings = {
        "gmail_auto_sync_enabled": True,
        "gmail_auto_sync_query": "subject:receipt",
        "gmail_auto_sync_max_results": 10,
    }
    db = SimpleNamespace(commit=AsyncMock())
    cm = AsyncMock()
    cm.__aenter__.return_value = db
    cm.__aexit__.return_value = None

    with patch("database.async_session_local", return_value=cm), patch(
        "scheduler.ensure_app_settings_seed", AsyncMock()
    ), patch("scheduler.get_app_settings", AsyncMock(return_value=settings)), patch(
        "scheduler.gmail_ingestor.oauth_configured", return_value=True
    ), patch("scheduler.gmail_ingestor.connected", return_value=True), patch(
        "scheduler.gmail_ingestor.search_receipts", return_value={"message_count": 4}
    ), patch("scheduler.upsert_app_setting", AsyncMock()) as upsert:
        await scheduler.run_gmail_auto_sync_once()

    assert upsert.await_count >= 3

    with patch("database.async_session_local", return_value=cm), patch(
        "scheduler.ensure_app_settings_seed", AsyncMock()
    ), patch("scheduler.get_app_settings", AsyncMock(return_value=settings)), patch(
        "scheduler.gmail_ingestor.oauth_configured", return_value=True
    ), patch("scheduler.gmail_ingestor.connected", return_value=True), patch(
        "scheduler.gmail_ingestor.search_receipts",
        side_effect=requests.RequestException("down"),
    ), patch("scheduler.upsert_app_setting", AsyncMock()) as upsert_error:
        await scheduler.run_gmail_auto_sync_once()

    assert upsert_error.await_count >= 1


@pytest.mark.asyncio
async def test_configure_scheduler_adds_job_only_when_enabled():
    db = SimpleNamespace()
    cm = AsyncMock()
    cm.__aenter__.return_value = db
    cm.__aexit__.return_value = None

    mock_scheduler = MagicMock()
    mock_scheduler.get_job.return_value = None
    scheduler.RUNTIME_STATE["gmail_scheduler"] = None

    with patch("database.async_session_local", return_value=cm), patch(
        "scheduler.ensure_app_settings_seed", AsyncMock()
    ), patch(
        "scheduler.get_app_settings",
        AsyncMock(return_value={"gmail_auto_sync_enabled": False, "gmail_poll_interval_minutes": 30}),
    ), patch("scheduler.AsyncIOScheduler", return_value=mock_scheduler):
        await scheduler.configure_gmail_auto_sync_scheduler()

    mock_scheduler.start.assert_called_once()
    assert mock_scheduler.add_job.call_count == 0

    with patch("database.async_session_local", return_value=cm), patch(
        "scheduler.ensure_app_settings_seed", AsyncMock()
    ), patch(
        "scheduler.get_app_settings",
        AsyncMock(return_value={"gmail_auto_sync_enabled": True, "gmail_poll_interval_minutes": 15}),
    ):
        await scheduler.configure_gmail_auto_sync_scheduler()

    assert mock_scheduler.add_job.call_count >= 1