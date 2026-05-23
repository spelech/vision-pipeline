import pytest
import asyncio
from unittest.mock import MagicMock, patch
from services.homebox import HomeboxService
from services.mealie import MealieService

@pytest.mark.asyncio
async def test_homebox_execution():
    """Test Homebox service execution flow."""
    service = HomeboxService()
    service.api_key = "test_key"
    
    data = {
        "product_name": "Test Item",
        "brand": "Test Brand",
        "quantity": 2,
        "description": "A test description"
    }

    with patch("requests.post") as mock_post, \
         patch("requests.put") as mock_put, \
         patch.object(service, "find_or_create_location", return_value="loc_123"):
        
        # Mock item creation
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "item_abc"}
        
        # Mock update
        mock_put.return_value.status_code = 200
        
        result = await service.execute(data)
        
        assert result["success"] is True
        assert result["item_id"] == "item_abc"
        assert mock_post.called
        assert mock_put.called

@pytest.mark.asyncio
async def test_concurrent_execution():
    """Test concurrent execution logic in a simulated environment."""
    mock_svc1 = MagicMock()
    mock_svc2 = MagicMock()
    
    async def mock_exec1(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"success": True, "svc": 1}
        
    async def mock_exec2(*args, **kwargs):
        await asyncio.sleep(0.1)
        return {"success": True, "svc": 2}

    mock_svc1.execute = mock_exec1
    mock_svc2.execute = mock_exec2
    
    results = await asyncio.gather(
        mock_svc1.execute({"test": "data"}),
        mock_svc2.execute({"test": "data"})
    )
    
    assert len(results) == 2
    assert results[0]["svc"] == 1
    assert results[1]["svc"] == 2
