from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

with patch("os.makedirs"), patch("os.path.exists", return_value=True), patch(
    "fastapi.staticfiles.StaticFiles", return_value=MagicMock()
):
    from app import app, get_db


@pytest.mark.asyncio
async def test_gmail_status_endpoint_reports_settings_and_connection_state():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("gmail_routes.ensure_app_settings_seed", AsyncMock()), patch(
            "gmail_routes.get_app_settings",
            AsyncMock(
                return_value={
                    "gmail_processed_message_ids": ["m1", "m2"],
                    "gmail_last_sync_at": "2026-05-30T00:00:00+00:00",
                    "gmail_last_error": "",
                }
            ),
        ), patch("app.gmail_ingestor.oauth_configured", return_value=True), patch(
            "app.gmail_ingestor.connected", return_value=False
        ), patch(
            "app.gmail_ingestor.receipt_wrangler_configured", return_value=True
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/gmail/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert payload["oauth_configured"] is True
        assert payload["connected"] is False
        assert payload["receipt_wrangler_configured"] is True
        assert payload["processed_message_count"] == 2
        assert "default" in payload["query_presets"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gmail_search_endpoint_excludes_processed_ids_by_default():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("gmail_routes.ensure_app_settings_seed", AsyncMock()), patch(
            "gmail_routes.get_app_settings",
            AsyncMock(return_value={"gmail_processed_message_ids": ["seen-1"]}),
        ), patch(
            "app.gmail_ingestor.search_receipts",
            return_value={"query": "receipt", "message_count": 1, "messages": [{"message_id": "new-1"}]},
        ) as search_receipts:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/api/gmail/search", json={"query": "receipt", "max_results": 5})

        assert response.status_code == 200
        assert response.json()["message_count"] == 1
        assert search_receipts.call_args.args[0].startswith("receipt")
        assert search_receipts.call_args.args[1] == 5
        assert search_receipts.call_args.args[2] == {"seen-1"}
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gmail_search_builds_query_from_preset_and_filters():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("gmail_routes.ensure_app_settings_seed", AsyncMock()), patch(
            "gmail_routes.get_app_settings",
            AsyncMock(return_value={"gmail_processed_message_ids": []}),
        ), patch(
            "app.gmail_ingestor.search_receipts",
            return_value={"query": "q", "message_count": 0, "messages": []},
        ) as search_receipts:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/gmail/search",
                    json={
                        "preset": "orders",
                        "max_results": 7,
                        "days_back": 30,
                        "has_attachment": True,
                        "include_promotions": False,
                        "include_social": False,
                        "sender_includes": ["amazon.com"],
                        "sender_excludes": ["newsletter@foo.com"],
                        "subject_terms": ["receipt"],
                    },
                )

        assert response.status_code == 200
        built_query = search_receipts.call_args.args[0]
        assert "subject:\"your order\"" in built_query
        assert "newer_than:30d" in built_query
        assert "has:attachment" in built_query
        assert "-category:promotions" in built_query
        assert "-category:social" in built_query
        assert "from:amazon.com" in built_query
        assert "-from:newsletter@foo.com" in built_query
        assert "subject:receipt" in built_query
        assert search_receipts.call_args.args[1] == 7
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gmail_sync_marks_messages_processed_when_requested():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("gmail_routes.ensure_app_settings_seed", AsyncMock()), patch(
            "gmail_routes.get_app_settings",
            AsyncMock(return_value={"gmail_processed_message_ids": ["old-1"]}),
        ), patch(
            "app.gmail_ingestor.search_receipts",
            return_value={
                "query": "receipt",
                "message_count": 2,
                "messages": [{"message_id": "new-1"}, {"message_id": "new-2"}],
            },
        ), patch("gmail_routes.upsert_app_setting", AsyncMock()) as upsert_app_setting:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/gmail/sync",
                    json={"query": "receipt", "max_results": 5, "mark_processed": True},
                )

        assert response.status_code == 200
        assert response.json()["marked_processed"] is True
        processed_update = upsert_app_setting.await_args_list[0]
        assert processed_update.args[1] == "gmail_processed_message_ids"
        assert processed_update.args[2] == ["old-1", "new-1", "new-2"]
        assert mock_session.commit.await_count == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_receipt_wrangler_sync_requires_explicit_selection_and_is_separate():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        missing_selection = await ac.post("/api/gmail/receipt-wrangler-sync", json={"message_ids": []})
        assert missing_selection.status_code == 400

        with patch("app.receipt_wrangler_client.configured", return_value=False):
            response = await ac.post(
                "/api/gmail/receipt-wrangler-sync",
                json={"message_ids": ["msg-1", "msg-2"]},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Receipt Wrangler is not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_receipt_wrangler_sync_processes_selected_message_attachments():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("gmail_routes.ensure_app_settings_seed", AsyncMock()), patch(
            "gmail_routes.get_app_settings",
            AsyncMock(return_value={"gmail_processed_message_ids": ["old-1"]}),
        ), patch(
            "gmail_routes.upsert_app_setting", AsyncMock()
        ) as upsert_app_setting, patch(
            "app.receipt_wrangler_client.configured", return_value=True
        ), patch(
            "app.receipt_wrangler_client.default_group_id", return_value="1"
        ), patch(
            "app.gmail_ingestor.get_message",
            return_value={
                "message_id": "msg-1",
                "attachments": [
                    {
                        "attachment_id": "att-1",
                        "filename": "receipt.pdf",
                        "mime_type": "application/pdf",
                    }
                ],
            },
        ) as get_message, patch(
            "app.gmail_ingestor.download_attachment",
            return_value=b"pdf-bytes",
        ) as download_attachment, patch(
            "app.receipt_wrangler_client.quick_scan_attachment",
            return_value={"id": 42},
        ) as quick_scan:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/gmail/receipt-wrangler-sync",
                    json={"message_ids": ["msg-1"]},
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["selected_count"] == 1
        assert payload["synced_count"] == 1
        assert payload["failed"] == []
        get_message.assert_called_once_with("msg-1")
        download_attachment.assert_called_once_with("msg-1", "att-1")
        quick_scan.assert_called_once()
        processed_update = upsert_app_setting.await_args_list[0]
        assert processed_update.args[1] == "gmail_processed_message_ids"
        assert processed_update.args[2] == ["old-1", "msg-1"]
        assert mock_session.commit.await_count == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_gmail_direct_ingest_requires_selection():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/api/gmail/ingest-direct", json={"message_ids": []})
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()