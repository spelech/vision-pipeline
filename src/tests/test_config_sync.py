import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app import app, get_db
from database import ConfigSecret, AppSetting, PipelineDefinition

@pytest.mark.asyncio
async def test_export_config():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    
    # Mock settings
    mock_settings_result = MagicMock()
    mock_settings_result.scalars.return_value.all.return_value = [
        AppSetting(key="prompt_templates", value=[{"id": "t1", "name": "n1", "prompt": "p1"}]),
        AppSetting(key="service_prompts", value={"homebox": {"prompt": "hp1"}})
    ]
    
    # Mock secrets
    mock_secrets_result = MagicMock()
    mock_secrets_result.scalars.return_value.all.return_value = [
        ConfigSecret(key="LLM_API_KEY", encrypted_value="enc_key")
    ]
    
    # Mock pipelines
    mock_pipelines_result = MagicMock()
    mock_pipelines_result.scalars.return_value.all.return_value = []
    
    def side_effect(stmt):
        stmt_str = str(stmt)
        if "app_settings" in stmt_str:
            return mock_settings_result
        if "config_secrets" in stmt_str:
            return mock_secrets_result
        if "pipeline_definitions" in stmt_str:
            return mock_pipelines_result
        return MagicMock()

    mock_session.execute.side_effect = side_effect

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/api/config/export")
            assert response.status_code == 200
            data = response.json()
            assert "prompt_templates" in data
            assert "encrypted_secrets" in data
            assert data["encrypted_secrets"]["LLM_API_KEY"] == "enc_key"
    finally:
        app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_import_config():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    
    import_payload = {
        "prompt_templates": [{"id": "t2", "name": "n2", "prompt": "p2"}],
        "encrypted_secrets": {
            "LLM_API_KEY": "new_enc_key"
        },
        "custom_pipelines": []
    }

    mock_secret_result = MagicMock()
    mock_secret_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_secret_result

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("routes.config_routes.decrypt_secret", return_value="decrypted"):
            with patch("routes.config_routes.upsert_app_setting", new=AsyncMock()) as mock_upsert:
                with patch("routes.config_routes.configure_gmail_auto_sync_scheduler", new=AsyncMock()):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                        response = await ac.post("/api/config/import", json=import_payload)
                        assert response.status_code == 200
                        assert response.json()["success"] is True
                        
                        # Verify settings were upserted
                        mock_upsert.assert_any_call(mock_session, "prompt_templates", import_payload["prompt_templates"])
                        # Verify secret was added to session
                        mock_session.add.assert_called()
                        assert mock_session.commit.called
    finally:
        app.dependency_overrides.pop(get_db, None)
