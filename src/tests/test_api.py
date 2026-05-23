import pytest
import io
import json
import uuid
import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Mock StaticFiles and os.makedirs before importing app
with patch("os.makedirs"):
    with patch("os.path.exists", return_value=True):
        with patch("fastapi.staticfiles.StaticFiles", return_value=MagicMock()):
            from app import app, SERVICES
from pipelines import get_pipeline

from httpx import ASGITransport, AsyncClient
from PIL import Image

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
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
            
            files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
            data = {'text': 'test context', 'rotation': 0, 'mirror': False}
            
            response = await ac.post("/identify", data=data, files=files)
            
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
                response = await ac.get("/locations")
                assert response.status_code == 200
                assert response.json()["success"] is True
                assert response.json()["locations"][0]["name"] == "Pantry"

@pytest.mark.asyncio
async def test_preview_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        data = {"product_name": "Test"}
        response = await ac.post("/preview/homebox", json=data)
        assert response.status_code == 200
        assert "payload" in response.json()
        
        # Test non-existent service
        response = await ac.post("/preview/invalid", json=data)
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
            response = await ac.post("/execute", json=payload)
            
            assert response.status_code == 200
            assert response.json()["results"]["homebox"]["success"] is True

@pytest.mark.asyncio
async def test_batch_upload_endpoint():
    with patch("app.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
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
                    
                    response = await ac.post("/batch-upload", data=data, files=files)
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
            response = await ac.post("/bulk-approve", json=payload)
            assert response.status_code == 200
            assert 1 in response.json()["success"]
