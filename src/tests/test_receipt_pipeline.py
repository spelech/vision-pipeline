from pipelines.receipt import ReceiptPipeline
import os
from unittest.mock import patch


def test_receipt_pipeline_identity_and_defaults():
    assert ReceiptPipeline.get_id() == "receipt"
    assert ReceiptPipeline.get_name() == "Receipt Pipeline"

    schema = ReceiptPipeline.get_settings_schema()
    assert schema["active_nodes"]["default"] == [
        "upc_lookup",
        "vision",
        "search",
        "scrape",
        "refine",
    ]
    assert "receipt line items" in schema["vision_prompt"]["default"].lower()
    assert "ocr output" in schema["refine_prompt"]["default"].lower()


@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.upc_lookup_node")
@patch("pipelines.composable.web_search")
@patch("pipelines.composable.web_scrape")
@patch("pipelines.composable.data_refine")
def test_receipt_pipeline_node_interactions(
    mock_refine,
    mock_scrape,
    mock_search,
    mock_upc_lookup,
    mock_vision,
):
    pipeline = ReceiptPipeline()

    mock_vision.return_value = {
        "product_name": "Milk",
        "barcode": "012345678905",
        "search_query": "milk whole",
        "is_food": True,
    }
    mock_upc_lookup.return_value = {"product_name": "Milk Whole 1L"}
    mock_search.return_value = [{"url": "https://example.com/milk"}]
    mock_scrape.return_value = "product page"
    mock_refine.return_value = {"product_name": "Milk Whole 1L (Refined)"}

    settings = {
        "active_nodes": ["vision", "upc_lookup", "search", "scrape", "refine"],
        "search_results_limit": 3,
        "scrape_wait_time": 1500,
        "refine_model": "qwen/qwen3-235b-a22b-2507",
    }

    results = pipeline.run(image=object(), settings=settings)

    mock_upc_lookup.assert_called_once_with(
        "012345678905",
        is_food=True,
        log_cb=None,
    )
    mock_search.assert_called_once_with(
        "012345678905",
        max_results=3,
        log_cb=None,
    )
    mock_scrape.assert_called_once_with(
        "https://example.com/milk",
        wait_time=1500,
        log_cb=None,
    )
    mock_refine.assert_called_once()
    assert results["llm_output"]["product_name"] == "Milk Whole 1L (Refined)"


@patch("pipelines.composable.upc_lookup_node")
@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.web_search")
def test_receipt_pipeline_default_sequence_skips_initial_upc_without_barcode(
    mock_search,
    mock_vision,
    mock_upc_lookup,
):
    pipeline = ReceiptPipeline()

    mock_vision.return_value = {
        "product_name": "Bread",
        "search_query": "bakery bread",
    }
    mock_search.return_value = [{"url": "https://example.com/bread"}]

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
        pipeline.run(image=object(), settings=None)

    # In the default receipt node order, UPC runs before vision.
    # With no scanner result, it should skip UPC at that stage.
    mock_upc_lookup.assert_not_called()
    mock_search.assert_called_once_with(
        "bakery bread",
        max_results=7,
        log_cb=None,
    )
