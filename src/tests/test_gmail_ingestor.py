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
