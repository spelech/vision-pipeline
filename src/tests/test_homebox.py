import pytest
from unittest.mock import AsyncMock, patch
from services.homebox import HomeboxService

@pytest.mark.asyncio
async def test_homebox_execution_new_item():
    service = HomeboxService()
    service._cached_token = "test-token"
    
    data = {
        "product_name": "Test Homebox Item",
        "quantity": 2,
        "description": "A test item",
        "location": "Pantry"
    }

    with (
        patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer test-token"})),
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("requests.put") as mock_put,
    ):
        # Mock finding location
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{"id": "loc-123", "name": "Pantry"}]
        mock_get.return_value.raise_for_status.return_value = None
        
        # Mock creating item
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": "item-456"}
        mock_post.return_value.raise_for_status.return_value = None
        
        # Mock updating item
        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status.return_value = None

        result = await service.execute(data)
        
        assert result["success"] is True
        assert result["item_id"] == "item-456"
        assert mock_post.called
        assert mock_put.called

@pytest.mark.asyncio
async def test_homebox_execution_update_item():
    service = HomeboxService()
    service._cached_token = "test-token"
    
    data = {
        "product_name": "Updated Item",
        "quantity": 5
    }

    with (
        patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer test-token"})),
        patch("requests.get") as mock_get,
        patch("requests.put") as mock_put,
    ):
        # Mock item exists check
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status.return_value = None
        
        # Mock updating item
        mock_put.return_value.status_code = 200
        mock_put.return_value.raise_for_status.return_value = None

        result = await service.execute(data, external_id="existing-id")
        
        assert result["success"] is True
        assert result["item_id"] == "existing-id"
        assert mock_put.called
        
@pytest.mark.asyncio
async def test_homebox_auth_email_password():
    service = HomeboxService()
    service.username = "test@example.com"
    service.password = "password"
    
    with patch("requests.post") as mock_post:
        mock_post.return_value.ok = True
        mock_post.return_value.json.return_value = {"token": "fake-jwt-token"}
        
        headers = service._get_headers()
        assert headers is not None
        assert headers["Authorization"] == "Bearer fake-jwt-token"
        assert mock_post.called


def test_homebox_get_payload():
    service = HomeboxService()

    payload = service.get_payload(
        {
            "product_name": "Desk Lamp",
            "quantity": "2",
            "description": "LED lamp",
            "location": "Office",
            "brand": "Acme",
            "model_number": "L-42",
            "serial_number": "SN123",
            "purchase_price": "19.99",
            "notes": "Spare bulb included",
            "technical_details": "Warm white",
        }
    )

    assert payload == {
        "name": "Desk Lamp",
        "quantity": 2,
        "description": "LED lamp",
        "location": "Office",
        "manufacturer": "Acme",
        "modelNumber": "L-42",
        "serialNumber": "SN123",
        "purchasePrice": 19.99,
        "notes": "Spare bulb included",
        "technical_details": "Warm white",
    }
