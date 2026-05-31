from services.gmail_ingestor import GmailIngestor


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
