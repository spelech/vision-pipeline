import pytest
from unittest.mock import patch
import requests
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


@pytest.mark.asyncio
async def test_pricebuddy_execute_without_api_key_returns_error():
    service = PriceBuddyService()
    service.api_key = None

    result = await service.execute({"product_name": "No Key"})
    assert result == {"success": False, "error": "No API Key"}


def test_pricebuddy_payload_falls_back_to_top_results_and_default_tag():
    service = PriceBuddyService()
    payload = service.get_payload(
        {
            "name": "Fallback Product",
            "searxng_results": [
                {"url": "https://docs.example.com/a"},
                {"url": "https://blog.example.com/b"},
                {"url": "https://shop.example.com/c"},
                {"url": "https://shop.example.com/d"},
            ],
        }
    )

    assert payload["name"] == "Fallback Product"
    assert payload["urls"] == [
        "https://docs.example.com/a",
        "https://blog.example.com/b",
        "https://shop.example.com/c",
    ]
    assert payload["tags"] == ["Vision Pipeline"]


def test_pricebuddy_payload_includes_monitor_urls_when_present():
    service = PriceBuddyService()
    payload = service.get_payload(
        {
            "product_name": "Smart Plug",
            "product_url": "https://bestbuy.com/smart-plug",
            "monitor_urls": [
                "https://target.com/smart-plug",
                "https://walmart.com/smart-plug",
            ],
        }
    )

    assert payload["urls"] == [
        "https://bestbuy.com/smart-plug",
        "https://target.com/smart-plug",
        "https://walmart.com/smart-plug",
    ]


@pytest.mark.asyncio
async def test_changedetection_execute_missing_url_returns_error():
    service = ChangeDetectionService()
    service.api_key = "k"

    result = await service.execute({"product_name": "Missing URL"})
    assert result == {"success": False, "error": "No URL to monitor"}


@pytest.mark.asyncio
async def test_changedetection_pre_enrichment_no_key_or_no_url_short_circuits():
    service = ChangeDetectionService()
    service.api_key = None
    assert await service.get_pre_enrichment({"product_url": "https://example.com"}) == {}

    service.api_key = "k"
    assert await service.get_pre_enrichment({}) == {}


@pytest.mark.asyncio
async def test_pricebuddy_execute_request_exception_returns_error():
    service = PriceBuddyService()
    service.api_key = "test_key"

    with patch("requests.post", side_effect=requests.RequestException("boom")):
        result = await service.execute({"product_name": "x"})
        assert result["success"] is False
        assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_pricebuddy_pre_enrichment_name_query_and_exception_paths():
    service = PriceBuddyService()
    service.api_key = "test_key"

    with patch("requests.get") as mock_get:
        barcode_resp = type("Resp", (), {"status_code": 200, "json": lambda self: []})()
        name_resp = type("Resp", (), {"status_code": 200, "json": lambda self: [{"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}]})()
        mock_get.side_effect = [barcode_resp, name_resp]

        result = await service.get_pre_enrichment({"barcode": "123", "name": "Widget"})
        assert result == {"existing_matches": [{"id": 2}, {"id": 3}, {"id": 4}]}

    with patch("requests.get", side_effect=requests.RequestException("offline")):
        assert await service.get_pre_enrichment({"barcode": "123"}) == {}


@pytest.mark.asyncio
async def test_changedetection_execute_request_exception_returns_error():
    service = ChangeDetectionService()
    service.api_key = "test_key"

    with patch("requests.post", side_effect=requests.RequestException("bad")):
        result = await service.execute({"product_url": "https://example.com"})
        assert result["success"] is False
        assert "bad" in result["error"]


@pytest.mark.asyncio
async def test_changedetection_pre_enrichment_no_matching_watch_and_exception_paths():
    service = ChangeDetectionService()
    service.api_key = "test_key"

    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "id-1": {"url": "https://other.example.com"}
        }
        result = await service.get_pre_enrichment({"product_url": "https://target.example.com"})
        assert result == {}

    with patch("requests.get", side_effect=requests.RequestException("timeout")):
        result = await service.get_pre_enrichment({"product_url": "https://target.example.com"})
        assert result == {}


@pytest.mark.asyncio
async def test_changedetection_execute_supports_multiple_monitor_urls():
    service = ChangeDetectionService()
    service.api_key = "test_key"

    with patch("requests.post") as mock_post:
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.side_effect = [
            {"uuid": "watch-1"},
            {"uuid": "watch-2"},
        ]

        result = await service.execute(
            {
                "product_name": "Widget",
                "product_url": "https://amazon.com/widget",
                "monitor_urls": ["https://target.com/widget"],
            }
        )

        assert result["success"] is True
        assert result["note"] == "Monitoring 2 URLs"
        assert len(result["data"]["created"]) == 2
        assert mock_post.call_count == 2


def test_enrichers_names():
    assert PriceBuddyService().name == "pricebuddy"
    assert ChangeDetectionService().name == "changedetection"


@pytest.mark.asyncio
async def test_enrichers_pre_enrichment_no_headers():
    pb = PriceBuddyService()
    pb.api_key = None
    assert await pb.get_pre_enrichment({"barcode": "1"}) == {}

    cd = ChangeDetectionService()
    cd.api_key = None
    assert await cd.get_pre_enrichment({"product_url": "https://x"}) == {}


@pytest.mark.asyncio
async def test_pricebuddy_pre_enrichment_name_non_200():
    service = PriceBuddyService()
    service.api_key = "k"
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 500
        res = await service.get_pre_enrichment({"name": "Widget"})
        assert res == {}


@pytest.mark.asyncio
async def test_changedetection_execute_no_api_key():
    service = ChangeDetectionService()
    service.api_key = None
    res = await service.execute({"product_url": "https://x"})
    assert res["success"] is False
    assert "no api key" in res["error"].lower()


@pytest.mark.asyncio
async def test_changedetection_execute_multi_fail():
    service = ChangeDetectionService()
    service.api_key = "k"
    with patch("requests.post", side_effect=requests.RequestException("conn error")):
        res = await service.execute({
            "product_name": "x",
            "product_url": "https://a.com",
            "monitor_urls": ["https://b.com"]
        })
        assert res["success"] is False
        assert "failed to create watches" in res["error"].lower()


@pytest.mark.asyncio
async def test_changedetection_pre_enrichment_non_200():
    service = ChangeDetectionService()
    service.api_key = "k"
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 404
        res = await service.get_pre_enrichment({"product_url": "https://a.com"})
        assert res == {}


def test_changedetection_get_payload():
    service = ChangeDetectionService()
    payload = service.get_payload({"product_name": "x"}, "https://x.com")
    assert payload["url"] == "https://x.com"
    assert payload["title"] == "x"


def test_pricebuddy_payload_uses_urls_override_directly():
    service = PriceBuddyService()
    payload = service.get_payload({
        "urls": ["https://my-override.com/a", "https://my-override.com/b"],
        "searxng_results": [{"url": "https://ignore.me"}]
    })
    assert payload["urls"] == ["https://my-override.com/a", "https://my-override.com/b"]


