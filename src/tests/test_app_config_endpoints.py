from __future__ import annotations

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
        get_config,
        list_models,
        list_pipelines,
        root,
        spa_fallback,
        update_config,
        upsert_pipeline,
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


@pytest.mark.asyncio
async def test_list_pipelines_success_and_failure_paths():
    db = SimpleNamespace()
    with patch("app.ensure_pipeline_catalog", AsyncMock()), patch(
        "app.list_pipeline_definitions",
        AsyncMock(return_value=[{"id": "default", "name": "Default", "schema": {}}]),
    ):
        response = await list_pipelines(db)
        assert response.success is True
        assert response.pipelines

    with patch("app.ensure_pipeline_catalog", AsyncMock()), patch(
        "app.list_pipeline_definitions",
        AsyncMock(side_effect=RuntimeError("db down")),
    ):
        response = await list_pipelines(db)
        assert response.success is False
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
    with patch("app.ensure_pipeline_catalog", AsyncMock()):
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
    with patch("app.ensure_pipeline_catalog", AsyncMock()):
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

    with patch("app.ensure_model_catalog", AsyncMock()):
        response = await list_models(db_ok)
    assert response.success is True
    assert response.models[0].id == "m1"

    db_err = SimpleNamespace(execute=AsyncMock())
    with patch("app.ensure_model_catalog", AsyncMock(side_effect=RuntimeError("catalog error"))):
        response = await list_models(db_err)
    assert response.success is False


@pytest.mark.asyncio
async def test_get_config_masks_secrets_and_handles_pipeline_failure():
    db = SimpleNamespace()
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

    with patch("app.ensure_app_settings_seed", AsyncMock()), patch(
        "app.get_app_settings", AsyncMock(return_value=settings)
    ), patch("app.ensure_pipeline_catalog", AsyncMock(side_effect=SQLAlchemyError("skip"))), patch(
        "app.get_secret_value", side_effect=_secret
    ):
        response = await get_config(db)

    assert response.secrets_status["HOMEBOX_URL"] == "http://example.test"
    assert response.secrets_status["OPENROUTER_API_KEY"] == "********"
    assert response.custom_pipelines == []


@pytest.mark.asyncio
async def test_update_config_persists_settings_models_and_secret_values():
    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[_Result(None), _Result(None)]),
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

    with patch("app.ensure_app_settings_seed", AsyncMock()), patch(
        "app.ensure_pipeline_catalog", AsyncMock()
    ), patch("app.persist_custom_pipelines", AsyncMock()), patch(
        "app.upsert_app_setting", AsyncMock()
    ), patch("app.set_secret_value") as set_secret, patch(
        "app.encrypt_secret", return_value="enc-token"
    ):
        response = await update_config(payload, db)

    assert response["success"] is True
    assert db.commit.await_count == 1
    assert db.add.call_count >= 2
    set_secret.assert_called_once_with("OPENROUTER_API_KEY", "token-123")


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
