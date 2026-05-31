from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

with patch("os.makedirs"), patch("os.path.exists", return_value=True), patch(
    "fastapi.staticfiles.StaticFiles", return_value=MagicMock()
):
    from app import app, get_db
    from gmail_routes import _extract_rw_line_items, _to_data_uri


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


@pytest.mark.asyncio
async def test_gmail_direct_ingest_uses_attachment_text_for_line_items():
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    async def refresh_with_ids(entity):
        if getattr(entity, "id", None) is None:
            entity.id = 101

    mock_session.refresh = AsyncMock(side_effect=refresh_with_ids)
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch(
            "app.gmail_ingestor.get_message",
            return_value={
                "message_id": "msg-1",
                "subject": "Receipt",
                "snippet": "",
                "plain_text": "",
                "attachments": [
                    {
                        "attachment_id": "att-1",
                        "filename": "receipt.png",
                        "mime_type": "image/png",
                    }
                ],
            },
        ), patch(
            "app.gmail_ingestor.extract_attachment_text",
            return_value="Widget Z $19.99",
        ) as extract_attachment_text, patch(
            "app.gmail_ingestor.download_attachment",
            return_value=b"png-bytes",
        ), patch(
            "app.gmail_ingestor.extract_line_items_from_message",
            return_value=[{"name": "Widget Z", "line_text": "Widget Z $19.99", "price": "$19.99"}],
        ) as extract_line_items:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/gmail/ingest-direct",
                    json={"message_ids": ["msg-1"], "mark_processed": False},
                )

        assert response.status_code == 200
        assert response.json()["selected_count"] == 1
        extract_attachment_text.assert_called_once_with(
            "msg-1",
            {
                "attachment_id": "att-1",
                "filename": "receipt.png",
                "mime_type": "image/png",
            },
        )
        extract_line_items.assert_called_once_with(
            {
                "message_id": "msg-1",
                "subject": "Receipt",
                "snippet": "",
                "plain_text": "",
                "attachments": [
                    {
                        "attachment_id": "att-1",
                        "filename": "receipt.png",
                        "mime_type": "image/png",
                    }
                ],
            },
            "Widget Z $19.99",
        )
        assert mock_session.commit.await_count >= 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_receipt_wrangler_process_pulls_and_resolves_pending_receipts():
    mock_session = MagicMock()
    mock_session.commit = AsyncMock()

    async def refresh_with_ids(entity):
        if getattr(entity, "id", None) is None:
            entity.id = 202

    mock_session.refresh = AsyncMock(side_effect=refresh_with_ids)
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.receipt_wrangler_client.configured", return_value=True), patch(
            "app.receipt_wrangler_client.get_pending_receipts",
            return_value=[
                {
                    "id": "rw-1",
                    "merchant": "Test Mart",
                    "image_id": "img-1",
                    "lineItems": [{"name": "Milk", "price": "3.99", "quantity": 2}],
                }
            ],
        ), patch(
            "app.receipt_wrangler_client.download_receipt_image",
            return_value=b"jpg-bytes",
        ), patch(
            "app.receipt_wrangler_client.update_receipt_status",
            return_value={"ok": True},
        ) as update_status, patch(
            "app.process_item_task_safe",
            AsyncMock(),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/api/gmail/receipt-wrangler-process",
                    json={"limit": 10, "mark_resolved": True},
                )

        assert response.status_code == 200
        payload = response.json()
        assert payload["pending_count"] == 1
        assert payload["processed_count"] == 1
        assert payload["resolved_count"] == 1
        assert payload["created_items"] == 1
        assert payload["batch_id"] == 202
        assert mock_session.add.call_count >= 2
        added_item = mock_session.add.call_args_list[1].args[0]
        assert added_item.ai_output["source"] == "receipt_wrangler"
        assert added_item.ai_output["receipt_line_item"]["name"] == "Milk"
        assert added_item.ai_output["receipt_image_data_uri"].startswith(
            "data:image/jpeg;base64,"
        )
        update_status.assert_called_once_with("rw-1", "RESOLVED")
    finally:
        app.dependency_overrides.clear()


def test_receipt_wrangler_helpers_cover_line_item_and_data_uri_fallbacks():
    items = _extract_rw_line_items(
        {
            "lineItems": [
                {"name": "Eggs", "price": "2.99", "quantity": 2, "barcode": "123"},
                {"description": "Bread", "amount": "1.99"},
            ]
        }
    )
    assert len(items) == 2
    assert items[0]["name"] == "Eggs"
    assert items[0]["barcode"] == "123"
    assert items[1]["name"] == "Bread"

    fallback_items = _extract_rw_line_items({"merchant": "Store X", "note": "Manual receipt"})
    assert fallback_items[0]["name"] == "Store X"
    assert fallback_items[0]["line_text"] == "Manual receipt"

    assert _to_data_uri(b"", "image/png") == ""
    assert _to_data_uri(b"abc", "image/png").startswith("data:image/png;base64,")