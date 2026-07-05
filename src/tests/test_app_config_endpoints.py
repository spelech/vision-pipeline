from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.exc import SQLAlchemyError

with patch("os.makedirs"), patch("os.path.exists", return_value=True), patch(
    "fastapi.staticfiles.StaticFiles", return_value=MagicMock()
):
    from app import (
        ConfigUpdateRequest,
        delete_pipeline,
        delete_item,
        get_item,
        get_queue,
        get_config,
        list_models,
        list_pipelines,
        bulk_approve,
        rerun_item,
        root,
        spa_fallback,
        update_config,
        update_item_data,
        upsert_pipeline,
        process_item_task,
        process_item_task_safe,
        encode_image_bytes_to_data_uri,
    )


class _ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _ScalarRows(self._rows)


class _BackgroundTasks:
    def __init__(self):
        self.calls = []

    def add_task(self, func, *args):
        self.calls.append((func, args))


@pytest.mark.asyncio
async def test_list_pipelines_success_and_failure_paths():
    db = SimpleNamespace()
    with patch("routes.pipeline_routes.ensure_pipeline_catalog", AsyncMock()), patch(
        "routes.pipeline_routes.list_pipeline_definitions",
        AsyncMock(return_value=[{"id": "default", "name": "Default", "schema": {}}]),
    ):
        response = await list_pipelines(db)
        assert response.success is True
        assert response.pipelines

    with patch("routes.pipeline_routes.ensure_pipeline_catalog", AsyncMock()), patch(
        "routes.pipeline_routes.list_pipeline_definitions",
        AsyncMock(side_effect=RuntimeError("db down")),
    ), patch(
        "pipelines.get_all_pipelines",
        return_value=[{"id": "fallback", "name": "Fallback", "schema": {}}],
    ):
        response = await list_pipelines(db)
        assert response.success is True
        assert response.pipelines
        assert response.error


@pytest.mark.asyncio
async def test_upsert_pipeline_insert_and_update_paths():
    existing = SimpleNamespace(
        name="Old",
        schema={},
        is_system=False,
        is_editable=True,
        service_target=None,
    )

    insert_db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(None)),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    with patch("routes.pipeline_routes.ensure_pipeline_catalog", AsyncMock()):
        result = await upsert_pipeline(
            "custom_1",
            {"name": "Custom 1", "schema": {"vision_model": {"default": "qwen/qwen2.5-72b-instruct"}}},
            insert_db,
        )
    assert result["success"] is True
    assert insert_db.add.called

    update_db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(existing)),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    with patch("routes.pipeline_routes.ensure_pipeline_catalog", AsyncMock()):
        result = await upsert_pipeline("service_homebox", {"name": "Service"}, update_db)
    assert result["success"] is True
    assert existing.name == "Service"
    assert existing.service_target == "homebox"


@pytest.mark.asyncio
async def test_delete_pipeline_found_and_missing_paths():
    db_missing = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(None)),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    resp = await delete_pipeline("missing", db_missing)
    assert resp["success"] is False

    row = SimpleNamespace(pipeline_id="x")
    db_found = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(row)),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    resp = await delete_pipeline("x", db_found)
    assert resp["success"] is True
    db_found.delete.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_list_models_success_and_error_paths():
    rows = [SimpleNamespace(model_id="m1", name="Model One", provider="openrouter", is_system=True)]
    db_ok = SimpleNamespace(execute=AsyncMock(return_value=_Result(rows=rows)))

    with patch("routes.model_routes.ensure_model_catalog", AsyncMock()):
        response = await list_models(db_ok)
    assert response.success is True
    assert response.models[0].id == "m1"

    db_err = SimpleNamespace(execute=AsyncMock())
    with patch("routes.model_routes.ensure_model_catalog", AsyncMock(side_effect=RuntimeError("catalog error"))):
        response = await list_models(db_err)
    assert response.success is False


@pytest.mark.asyncio
async def test_get_config_masks_secrets_and_handles_pipeline_failure():
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(rows=[
            SimpleNamespace(key="HOMEBOX_URL", encrypted_value="enc-val")
        ]))
    )
    settings = {
        "prompt_templates": [{"id": "a", "name": "A", "prompt": "x"}],
        "service_prompts": {"homebox": {"prompt": "p", "enabled": True}},
        "model_favorites": ["m1", "m2"],
        "starred_models": ["m2"],
        "image_optimization": {"quality": 80},
    }

    secret_values = {"HOMEBOX_URL": "http://example.test", "OPENROUTER_API_KEY": "secret-token"}

    def _secret(key: str) -> str:
        return secret_values.get(key, "")

    with patch("routes.config_routes.ensure_app_settings_seed", AsyncMock()), patch(
        "routes.config_routes.get_app_settings", AsyncMock(return_value=settings)
    ), patch("routes.config_routes.ensure_pipeline_catalog", AsyncMock(side_effect=SQLAlchemyError("skip"))), patch(
        "routes.config_routes.get_secret_value", side_effect=_secret
    ), patch("routes.config_routes.ORIGINAL_ENV", {"OPENROUTER_API_KEY": "env-val"}):
        response = await get_config(db)

    assert response.secrets_status["HOMEBOX_URL"] == "http://example.test"
    assert response.secrets_status["OPENROUTER_API_KEY"] == "********"
    assert response.secrets_sources["HOMEBOX_URL"] == "database"
    assert response.secrets_sources["OPENROUTER_API_KEY"] == "environment"
    assert response.secrets_sources["LLM_API_KEY"] == "none"
    assert response.custom_pipelines == []


@pytest.mark.asyncio
async def test_get_config_reveals_secrets_when_requested():
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(rows=[]))
    )
    settings = {
        "prompt_templates": [],
        "service_prompts": {},
        "model_favorites": [],
        "starred_models": [],
        "image_optimization": {},
    }

    secret_values = {"HOMEBOX_URL": "http://example.test", "OPENROUTER_API_KEY": "secret-token"}

    def _secret(key: str) -> str:
        return secret_values.get(key, "")

    with patch("routes.config_routes.ensure_app_settings_seed", AsyncMock()), patch(
        "routes.config_routes.get_app_settings", AsyncMock(return_value=settings)
    ), patch("routes.config_routes.ensure_pipeline_catalog", AsyncMock()), patch(
        "routes.config_routes.list_pipeline_definitions", AsyncMock(return_value=[])
    ), patch("routes.config_routes.get_secret_value", side_effect=_secret):
        response = await get_config(db, reveal_secrets=True)

    assert response.secrets_status["HOMEBOX_URL"] == "http://example.test"
    assert response.secrets_status["OPENROUTER_API_KEY"] == "secret-token"


@pytest.mark.asyncio
async def test_get_config_derives_prompt_templates_from_pipeline_defaults_when_empty():
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(rows=[]))
    )
    settings = {
        "prompt_templates": [],
        "service_prompts": {},
        "model_favorites": [],
        "starred_models": [],
        "image_optimization": {},
    }

    with patch("routes.config_routes.ensure_app_settings_seed", AsyncMock()), patch(
        "routes.config_routes.get_app_settings", AsyncMock(return_value=settings)
    ), patch("routes.config_routes.ensure_pipeline_catalog", AsyncMock()), patch(
        "routes.config_routes.list_pipeline_definitions", AsyncMock(return_value=[])
    ), patch("pipelines.get_all_pipelines", return_value=[
        {
            "id": "receipt",
            "name": "Receipt",
            "schema": {
                "vision_prompt": {"default": "Extract receipt text"},
                "search_results_limit": {"default": 7},
            },
        }
    ]), patch("routes.config_routes.get_secret_value", return_value=""):
        response = await get_config(db)

    assert response.prompt_templates is not None
    assert any(template.name == "Receipt vision prompt" for template in response.prompt_templates)


@pytest.mark.asyncio
async def test_update_config_persists_settings_models_and_secret_values():
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Result(None), _Result(None), _Result(None), _Result(None)]),
        add=MagicMock(),
        commit=AsyncMock(),
    )

    payload = ConfigUpdateRequest(
        model_favorites=["custom/model"],
        custom_pipelines=[{"id": "custom", "name": "Custom", "schema": {}}],
        service_prompts={
            "homebox": {
                "service": "homebox",
                "prompt": "custom prompt",
                "enabled": True,
                "model": "qwen/qwen2.5-32b-instruct",
                "feedback_enabled": False,
                "feedback_prompt": "",
            }
        },
        OPENROUTER_API_KEY="token-123",
    )

    with patch("routes.config_routes.ensure_app_settings_seed", AsyncMock()), patch(
        "routes.config_routes.ensure_pipeline_catalog", AsyncMock()
    ), patch("routes.config_routes.persist_custom_pipelines", AsyncMock()), patch(
        "routes.config_routes.upsert_app_setting", AsyncMock()
    ), patch("secrets_manager.set_secret_value") as set_secret, patch(
        "secrets_manager.encrypt_secret", return_value="enc-token"
    ):
        response = await update_config(payload, db)

    assert response["success"] is True
    assert db.commit.await_count == 1
    assert db.add.call_count >= 2
    set_secret.assert_called_once_with("OPENROUTER_API_KEY", "token-123")


@pytest.mark.asyncio
async def test_update_config_reset_secret_to_empty_string():
    import os
    secret_obj = SimpleNamespace(key="OPENROUTER_API_KEY", encrypted_value="enc")
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=secret_obj)),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )

    payload = ConfigUpdateRequest(
        OPENROUTER_API_KEY="",
    )

    with patch("routes.config_routes.ensure_app_settings_seed", AsyncMock()), patch(
        "routes.config_routes.ORIGINAL_ENV", {"OPENROUTER_API_KEY": "fallback-key"}
    ), patch("secrets_manager.set_secret_value") as set_secret:
        response = await update_config(payload, db)

    assert response["success"] is True
    db.delete.assert_awaited_once_with(secret_obj)
    db.commit.assert_awaited_once()
    assert os.environ.get("OPENROUTER_API_KEY") == "fallback-key"


@pytest.mark.asyncio
async def test_root_and_spa_fallback_serve_index_and_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    dist = tmp_path / "dist"
    assets_dir = dist / "assets"
    assets_dir.mkdir(parents=True)
    index_file = dist / "index.html"
    asset_file = assets_dir / "main.js"
    index_file.write_text("<html>ok</html>", encoding="utf-8")
    asset_file.write_text("console.log('ok')", encoding="utf-8")

    monkeypatch.setattr("app.WEB_DIST_DIR", dist)
    monkeypatch.setattr("app.WEB_INDEX_FILE", index_file)

    root_resp = await root()
    assert isinstance(root_resp, FileResponse)

    file_resp = await spa_fallback("assets/main.js")
    assert isinstance(file_resp, FileResponse)

    index_resp = await spa_fallback("settings/profile")
    assert isinstance(index_resp, FileResponse)

    with pytest.raises(HTTPException) as exc:
        await spa_fallback("api/health")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_root_uses_fallback_web_dist_when_primary_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    primary = tmp_path / "primary_dist"
    fallback = tmp_path / "fallback_dist"
    primary.mkdir(parents=True)
    fallback.mkdir(parents=True)

    index_file = fallback / "index.html"
    index_file.write_text("<html>fallback</html>", encoding="utf-8")

    monkeypatch.setattr("app.WEB_DIST_DIR", primary)
    monkeypatch.setattr("app.WEB_INDEX_FILE", primary / "index.html")
    monkeypatch.setattr("app.WEB_DIST_FALLBACKS", [fallback])

    root_resp = await root()
    assert isinstance(root_resp, FileResponse)

    spa_resp = await spa_fallback("settings/profile")
    assert isinstance(spa_resp, FileResponse)



@pytest.mark.asyncio
async def test_process_item_task_success_and_error_and_safe_wrapper():
    review_uri = encode_image_bytes_to_data_uri(b"img", mime="image/jpeg")
    item = SimpleNamespace(
        id=1,
        batch_id=2,
        image_path=review_uri,
        raw_image_path=review_uri,
        status="processing",
        error=None,
        ai_output={},
        product_type="product",
    )
    batch = SimpleNamespace(description="desc")

    execute_results = [
        _Result(item),
        _Result(batch),
        _Result(item),
        _Result(batch),
    ]
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute_results),
        commit=AsyncMock(),
    )
    session_cm = AsyncMock()
    session_cm.__aenter__.return_value = db
    session_cm.__aexit__.return_value = None

    mock_pipeline = MagicMock()
    mock_pipeline.run.return_value = {
        "llm_output": {"product_name": "Widget", "is_food": False},
        "searxng_results": [],
        "scraped_content": "",
    }

    with patch("database.async_session_local", return_value=session_cm), patch(
        "tasks.get_pipeline", return_value=mock_pipeline
    ), patch("tasks.run_in_threadpool", AsyncMock(return_value=mock_pipeline.run.return_value)), patch(
        "tasks.decode_data_uri_to_bytes", return_value=b"bytes"
    ), patch("tasks.Image.open", return_value=SimpleNamespace()), patch(
        "tasks.ImageOps.exif_transpose", return_value=SimpleNamespace()
    ), patch("tasks.build_review_image_data_uri", return_value=review_uri), patch(
        "tasks.get_runtime_service_prompt_configs", AsyncMock(return_value={"homebox": {}})
    ), patch("tasks.generate_service_output", return_value={"status": "ready", "data": {}}), patch.object(
        list(__import__("app").SERVICES.values())[0],
        "get_pre_enrichment",
        AsyncMock(return_value={}),
    ), patch.object(
        list(__import__("app").SERVICES.values())[1],
        "get_pre_enrichment",
        AsyncMock(return_value={}),
    ), patch.object(
        list(__import__("app").SERVICES.values())[2],
        "get_pre_enrichment",
        AsyncMock(return_value={}),
    ), patch.object(
        list(__import__("app").SERVICES.values())[3],
        "get_pre_enrichment",
        AsyncMock(return_value={}),
    ):
        await process_item_task(1, "default", "{}")

    assert item.status == "pending"
    assert db.commit.await_count >= 1

    error_item = SimpleNamespace(
        id=3,
        batch_id=4,
        image_path="no-data",
        raw_image_path=None,
        status="processing",
        error=None,
        ai_output={},
    )
    error_db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Result(error_item), _Result(batch)]),
        commit=AsyncMock(),
    )
    error_cm = AsyncMock()
    error_cm.__aenter__.return_value = error_db
    error_cm.__aexit__.return_value = None

    with patch("database.async_session_local", return_value=error_cm), patch("tasks.get_pipeline", return_value=mock_pipeline):
        await process_item_task(3, "default", "{}")

    assert error_item.status == "error"
    assert isinstance(error_item.error, str)

    with patch("tasks.process_item_task", AsyncMock(side_effect=RuntimeError("bg fail"))):
        await process_item_task_safe(99, "default", "{}")


@pytest.mark.asyncio
async def test_queue_item_update_delete_and_rerun_endpoints():
    items = [SimpleNamespace(id=1, created_at=1), SimpleNamespace(id=2, created_at=2)]
    queue_db = SimpleNamespace(execute=AsyncMock(return_value=_Result(rows=items)))
    queue_resp = await get_queue("all", queue_db)
    assert queue_resp["items"] == items

    item = SimpleNamespace(id=123, status="pending")
    item_db = SimpleNamespace(execute=AsyncMock(return_value=_Result(item)))
    item_resp = await get_item(123, item_db)
    assert item_resp.id == 123

    missing_db = SimpleNamespace(execute=AsyncMock(return_value=_Result(None)))
    with pytest.raises(HTTPException) as exc:
        await get_item(404, missing_db)
    assert exc.value.status_code == 404

    update_db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
    update_resp = await update_item_data(10, {"status": "approved"}, update_db)
    assert update_resp["success"] is True
    assert update_db.commit.await_count == 1

    delete_db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Result(item), _Result(None)]),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    delete_resp = await delete_item(10, delete_db)
    assert delete_resp["success"] is True
    delete_db.delete.assert_awaited_once_with(item)

    bg_tasks = _BackgroundTasks()
    rerun_db = SimpleNamespace(execute=AsyncMock(), commit=AsyncMock())
    rerun_resp = await rerun_item(88, bg_tasks, rerun_db)
    assert rerun_resp["success"] is True
    assert len(bg_tasks.calls) == 1
    assert bg_tasks.calls[0][1][0] == 88


@pytest.mark.asyncio
async def test_bulk_approve_success_failure_and_missing_item_paths():
    item_food = SimpleNamespace(id=1, product_type="food")
    item_product = SimpleNamespace(id=2, product_type="product")

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Result(item_food), _Result(item_product), _Result(None)]),
    )

    with patch(
        "routes.item_routes.execute_services",
        AsyncMock(side_effect=[{"success": True}, {"success": False, "error": "sync failed"}]),
    ):
        result = await bulk_approve({"item_ids": [1, 2, 999]}, db)

    assert result["success"] == [1]
    assert result["failed"] == [{"id": 2, "error": "sync failed"}]
