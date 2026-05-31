from unittest.mock import MagicMock, patch

import pytest
import requests

from services.receipt_wrangler import ReceiptWranglerClient


def _secret_getter(key: str) -> str:
    data = {
        "RECEIPT_WRANGLER_URL": "https://rw.example.com",
        "RECEIPT_WRANGLER_API_KEY": "rw-key",
        "RECEIPT_WRANGLER_GROUP_ID": "1",
    }
    return data.get(key, "")


def _token_secret_getter(key: str) -> str:
    data = {
        "RECEIPT_WRANGLER_URL": "https://rw.example.com",
        "RECEIPT_WRANGLER_API_TOKEN": "rw-token",
        "RECEIPT_WRANGLER_GROUP_ID": "1",
    }
    return data.get(key, "")


def test_get_pending_receipts_list_and_wrapped_payloads():
    client = ReceiptWranglerClient(_secret_getter)

    direct = MagicMock()
    direct.raise_for_status.return_value = None
    direct.json.return_value = [{"id": "r1"}]

    wrapped = MagicMock()
    wrapped.raise_for_status.return_value = None
    wrapped.json.return_value = {"receipts": [{"id": "r2"}]}

    with patch("services.receipt_wrangler.requests.get", side_effect=[direct, wrapped]):
        assert client.get_pending_receipts() == [{"id": "r1"}]
        assert client.get_pending_receipts() == [{"id": "r2"}]


def test_download_receipt_image_requires_id_and_returns_bytes():
    client = ReceiptWranglerClient(_secret_getter)
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.content = b"img"

    with pytest.raises(ValueError):
        client.download_receipt_image("")

    with patch("services.receipt_wrangler.requests.get", return_value=response):
        assert client.download_receipt_image("img-1") == b"img"


def test_update_receipt_status_json_and_fallback_paths():
    client = ReceiptWranglerClient(_secret_getter)

    json_resp = MagicMock()
    json_resp.raise_for_status.return_value = None
    json_resp.json.return_value = {"ok": True}

    non_json_resp = MagicMock()
    non_json_resp.raise_for_status.return_value = None
    non_json_resp.json.side_effect = ValueError("not json")

    with patch("services.receipt_wrangler.requests.patch", side_effect=[json_resp, non_json_resp]):
        assert client.update_receipt_status("r-1", "RESOLVED") == {"ok": True}
        assert client.update_receipt_status("r-2", "OPEN") == {
            "success": True,
            "receipt_id": "r-2",
            "status": "OPEN",
        }


def test_quick_scan_empty_bytes_raises_error():
    client = ReceiptWranglerClient(_secret_getter)

    with pytest.raises(ValueError):
        client.quick_scan_attachment(b"", "receipt.jpg")

    with patch(
        "services.receipt_wrangler.requests.post",
        side_effect=requests.RequestException("down"),
    ):
        with pytest.raises(requests.RequestException):
            client.quick_scan_attachment(b"123", "receipt.jpg")


def test_receipt_wrangler_uses_api_token_fallback_when_api_key_missing():
    client = ReceiptWranglerClient(_token_secret_getter)
    assert client.configured() is True

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"ok": True}

    with patch("services.receipt_wrangler.requests.post", return_value=response) as post_mock:
        client.quick_scan_attachment(b"123", "receipt.jpg")

    headers = post_mock.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer rw-token"