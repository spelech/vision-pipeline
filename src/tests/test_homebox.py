import pytest
from unittest.mock import patch
from services.homebox import HomeboxService

@pytest.mark.asyncio
async def test_homebox_execution_new_item():
    service = HomeboxService()
    service.api_key = "test_key"
    
    data = {
        "product_name": "Test Homebox Item",
        "quantity": 2,
        "description": "A test item",
        "location": "Pantry"
    }

    with patch("requests.get") as mock_get, patch("requests.post") as mock_post, patch("requests.put") as mock_put:
        # Mock finding location
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{"id": "loc-123", "name": "Pantry"}]
        
        # Mock creating item
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "item-456"}
        
        # Mock updating item
        mock_put.return_value.status_code = 200

        result = await service.execute(data)
        
        assert result["success"] is True
        assert result["item_id"] == "item-456"
        assert mock_post.called
        assert mock_put.called

@pytest.mark.asyncio
async def test_homebox_execution_update_item():
    service = HomeboxService()
    service.api_key = "test_key"
    
    data = {
        "product_name": "Updated Item",
        "quantity": 5
    }

    with patch("requests.get") as mock_get, patch("requests.put") as mock_put:
        # Mock item exists check
        mock_get.return_value.status_code = 200
        
        # Mock updating item
        mock_put.return_value.status_code = 200

        result = await service.execute(data, external_id="existing-id")
        
        assert result["success"] is True
        assert result["item_id"] == "existing-id"
        assert mock_put.called
        
@pytest.mark.asyncio
async def test_homebox_auth_email_password():
    service = HomeboxService()
    service.api_key = None
    service.email = "test@example.com"
    service.password = "password"
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"token": "fake-jwt-token"}
        
        headers = service._get_headers()
        assert headers is not None
        assert headers["Authorization"] == "Bearer fake-jwt-token"
        assert mock_post.called
