import pytest
import os
from unittest.mock import patch
from PIL import Image

from pipelines.composable import ComposablePipeline

@pytest.fixture
def mock_image():
    # Create a simple 1x1 image for testing
    img = Image.new('RGB', (1, 1), color='red')
    return img

@pytest.fixture
def pipeline():
    return ComposablePipeline()

@patch("pipelines.composable.scan_barcode")
@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.web_search")
@patch("pipelines.composable.web_scrape")
@patch("pipelines.composable.data_refine")
def test_pipeline_respects_custom_order(
    mock_refine, mock_scrape, mock_search, mock_vision, mock_barcode,
    pipeline, mock_image
):
    # Setup mock returns
    mock_barcode.return_value = "123456"
    mock_vision.return_value = {"product_name": "Test Product", "barcode": "123456"}
    mock_search.return_value = [{"url": "http://example.com"}]
    mock_scrape.return_value = "Scraped Text"
    mock_refine.return_value = {"product_name": "Refined Product"}

    # Define a custom sequence: Vision -> Search -> Barcode -> Refine
    # (Note: Barcode is usually first, but we test reordering)
    custom_sequence = ["vision", "search", "barcode", "refine"]
    settings = {"active_nodes": custom_sequence}

    # Track call order using a list
    call_order = []
    mock_barcode.side_effect = lambda *args, **kwargs: call_order.append("barcode") or "123456"
    mock_vision.side_effect = lambda *args, **kwargs: call_order.append("vision") or {"product_name": "Test Product"}
    mock_search.side_effect = lambda *args, **kwargs: call_order.append("search") or []
    mock_refine.side_effect = lambda *args, **kwargs: call_order.append("refine") or {}

    results = pipeline.run(image=mock_image, settings=settings)

    # Verify execution order
    assert call_order == ["vision", "search", "barcode", "refine"]
    assert mock_barcode.called
    assert mock_vision.called
    assert mock_search.called
    assert mock_refine.called

@patch("pipelines.composable.scan_barcode")
@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.web_search")
def test_pipeline_skips_search_if_no_query(
    mock_search, mock_vision, mock_barcode,
    pipeline, mock_image
):
    # If we run Search BEFORE Vision or Barcode, it should skip
    custom_sequence = ["search", "vision"]
    settings = {"active_nodes": custom_sequence}

    # Mock Vision to return data LATER
    mock_vision.return_value = {"product_name": "Found Product"}
    mock_barcode.return_value = None

    results = pipeline.run(image=mock_image, settings=settings)

    # Search should NOT have been called because results['barcode'] and results['llm_output'] were empty at that stage
    assert not mock_search.called
    assert mock_vision.called

@patch("pipelines.composable.web_scrape")
def test_pipeline_skips_scrape_if_no_url(
    mock_scrape, pipeline, mock_image
):
    # Run Scrape in isolation
    settings = {"active_nodes": ["scrape"]}

    results = pipeline.run(image=mock_image, settings=settings)

    assert not mock_scrape.called
    assert results["scraped_content"] is None

@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.data_refine")
def test_double_refinement_pass(
    mock_refine, mock_vision, pipeline, mock_image
):
    # Test a weird case: Vision -> Refine -> Refine
    custom_sequence = ["vision", "refine", "refine"]
    settings = {"active_nodes": custom_sequence}

    mock_vision.return_value = {"product_name": "Initial"}
    mock_refine.return_value = {"product_name": "Refined"}

    results = pipeline.run(image=mock_image, settings=settings)

    assert mock_vision.call_count == 1
    assert mock_refine.call_count == 2
    assert results["llm_output"]["product_name"] == "Refined"


@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.web_search")
def test_pipeline_uses_default_sequence_when_settings_missing(
    mock_search, mock_vision, pipeline, mock_image
):
    mock_vision.return_value = {"product_name": "Widget", "search_query": "widget"}
    mock_search.return_value = []

    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
        results = pipeline.run(image=mock_image, settings=None)

    assert mock_vision.called
    assert mock_search.called
    assert "llm_output" in results


@patch("pipelines.composable.vision_identify")
@patch("pipelines.composable.web_scrape")
def test_pipeline_scrape_uses_product_url_fallback_when_no_search_results(
    mock_scrape, mock_vision, pipeline, mock_image
):
    mock_vision.return_value = {"product_url": "https://example.com/product"}
    mock_scrape.return_value = {"html": "ok"}

    settings = {"active_nodes": ["vision", "scrape"], "scrape_wait_time": 1111}
    results = pipeline.run(image=mock_image, settings=settings)

    assert mock_scrape.called
    args, kwargs = mock_scrape.call_args
    assert args[0] == "https://example.com/product"
    assert kwargs["wait_time"] == 1111
    assert results["scraped_content"] == {"html": "ok"}
