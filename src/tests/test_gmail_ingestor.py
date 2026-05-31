from services.gmail_ingestor import GmailIngestor
import requests
import pytest
from unittest.mock import MagicMock, patch


def test_extract_line_items_from_message_uses_plain_text_prices():
    message = {
        "subject": "Your order",
        "snippet": "Thanks for your purchase",
        "plain_text": "Widget A $12.99\nSubtotal $12.99\nTax $1.00\nTotal $13.99",
    }

    items = GmailIngestor.extract_line_items_from_message(message)

    assert len(items) >= 1
    assert items[0]["name"].startswith("Widget A")
    assert items[0]["price"] == "$12.99"


def test_extract_line_items_from_message_falls_back_to_subject():
    message = {
        "subject": "Order confirmation #12345",
        "snippet": "",
        "plain_text": "",
    }

    items = GmailIngestor.extract_line_items_from_message(message)

    assert len(items) == 1
    assert items[0]["name"] == "Order confirmation #12345"
    assert items[0]["price"] is None


def test_extract_line_items_from_message_uses_attachment_text_when_plain_text_missing():
    message = {
        "subject": "Receipt",
        "snippet": "",
        "plain_text": "",
    }

    items = GmailIngestor.extract_line_items_from_message(
        message,
        attachment_text="Replacement filter $24.99\nTax $2.00\nTotal $26.99",
    )

    assert len(items) >= 1
    assert items[0]["name"].startswith("Replacement filter")
    assert items[0]["price"] == "$24.99"


def test_ocr_backend_defaults_to_tesseract_for_unknown_values():
    ingestor = GmailIngestor(lambda key: {"GMAIL_OCR_BACKEND": "unknown"}.get(key, ""))

    assert ingestor.ocr_backend() == "tesseract"


def test_ocr_backend_accepts_vision_llm_value():
    ingestor = GmailIngestor(lambda key: {"GMAIL_OCR_BACKEND": "vision_llm"}.get(key, ""))

    assert ingestor.ocr_backend() == "vision_llm"


def test_build_auth_url_and_validation_paths():
    ingestor = GmailIngestor(lambda key: {"GWS_CLIENT_ID": "client-id"}.get(key, ""))

    url = ingestor.build_auth_url("https://example.com/callback", state="abc")
    assert "client_id=client-id" in url
    assert "state=abc" in url

    with pytest.raises(ValueError):
        ingestor.build_auth_url("")

    missing_client = GmailIngestor(lambda _key: "")
    with pytest.raises(ValueError):
        missing_client.build_auth_url("https://example.com/callback")


def test_exchange_code_for_tokens_success_and_missing_configuration():
    ingestor = GmailIngestor(
        lambda key: {
            "GWS_CLIENT_ID": "client-id",
            "GWS_CLIENT_SECRET": "client-secret",
        }.get(key, "")
    )

    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"refresh_token": "r1", "access_token": "a1"}
    with patch("services.gmail_ingestor.requests.post", return_value=response):
        tokens = ingestor.exchange_code_for_tokens("code-1", "https://example.com/callback")
    assert tokens["access_token"] == "a1"

    with pytest.raises(ValueError):
        ingestor.exchange_code_for_tokens("", "https://example.com/callback")
    with pytest.raises(ValueError):
        ingestor.exchange_code_for_tokens("code", "")

    missing = GmailIngestor(lambda _key: "")
    with pytest.raises(ValueError):
        missing.exchange_code_for_tokens("code", "https://example.com/callback")


def test_access_token_api_get_and_download_attachment_paths():
    ingestor = GmailIngestor(
        lambda key: {
            "GWS_CLIENT_ID": "client-id",
            "GWS_CLIENT_SECRET": "client-secret",
            "GWS_REFRESH_TOKEN": "refresh",
        }.get(key, "")
    )

    token_response = MagicMock()
    token_response.raise_for_status.return_value = None
    token_response.json.return_value = {"access_token": "token-123"}

    api_response = MagicMock()
    api_response.raise_for_status.return_value = None
    api_response.json.return_value = {"messages": []}

    with patch("services.gmail_ingestor.requests.post", return_value=token_response), patch(
        "services.gmail_ingestor.requests.get", return_value=api_response
    ):
        payload = ingestor._api_get("messages", {"q": "receipt"})

    assert payload == {"messages": []}

    with patch.object(ingestor, "_api_get", return_value={"data": "YXR0YWNobWVudA"}):
        data = ingestor.download_attachment("msg-1", "att-1")
    assert data == b"attachment"

    with pytest.raises(ValueError):
        ingestor.download_attachment("", "att")
    with pytest.raises(ValueError):
        ingestor.download_attachment("msg", "")


def test_search_receipts_get_message_and_skip_failed_detail():
    ingestor = GmailIngestor(lambda _key: "")

    listing = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    detailed_1 = {
        "id": "m1",
        "threadId": "t1",
        "snippet": "Thanks",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Receipt"},
                {"name": "From", "value": "shop@example.com"},
            ],
            "parts": [],
        },
    }

    def _api_get_side_effect(path, params=None):
        if path == "messages":
            return listing
        if path == "messages/m1":
            return detailed_1
        if path == "messages/m2":
            raise requests.RequestException("down")
        if path == "messages/m3":
            return detailed_1
        raise AssertionError(path)

    with patch.object(ingestor, "_api_get", side_effect=_api_get_side_effect):
        result = ingestor.search_receipts("receipt", 10)
        message = ingestor.get_message("m3")

    assert result["message_count"] == 1
    assert result["messages"][0]["subject"] == "Receipt"
    assert message["from"] == "shop@example.com"


def test_extract_attachment_text_pdf_image_and_fallback_paths():
    secrets = {
        "GMAIL_OCR_BACKEND": "vision_llm",
        "OPENROUTER_API_KEY": "key",
    }
    ingestor = GmailIngestor(lambda key: secrets.get(key, ""))

    with patch.object(ingestor, "download_attachment", return_value=b"pdf"), patch.object(
        ingestor, "_extract_text_from_pdf_bytes", return_value="PDF TEXT"
    ):
        text = ingestor.extract_attachment_text(
            "msg-1",
            {"attachment_id": "a1", "filename": "receipt.pdf", "mime_type": "application/pdf"},
        )
    assert text == "PDF TEXT"

    with patch.object(ingestor, "download_attachment", return_value=b"img"), patch.object(
        ingestor,
        "_extract_text_with_vision_llm",
        side_effect=ValueError("bad model"),
    ), patch.object(ingestor, "_extract_text_with_tesseract", return_value="OCR TEXT"):
        image_text = ingestor.extract_attachment_text(
            "msg-1",
            {"attachment_id": "a2", "filename": "receipt.jpg", "mime_type": "image/jpeg"},
        )
    assert image_text == "OCR TEXT"

    with patch.object(ingestor, "download_attachment", return_value=b"raw"):
        assert (
            ingestor.extract_attachment_text(
                "msg-1",
                {"attachment_id": "a3", "filename": "notes.txt", "mime_type": "text/plain"},
            )
            == ""
        )
