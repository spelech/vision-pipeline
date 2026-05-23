import pytest
from httpx import ASGITransport, AsyncClient
from app import app, pipeline
import io
from PIL import Image

@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_identify_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        img = Image.new('RGB', (100, 100), color=(73, 109, 137))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        img_bytes = buf.getvalue()
        files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
        data = {'text': 'test product', 'rotation': 0, 'mirror': False}
        response = await ac.post("/identify", data=data, files=files)
        assert response.status_code == 200
        assert response.json()["success"] is True

@pytest.mark.asyncio
async def test_add_to_homebox_endpoint(mocker):
    # Mock the homebox adapter methods
    mocker.patch.object(pipeline.homebox, 'find_or_create_location', return_value="loc-123")
    mocker.patch.object(pipeline.homebox, 'create_item', return_value={"id": "item-123"})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "name": "Test Item",
            "description": "Test Desc",
            "location": "Pantry",
            "quantity": 5,
            "unit": "pcs"
        }
        response = await ac.post("/add-to-homebox", json=payload)
        assert response.status_code == 200
        assert response.json()["success"] == {"id": "item-123"}
        
        # Verify mock calls
        pipeline.homebox.find_or_create_location.assert_called_once_with("Pantry")
        pipeline.homebox.create_item.assert_called_once_with(
            "Test Item", "Test Desc", location_id="loc-123", quantity=5, unit="pcs"
        )

@pytest.mark.asyncio
async def test_add_food_to_mealie_endpoint(mocker):
    mocker.patch.object(pipeline.mealie, 'create_food', return_value={"id": "food-123"})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "name": "Apple",
            "description": "Fresh apple",
            "extras": {"in_stock": "true"}
        }
        response = await ac.post("/add-food-to-mealie", json=payload)
        assert response.status_code == 200
        assert response.json()["success"] == {"id": "food-123"}

@pytest.mark.asyncio
async def test_add_to_mealie_shopping_list_endpoint(mocker):
    mocker.patch.object(pipeline.mealie, 'add_shopping_list_item', return_value={"id": "sl-123"})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "name": "Milk",
            "quantity": 2,
            "note": "Whole milk"
        }
        response = await ac.post("/add-to-mealie-shopping-list", json=payload)
        assert response.status_code == 200
        assert response.json()["success"] == {"id": "sl-123"}
