import pytest

from pipelines.advanced import AdvancedPipeline


@pytest.mark.feature("advanced-pipeline-core")
def test_advanced_pipeline_runs_full_search_scrape_refine_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: run advanced pipeline end-to-end with search/scrape/refine context path."""
    monkeypatch.setattr("pipelines.advanced.scan_barcode", lambda image, log_cb=None: None)
    monkeypatch.setattr(
        "pipelines.advanced.vision_identify",
        lambda image, text_description, model=None, log_cb=None: {
            "search_query": "sriracha",
            "product_name": "Sriracha",
            "barcode": "12345",
        },
    )
    monkeypatch.setattr(
        "pipelines.advanced.web_search",
        lambda query, log_cb=None: [{"url": "https://example.com/item", "title": "Example", "snippet": "..."}],
    )
    monkeypatch.setattr(
        "pipelines.advanced.web_scrape",
        lambda best_url, wait_time=2000, log_cb=None: {"title": "Scraped Item", "body": "content"},
    )
    monkeypatch.setattr(
        "pipelines.advanced.data_refine",
        lambda llm_output, context, log_cb=None: {**llm_output, "refined": True},
    )

    pipeline = AdvancedPipeline()
    out = pipeline.run(image=object(), text_description="test", settings={"vision_model": "qwen/x", "scrape_wait_time": 1500})

    assert out["barcode"] == "12345"
    assert out["searxng_results"][0]["url"] == "https://example.com/item"
    assert out["scraped_content"]["title"] == "Scraped Item"
    assert out["llm_output"]["refined"] is True


@pytest.mark.feature("advanced-pipeline-guards")
def test_advanced_pipeline_skips_search_when_query_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: guard search/scrape path when query cannot be trusted."""
    monkeypatch.setattr("pipelines.advanced.scan_barcode", lambda image, log_cb=None: None)
    monkeypatch.setattr(
        "pipelines.advanced.vision_identify",
        lambda image, text_description, model=None, log_cb=None: {
            "search_query": "Unknown",
            "product_name": "Unknown",
        },
    )

    called = {"search": False}

    def _search(*args, **kwargs):
        called["search"] = True
        return []

    monkeypatch.setattr("pipelines.advanced.web_search", _search)

    pipeline = AdvancedPipeline()
    out = pipeline.run(image=object(), text_description="test", settings={})

    assert out["searxng_results"] == []
    assert out["scraped_content"] is None
    assert called["search"] is False


@pytest.mark.feature("advanced-pipeline-guards")
def test_advanced_pipeline_handles_no_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: skip scraping/refine when search returns no candidate URLs."""
    monkeypatch.setattr("pipelines.advanced.scan_barcode", lambda image, log_cb=None: None)
    monkeypatch.setattr(
        "pipelines.advanced.vision_identify",
        lambda image, text_description, model=None, log_cb=None: {
            "search_query": "sriracha",
            "product_name": "Sriracha",
            "barcode": None,
        },
    )
    monkeypatch.setattr("pipelines.advanced.web_search", lambda query, log_cb=None: [])

    called = {"scrape": False, "refine": False}

    def _scrape(*args, **kwargs):
        called["scrape"] = True
        return {}

    def _refine(*args, **kwargs):
        called["refine"] = True
        return {}

    monkeypatch.setattr("pipelines.advanced.web_scrape", _scrape)
    monkeypatch.setattr("pipelines.advanced.data_refine", _refine)

    pipeline = AdvancedPipeline()
    out = pipeline.run(image=object(), text_description="test", settings={})

    assert out["searxng_results"] == []
    assert out["scraped_content"] is None
    assert called["scrape"] is False
    assert called["refine"] is False


@pytest.mark.feature("advanced-pipeline-guards")
def test_advanced_pipeline_uses_barcode_query_and_defaults_without_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: barcode query path should work even when settings are omitted."""
    monkeypatch.setattr("pipelines.advanced.scan_barcode", lambda image, log_cb=None: "9988")
    monkeypatch.setattr(
        "pipelines.advanced.vision_identify",
        lambda image, text_description, model=None, log_cb=None: {"product_name": "Widget"},
    )

    search_queries: list[str] = []

    def _search(query, log_cb=None):
        search_queries.append(query)
        return []

    monkeypatch.setattr("pipelines.advanced.web_search", _search)

    pipeline = AdvancedPipeline()
    out = pipeline.run(image=object(), text_description="test", settings=None)

    assert search_queries == ["9988"]
    assert out["barcode"] == "9988"
