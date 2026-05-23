import pytest
from unittest.mock import patch, MagicMock
from services.enrichers import PriceBuddyService, ChangeDetectionService

@pytest.mark.asyncio
async def test_pricebuddy_execution():
    service = PriceBuddyService()
    service.api_key = "test_key"
    
    data = {
        "product_name": "Test Product",
        "barcode": "123456789",
        "searxng_results": [{"url": "https://amazon.com/test"}]
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"id": 1, "name": "Test Product"}
        
        result = await service.execute(data)
        
        assert result["success"] is True
        assert result["data"]["id"] == 1
        assert mock_post.called
        # Check payload
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["name"] == "Test Product"
        assert "https://amazon.com/test" in payload["urls"]

@pytest.mark.asyncio
async def test_changedetection_execution():
    service = ChangeDetectionService()
    service.api_key = "test_key"
    
    data = {
        "product_name": "Test Product",
        "product_url": "https://example.com/item"
    }

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {"uuid": "abc-123"}
        
        result = await service.execute(data)
        
        assert result["success"] is True
        assert "abc-123" in str(result["data"])
        assert mock_post.called
        # Check payload
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["url"] == "https://example.com/item"
        assert payload["track_ldjson_price_data"] is True

@pytest.mark.asyncio
async def test_enrichers_pre_enrichment():
    pb_service = PriceBuddyService()
    pb_service.api_key = "test_key"
    cd_service = ChangeDetectionService()
    cd_service.api_key = "test_key"

    with patch("requests.get") as mock_get:
        # Mock PriceBuddy search
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [{"id": 1, "name": "Found"}]
        
        pb_res = await pb_service.get_pre_enrichment({"barcode": "123"})
        assert "existing_product" in pb_res

        # Mock ChangeDetection list
        mock_get.return_value.json.return_value = {"uuid1": {"url": "https://exists.com"}}
        cd_res = await cd_service.get_pre_enrichment({"product_url": "https://exists.com"})
        assert "existing_watch" in cd_res
