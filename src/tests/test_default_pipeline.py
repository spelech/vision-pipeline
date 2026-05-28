import pytest

from pipelines.default import DefaultPipeline


@pytest.mark.feature("default-pipeline-core")
def test_default_pipeline_refines_when_search_has_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: full default pipeline path with query/search/refine."""
    monkeypatch.setattr("pipelines.default.scan_barcode", lambda image, log_cb=None: None)
    monkeypatch.setattr(
        "pipelines.default.vision_identify",
        lambda image, text_description, model=None, prompt=None, log_cb=None: {
            "barcode": "12345",
            "product_name": "Item",
        },
    )
    monkeypatch.setattr("pipelines.default.web_search", lambda query, log_cb=None: [{"url": "https://example.com"}])
    monkeypatch.setattr(
        "pipelines.default.data_refine",
        lambda llm_output, context, model=None, log_cb=None: {**llm_output, "refined": True},
    )

    pipeline = DefaultPipeline()
    out = pipeline.run(image=object(), text_description="desc", settings={"custom_prompt": "x"})

    assert out["barcode"] == "12345"
    assert out["searxng_results"]
    assert out["llm_output"]["refined"] is True


@pytest.mark.feature("default-pipeline-guards")
def test_default_pipeline_skips_search_and_refine_for_unknown_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: unknown query should block search/refine branch."""
    monkeypatch.setattr("pipelines.default.scan_barcode", lambda image, log_cb=None: None)
    monkeypatch.setattr(
        "pipelines.default.vision_identify",
        lambda image, text_description, model=None, prompt=None, log_cb=None: {
            "search_query": "Unknown",
            "product_name": "Unknown",
        },
    )

    calls = {"search": 0, "refine": 0}

    def _search(*args, **kwargs):
        calls["search"] += 1
        return []

    def _refine(*args, **kwargs):
        calls["refine"] += 1
        return {}

    monkeypatch.setattr("pipelines.default.web_search", _search)
    monkeypatch.setattr("pipelines.default.data_refine", _refine)

    pipeline = DefaultPipeline()
    out = pipeline.run(image=object(), text_description="desc", settings=None)

    assert out["searxng_results"] == []
    assert calls["search"] == 0
    assert calls["refine"] == 0


@pytest.mark.feature("default-pipeline-guards")
def test_default_pipeline_handles_missing_image_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: no image means no barcode scan branch but vision still runs."""
    scan_called = {"called": False}

    def _scan(*args, **kwargs):
        scan_called["called"] = True
        return None

    monkeypatch.setattr("pipelines.default.scan_barcode", _scan)
    monkeypatch.setattr(
        "pipelines.default.vision_identify",
        lambda image, text_description, model=None, prompt=None, log_cb=None: {"product_name": "Widget"},
    )
    monkeypatch.setattr("pipelines.default.web_search", lambda query, log_cb=None: [])

    pipeline = DefaultPipeline()
    out = pipeline.run(image=None, text_description="from text only", settings={})

    assert scan_called["called"] is False
    assert out["llm_output"]["product_name"] == "Widget"
