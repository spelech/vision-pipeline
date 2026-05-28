import pytest
import io
import json
import uuid
import base64
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace

# Mock StaticFiles and os.makedirs before importing app
with patch("os.makedirs"):
    with patch("os.path.exists", return_value=True):
        with patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()):
            from app import app, SERVICES, get_db
from pipelines import get_pipeline

from httpx import ASGITransport, AsyncClient
from PIL import Image

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_identify_endpoint():
    # Mock core_pipeline.run_pipeline
    mock_results = {
        "barcode": "123456",
        "llm_output": {"product_name": "Test Product", "is_food": False},
        "searxng_results": []
    }

    with patch('app.AsyncSessionLocal') as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        # Mock database select result for Batch
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None # No existing batch
        mock_session.execute.return_value = mock_result

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = mock_results
        with patch('app.get_pipeline', return_value=mock_pipeline):
            # Mock services pre_enrichment
            for svc in SERVICES.values():
                svc.get_pre_enrichment = AsyncMock(return_value={})

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                img = Image.new('RGB', (100, 100), color=(73, 109, 137))
                buf = io.BytesIO()
                img.save(buf, format='JPEG')
                img_bytes = buf.getvalue()

                # Mock file operations
                with patch("builtins.open", MagicMock()):
                    files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
                    data = {'text': 'test context', 'rotation': 0, 'mirror': False}

                    response = await ac.post("/api/identify", data=data, files=files)

                    assert response.status_code == 200
                    res_json = response.json()
                    assert res_json["success"] is True
                    assert res_json["results"]["llm_output"]["product_name"] == "Test Product"
                    assert "ai_preview" in res_json

@pytest.mark.asyncio
async def test_get_locations_endpoint():
    # Mock Homebox headers and requests.get
    with patch.object(SERVICES["homebox"], '_get_headers', return_value={"Authorization": "Bearer test"}):
        with patch('requests.get') as mock_get:
            mock_get.return_value.json.return_value = [{"id": "loc1", "name": "Pantry"}]
            mock_get.return_value.status_code = 200

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/locations")
                assert response.status_code == 200
                assert response.json()["success"] is True
                assert response.json()["locations"][0]["name"] == "Pantry"

@pytest.mark.asyncio
async def test_preview_endpoint():
    # Mock database to return a dummy item
    mock_item = MagicMock()
    mock_item.id = 1
    mock_item.user_overrides = None
    mock_item.ai_output = {"llm_output": {"product_name": "Test"}}

    with patch("app.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/preview/homebox?item_id=1")
            assert response.status_code == 200
            assert "payload" in response.json()

            # Test non-existent service
            response = await ac.get("/api/preview/invalid?item_id=1")
            assert response.status_code == 404

@pytest.mark.asyncio
async def test_execute_endpoint():
    # Mock execution for homebox
    mock_item = MagicMock()
    mock_item.image_path = "test.jpg"
    mock_item.ai_output = {"llm_output": {"product_name": "Test"}}
    mock_item.user_overrides = None

    with patch("app.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        # Mock database query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result

        # Mock service execution
        SERVICES["homebox"].execute = AsyncMock(return_value={"success": True, "item_id": "hb-123"})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"item_id": 1, "service_names": ["homebox"]}
            response = await ac.post("/api/execute", json=payload)

            assert response.status_code == 200
            assert response.json()["results"]["homebox"]["success"] is True

@pytest.mark.asyncio
async def test_batch_upload_endpoint():
    with patch("app.AsyncSessionLocal") as mock_session_factory:
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        async def refresh_side_effect(obj):
            if getattr(obj, "id", None) is None:
                obj.id = 1

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        mock_session.add = MagicMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        # Mock background task to avoid actually running it
        with patch("app.process_item_task", AsyncMock()):
            # Mock open() for file writing
            with patch("builtins.open", MagicMock()):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    img = Image.new('RGB', (10, 10))
                    buf = io.BytesIO()
                    img.save(buf, format='JPEG')

                    files = [
                        ('files', ('img1.jpg', buf.getvalue(), 'image/jpeg'))
                    ]
                    data = {'text': 'Batch Desc'}

                    response = await ac.post("/api/batch-upload", data=data, files=files)
                    assert response.status_code == 200
                    assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_bulk_approve_endpoint():
    with patch("app.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_item = MagicMock()
        mock_item.id = 1
        mock_item.product_type = "product"
        mock_item.image_path = "test.jpg"
        mock_item.ai_output = {"llm_output": {"name": "Test"}}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_session.execute.return_value = mock_result

        # Mock execute_services internally or the SERVICES themselves
        SERVICES["homebox"].execute = AsyncMock(return_value={"success": True})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            payload = {"item_ids": [1]}
            response = await ac.post("/api/bulk-approve", json=payload)
            assert response.status_code == 200
            assert 1 in response.json()["success"]


@pytest.mark.asyncio
async def test_queue_endpoint_all_status_returns_items():
    mock_session = AsyncMock()
    mock_items = [SimpleNamespace(id=1, status="pending"), SimpleNamespace(id=2, status="approved")]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_items
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/queue?status=all")
            assert response.status_code == 200
            payload = response.json()
            assert "items" in payload
            assert len(payload["items"]) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_get_item_endpoint_returns_item():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = SimpleNamespace(
        id=42,
        status="pending",
        image_path="masked_test.png",
        product_type="food",
        ai_output={},
        user_overrides={}
    )
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/items/42")
            assert response.status_code == 200
            payload = response.json()
            assert payload["id"] == 42
            assert payload["image_path"] == "masked_test.png"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_update_and_rerun_item_endpoints():
    mock_session = AsyncMock()

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            update_resp = await ac.post("/api/items/5/update", json={"status": "approved"})
            assert update_resp.status_code == 200
            assert update_resp.json()["success"] is True

            rerun_resp = await ac.post("/api/items/5/rerun")
            assert rerun_resp.status_code == 200
            assert rerun_resp.json()["success"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_identify_returns_500_when_pipeline_run_fails():
    mock_pipeline = MagicMock()
    mock_pipeline.run.side_effect = RuntimeError("pipeline failed")

    with patch("app.get_pipeline", return_value=mock_pipeline):
        with patch("builtins.open", MagicMock()):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                img = Image.new("RGB", (12, 12), color=(20, 20, 20))
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                files = {"file": ("fail.jpg", buf.getvalue(), "image/jpeg")}

                response = await ac.post("/api/identify", files=files, data={"settings": "{"})
                assert response.status_code == 500
                body = response.json()
                assert body["success"] is False
                assert "pipeline failed" in body["error"]


@pytest.mark.feature("models-list")
@pytest.mark.asyncio
async def test_models_endpoint_returns_catalog():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["success"] is True
        assert len(payload["models"]) >= 3


@pytest.mark.feature("pipelines-list")
@pytest.mark.asyncio
async def test_pipelines_endpoint_handles_success_and_error():
    fake_pipeline_list = [{"id": "default", "name": "Default", "schema": {}}]

    with patch("pipelines.get_all_pipelines", return_value=fake_pipeline_list):
        with patch("os.path.exists", return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                ok_resp = await ac.get("/api/pipelines")
                assert ok_resp.status_code == 200
                assert ok_resp.json()["success"] is True
                assert ok_resp.json()["pipelines"][0]["id"] == "default"

    with patch("pipelines.get_all_pipelines", side_effect=RuntimeError("boom")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            err_resp = await ac.get("/api/pipelines")
            assert err_resp.status_code == 200
            assert err_resp.json()["success"] is False


@pytest.mark.feature("config-read")
@pytest.mark.asyncio
async def test_get_config_masks_and_preserves_url_secrets():
    fake_config = {
        "model_favorites": ["qwen/qwen2.5-vl-72b-instruct"],
        "prompt_templates": [{"id": "1", "name": "Default", "prompt": "Analyze"}],
    }

    with patch("app.load_merged_user_config", return_value=fake_config):
        with patch("app.get_secret_value", side_effect=lambda key: "https://example.com" if "URL" in key else "secret"):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.get("/api/config")
                assert response.status_code == 200
                body = response.json()
                assert body["secrets_status"]["SEARXNG_URL"] == "https://example.com"
                assert body["secrets_status"]["OPENROUTER_API_KEY"] == "********"


@pytest.mark.feature("config-write")
@pytest.mark.asyncio
async def test_update_config_persists_custom_pipelines_and_secret():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.load_json_file", return_value={}):
            with patch("app.encrypt_secret", return_value="enc"):
                with patch("app.set_secret_value") as set_secret:
                    with patch("builtins.open", MagicMock()):
                        with patch("json.dump"):
                            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                                payload = {
                                    "custom_pipelines": [{"id": "custom_1", "name": "C1", "schema": {}}],
                                    "OPENROUTER_API_KEY": "abc123"
                                }
                                response = await ac.post("/api/config", json=payload)
                                assert response.status_code == 200
                                assert response.json()["success"] is True
                                set_secret.assert_any_call("OPENROUTER_API_KEY", "abc123")
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.feature("search-items")
@pytest.mark.asyncio
async def test_search_endpoint_returns_merged_item_data():
    mock_session = AsyncMock()
    mock_item = SimpleNamespace(
        id=11,
        status="pending",
        image_path="masked_x.png",
        raw_image_path="raw_x.jpg",
        product_type="food",
        ai_output={"llm_output": {"product_name": "Sriracha", "brand": "Huy Fong"}},
        user_overrides={},
        created_at=datetime.utcnow(),
    )
    mock_mapping = SimpleNamespace(service_name="mealie", external_id="r-1", external_url="http://x")

    first = MagicMock()
    first.scalars.return_value.all.return_value = [mock_item]
    second = MagicMock()
    second.scalars.return_value.all.return_value = [mock_mapping]
    mock_session.execute.side_effect = [first, second]

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/search?query=sriracha")
            assert response.status_code == 200
            payload = response.json()
            assert len(payload["items"]) == 1
            assert payload["items"][0]["product_name"] == "Sriracha"
            assert payload["items"][0]["mappings"][0]["service"] == "mealie"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.feature("session-logs")
@pytest.mark.asyncio
async def test_logs_endpoint_wraps_messages():
    with patch("app.session_logger.get_logs", return_value=["a", "b"]):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/logs/test-session")
            assert response.status_code == 200
            assert response.json()["logs"] == [{"message": "a"}, {"message": "b"}]


@pytest.mark.feature("locations-errors")
@pytest.mark.asyncio
async def test_locations_endpoint_handles_missing_headers():
    with patch.object(SERVICES["homebox"], "_get_headers", return_value={}):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/locations")
            assert response.status_code == 200
            assert response.json()["success"] is False
            assert "No API Key" in response.json()["error"]


@pytest.mark.feature("pipelines-custom")
@pytest.mark.asyncio
async def test_pipelines_endpoint_merges_custom_from_config_file():
    fake_pipeline_list = [{"id": "default", "name": "Default", "schema": {}}]
    custom_pipeline = {"id": "custom_test", "name": "Custom Test", "schema": {}}

    with patch("pipelines.get_all_pipelines", return_value=fake_pipeline_list):
        with patch("os.path.exists", side_effect=lambda p: p == "config/user_config.json"):
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value={"custom_pipelines": [custom_pipeline]}):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                        response = await ac.get("/api/pipelines")
                        assert response.status_code == 200
                        data = response.json()
                        assert data["success"] is True
                        assert any(p["id"] == "custom_test" for p in data["pipelines"])


@pytest.mark.feature("preview-item-not-found")
@pytest.mark.asyncio
async def test_preview_endpoint_item_not_found():
    with patch("app.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/preview/homebox?item_id=404")
            assert response.status_code == 404
            assert response.json()["error"] == "Item not found"


@pytest.mark.feature("delete-item")
@pytest.mark.asyncio
async def test_delete_item_endpoint_deletes_files_and_item():
    mock_session = AsyncMock()
    mock_item = SimpleNamespace(id=3, image_path="masked.png", raw_image_path="raw.jpg")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_item
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("os.path.exists", return_value=True):
            with patch("os.remove") as remove_mock:
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    response = await ac.delete("/api/items/3")
                    assert response.status_code == 200
                    assert response.json()["success"] is True
                    assert remove_mock.call_count == 2
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.feature("config-legacy-homebox-email")
@pytest.mark.asyncio
async def test_update_config_handles_legacy_homebox_email():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.load_json_file", return_value={}):
            with patch("app.encrypt_secret", return_value="enc"):
                with patch("app.set_secret_value") as set_secret:
                    with patch("builtins.open", MagicMock()):
                        with patch("json.dump"):
                            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                                response = await ac.post("/api/config", json={"HOMEBOX_EMAIL": "legacy@example.com"})
                                assert response.status_code == 200
                                assert response.json()["success"] is True
                                set_secret.assert_any_call("HOMEBOX_USERNAME", "legacy@example.com")
    finally:
        app.dependency_overrides.pop(get_db, None)
