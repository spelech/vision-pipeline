import types
from unittest.mock import MagicMock, patch

import pytest
import requests
from openai import OpenAIError
from PIL import Image

from pipelines import nodes


class _Barcode:
    def __init__(self, value: bytes):
        self.data = value


def _mk_image(mode: str = "RGB"):
    return Image.new(mode, (10, 10), color="white")


def test_scan_barcode_none_image_returns_none():
    assert nodes.scan_barcode(None) is None


def test_scan_barcode_raw_success():
    img = _mk_image()
    with patch("pipelines.nodes.decode", return_value=[_Barcode(b"123")]):
        assert nodes.scan_barcode(img) == "123"


def test_scan_barcode_grayscale_and_contrast_fallbacks():
    img = _mk_image()
    with patch(
        "pipelines.nodes.decode",
        side_effect=[[], [_Barcode(b"456")]],
    ):
        assert nodes.scan_barcode(img) == "456"

    with patch(
        "pipelines.nodes.decode",
        side_effect=[[], [], [_Barcode(b"789")]],
    ):
        assert nodes.scan_barcode(img) == "789"


def test_scan_barcode_exception_logs_and_returns_none():
    img = _mk_image()
    logs = []
    with patch("pipelines.nodes.decode", side_effect=RuntimeError("decode error")):
        assert nodes.scan_barcode(img, logs.append) is None
    assert any("[Node: Barcode] Error" in entry for entry in logs)


def test_vision_identify_success_parses_json_from_response():
    mock_client = MagicMock()
    content = "prefix {\"product_name\":\"Milk\",\"is_food\":true} suffix"
    mock_client.chat.completions.create.return_value = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
    )

    with patch("pipelines.nodes.get_client", return_value=mock_client):
        result = nodes.vision_identify(
            _mk_image("RGBA"),
            text_description="from fridge",
            model="x-test",
        )

    assert result["product_name"] == "Milk"
    assert result["is_food"] is True


def test_vision_identify_error_returns_error_object():
    logs = []
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("client boom")

    with patch("pipelines.nodes.get_client", return_value=mock_client):
        result = nodes.vision_identify(_mk_image(), log_cb=logs.append)

    assert "error" in result
    assert "client boom" in result["error"]
    assert any("[Node: Vision] Calling" in entry for entry in logs)


def test_vision_identify_client_init_error_returns_error_object():
    logs = []
    with patch(
        "pipelines.nodes.get_client",
        side_effect=OpenAIError("Missing credentials"),
    ):
        result = nodes.vision_identify(_mk_image(), log_cb=logs.append)

    assert "error" in result
    assert "Missing credentials" in result["error"]
    assert any("[Node: Vision] Error" in entry for entry in logs)


def test_web_search_and_scrape_paths():
    with patch.dict("os.environ", {}, clear=True):
        assert nodes.web_search("abc") == []

    with patch.dict("os.environ", {"SEARXNG_URL": "http://searxng"}, clear=False), patch(
        "pipelines.nodes.requests.get"
    ) as mock_get:
        mock_get.return_value.json.return_value = {
            "results": [
                {"title": "T1", "url": "u1", "content": "s1"},
                {"title": "T2", "url": "u2", "content": "s2"},
            ]
        }
        got = nodes.web_search("milk")
        assert got[0]["title"] == "T1"
        assert got[1]["url"] == "u2"

    with patch(
        "pipelines.nodes.requests.get",
        side_effect=requests.RequestException("net"),
    ):
        assert nodes.web_search("milk") == []

    long_text = "x" * 12050
    with patch("pipelines.nodes.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"success": True, "text": long_text}
        assert len(nodes.web_scrape("http://example.com")) == 10000

    with patch("pipelines.nodes.requests.post") as mock_post:
        mock_post.return_value.json.return_value = {"success": False}
        assert nodes.web_scrape("http://example.com") is None

    with patch(
        "pipelines.nodes.requests.post",
        side_effect=requests.RequestException("boom"),
    ):
        assert nodes.web_scrape("http://example.com") is None


def test_data_refine_success_and_fallback():
    current = {"name": "old"}
    context = {"source": "web"}

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = types.SimpleNamespace(
        choices=[
            types.SimpleNamespace(
                message=types.SimpleNamespace(content='{"name":"new","score":10}')
            )
        ]
    )

    with patch("pipelines.nodes.get_client", return_value=mock_client):
        refined = nodes.data_refine(current, context)
    assert refined["name"] == "new"

    mock_error_client = MagicMock()
    mock_error_client.chat.completions.create.side_effect = RuntimeError(
        "refine down"
    )
    with patch("pipelines.nodes.get_client", return_value=mock_error_client):
        assert nodes.data_refine(current, context) == current


def test_data_refine_client_init_error_returns_current_data():
    current = {"name": "old"}
    context = {"source": "web"}
    logs = []

    with patch(
        "pipelines.nodes.get_client",
        side_effect=OpenAIError("Missing credentials"),
    ):
        refined = nodes.data_refine(current, context, log_cb=logs.append)

    assert refined == current
    assert any("[Node: Refine] Failed" in entry for entry in logs)


def test_upc_lookup_node_food_and_generic_paths():
    food_payload = {
        "product": {
            "product_name": "Whole Milk",
            "brands": "Farm Co",
            "categories": "Dairy",
            "generic_name": "Milk",
        }
    }
    generic_payload = {
        "items": [
            {
                "title": "Widget",
                "brand": "Acme",
                "category": "Tools",
                "description": "Handy widget",
                "offers": [{"link": "https://example.com/widget"}],
            }
        ]
    }

    with patch("pipelines.nodes.requests.get") as mock_get:
        mock_get.return_value.json.return_value = food_payload
        mock_get.return_value.raise_for_status.return_value = None
        food = nodes.upc_lookup_node("123", is_food=True)

    assert food["source"] == "openfoodfacts"
    assert food["product_name"] == "Whole Milk"

    with patch("pipelines.nodes.requests.get") as mock_get:
        mock_get.return_value.json.return_value = generic_payload
        mock_get.return_value.raise_for_status.return_value = None
        generic = nodes.upc_lookup_node("456", is_food=False)

    assert generic["source"] == "upcitemdb"
    assert generic["product_name"] == "Widget"


def test_upc_lookup_node_handles_request_failure():
    with patch("pipelines.nodes.requests.get", side_effect=requests.RequestException("down")):
        result = nodes.upc_lookup_node("123", is_food=True)

    assert result == {}


def test_gmail_search_node_success_and_failure_paths():
    token_resp = MagicMock()
    token_resp.raise_for_status.return_value = None
    token_resp.json.return_value = {"access_token": "abc"}

    listing_resp = MagicMock()
    listing_resp.raise_for_status.return_value = None
    listing_resp.json.return_value = {"messages": [{"id": "m1", "threadId": "t1"}]}

    with patch.dict(
        "os.environ",
        {
            "GWS_CLIENT_ID": "id",
            "GWS_CLIENT_SECRET": "secret",
            "GWS_REFRESH_TOKEN": "refresh",
        },
        clear=False,
    ), patch("pipelines.nodes.requests.post", return_value=token_resp), patch(
        "pipelines.nodes.requests.get", return_value=listing_resp
    ):
        rows = nodes.gmail_search_node("subject:receipt")

    assert rows == [{"id": "m1", "thread_id": "t1"}]

    with patch.dict("os.environ", {}, clear=True):
        assert nodes.gmail_search_node("subject:receipt") == []
