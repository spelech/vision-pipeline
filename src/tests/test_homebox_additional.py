from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import requests

from services.homebox import HomeboxService


@pytest.mark.asyncio
async def test_execute_returns_credentials_error_when_no_headers():
    service = HomeboxService()

    with patch.object(service, "_get_headers_async", AsyncMock(return_value=None)):
        result = await service.execute({"product_name": "X"})

    assert result["success"] is False
    assert "credentials" in result["error"].lower()


def test_get_headers_without_credentials_returns_none():
    service = HomeboxService()
    service.username = None
    service.password = None
    assert service.get_headers() is None


def test_get_headers_handles_login_exception():
    service = HomeboxService()
    service.username = "user"
    service.password = "pw"

    with patch(
        "services.homebox.requests.post",
        side_effect=requests.RequestException("login down"),
    ):
        assert service.get_headers() is None


def test_find_or_create_location_existing_and_create_paths():
    service = HomeboxService()
    with patch.object(service, "_get_headers", return_value={"Authorization": "Bearer t"}), patch(
        "services.homebox.requests.get"
    ) as mock_get, patch("services.homebox.requests.post") as mock_post:
        mock_get.return_value.raise_for_status.return_value = None

        mock_get.return_value.json.return_value = [{"id": "loc1", "name": "Pantry"}]
        assert service.find_or_create_location("pantry") == "loc1"

        mock_get.return_value.json.return_value = []
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {"id": "loc2"}
        assert service.find_or_create_location("Freezer") == "loc2"


def test_find_or_create_location_request_exception_returns_none():
    service = HomeboxService()
    with patch.object(service, "_get_headers", return_value={"Authorization": "Bearer t"}), patch(
        "services.homebox.requests.get",
        side_effect=requests.RequestException("down"),
    ):
        assert service.find_or_create_location("Pantry") is None


@pytest.mark.asyncio
async def test_execute_recreates_item_on_404_and_uploads_attachment():
    service = HomeboxService()

    check_404 = MagicMock(status_code=404)
    create_resp = MagicMock()
    create_resp.raise_for_status.return_value = None
    create_resp.json.return_value = {"id": "new-item"}
    update_resp = MagicMock()
    update_resp.raise_for_status.return_value = None
    attach_resp = MagicMock()

    async def _mock_request(method, endpoint, **kwargs):
        if method == "GET" and endpoint.startswith("/items/"):
            return check_404
        if method == "POST" and endpoint == "/items":
            return create_resp
        if method == "PUT" and endpoint.startswith("/items/"):
            return update_resp
        if method == "POST" and endpoint.endswith("/attachments"):
            return attach_resp
        raise AssertionError(f"Unexpected request {method} {endpoint}")

    with patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer t"})), patch.object(
        service, "_request", side_effect=_mock_request
    ), patch.object(service, "find_or_create_location_async", AsyncMock(return_value="loc-1")), patch(
        "services.homebox.os.path.exists", return_value=True
    ), patch("builtins.open", mock_open(read_data=b"img")):
        result = await service.execute(
            {
                "product_name": "Milk",
                "location": "Fridge",
                "notes": "n1",
                "technical_details": "cold",
            },
            image_path="x.jpg",
            external_id="old-id",
        )

    assert result["success"] is True
    assert result["item_id"] == "new-item"


@pytest.mark.asyncio
async def test_execute_handles_request_exception():
    service = HomeboxService()
    with patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer t"})), patch.object(
        service, "_request", side_effect=requests.RequestException("boom")
    ):
        result = await service.execute({"product_name": "Milk"})

    assert result["success"] is False
    assert "boom" in result["error"]


@pytest.mark.asyncio
async def test_get_pre_enrichment_paths():
    service = HomeboxService()

    with patch.object(service, "_get_headers_async", AsyncMock(return_value=None)):
        assert await service.get_pre_enrichment({"product_name": "x"}) == {}

    with patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer t"})):
        assert await service.get_pre_enrichment({}) == {}

    good_resp = MagicMock()
    good_resp.raise_for_status.return_value = None
    good_resp.json.return_value = {"items": [{"id": 1}]}

    with patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer t"})), patch.object(
        service, "_request", AsyncMock(return_value=good_resp)
    ):
        assert await service.get_pre_enrichment({"product_name": "milk"}) == {
            "existing_items": [{"id": 1}]
        }

    with patch.object(service, "_get_headers_async", AsyncMock(return_value={"Authorization": "Bearer t"})), patch.object(
        service,
        "_request",
        AsyncMock(side_effect=requests.RequestException("down")),
    ):
        assert await service.get_pre_enrichment({"product_name": "milk"}) == {}
