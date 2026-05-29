import pytest

from app import (
    build_service_feedback_context,
    extract_search_candidates,
    get_secret_value,
    merge_service_prompt_configs,
    merge_unique_str_lists,
    normalize_prompt_templates,
    normalize_service_prompts,
    set_secret_value,
    get_pipeline,
)


@pytest.mark.feature("config-templates")
def test_normalize_prompt_templates_from_list_and_dict() -> None:
    """Feature: normalize mixed prompt template representations into stable objects."""
    source = [
        {"id": "a", "name": "Template A", "prompt": "Do A"},
        {"name": "Template B", "prompt": "Do B"},
        "ignore-me",
    ]

    normalized = normalize_prompt_templates(source)

    assert len(normalized) == 2
    assert normalized[0]["id"] == "a"
    assert normalized[0]["name"] == "Template A"
    assert normalized[1]["name"] == "Template B"
    assert normalized[1]["prompt"] == "Do B"


@pytest.mark.feature("config-templates")
def test_normalize_prompt_templates_from_mapping() -> None:
    """Feature: convert prompt maps into UI-friendly template arrays."""
    source = {
        "quick_scan": "Summarize this quickly",
        "deep_scan": {"id": "deep", "name": "Deep Scan", "prompt": "Analyze deeply"},
    }

    normalized = normalize_prompt_templates(source)

    assert {item["id"] for item in normalized} == {"quick_scan", "deep"}
    assert any(item["name"] == "Quick Scan" for item in normalized)


@pytest.mark.feature("config-models")
def test_merge_unique_lists() -> None:
    """Feature: collect deduplicated model favorites lists."""
    merged = merge_unique_str_lists(["a", "b"], ["b", "c"], "skip")
    assert merged == ["a", "b", "c"]


@pytest.mark.feature("config-service-prompts")
def test_normalize_and_merge_service_prompts() -> None:
    """Feature: normalize service prompt configs and overlay them onto defaults."""
    source = {
        "homebox": "Prompt A",
        "mealie": {
            "prompt": "Prompt B",
            "model": "qwen/qwen2.5-32b-instruct",
            "enabled": False,
        },
        "unknown": {"prompt": "skip"},
    }

    normalized = normalize_service_prompts(source)
    merged = merge_service_prompt_configs(normalized)

    assert normalized["homebox"]["prompt"] == "Prompt A"
    assert normalized["mealie"]["model"] == "qwen/qwen3-235b-a22b-2507"
    assert normalized["mealie"]["enabled"] is False
    assert "unknown" not in normalized
    assert merged["changedetection"]["service"] == "changedetection"


@pytest.mark.feature("service-feedback-loop")
def test_extract_search_candidates_and_feedback_context() -> None:
    """Feature: derive retailer-weighted candidates for service prompt feedback passes."""
    search_results = [
        {"url": "https://amazon.com/widget-123", "title": "Widget 123", "content": "Great widget"},
        {"url": "https://example.org/blog", "title": "Thoughts", "content": "Random content"},
    ]
    base_data = {"product_name": "Widget 123"}

    candidates = extract_search_candidates(search_results, base_data)
    assert candidates
    assert candidates[0]["url"] == "https://amazon.com/widget-123"

    feedback_context = build_service_feedback_context(
        "changedetection",
        base_data,
        {"search": search_results},
    )
    assert feedback_context["candidate_urls"][0] == "https://amazon.com/widget-123"
    assert "monitor_urls" in feedback_context["required_fields"]


@pytest.mark.feature("config-secrets")
def test_secret_get_set_homebox_username(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: read and write Homebox username env variable."""
    monkeypatch.delenv("HOMEBOX_USERNAME", raising=False)
    assert get_secret_value("HOMEBOX_USERNAME") == ""

    set_secret_value("HOMEBOX_USERNAME", "new@example.com")
    assert get_secret_value("HOMEBOX_USERNAME") == "new@example.com"


@pytest.mark.feature("pipeline-selection")
def test_get_pipeline_uses_composable_when_db_pipeline_exists() -> None:
    """Feature: select composable pipeline when pipeline id exists in DB catalog."""
    pipeline = get_pipeline("my_custom", db_pipeline_exists=True)
    assert pipeline.__class__.__name__ == "ComposablePipeline"


@pytest.mark.feature("pipeline-selection")
def test_get_pipeline_uses_registry_and_default_fallback() -> None:
    """Feature: resolve registered pipeline ids and fallback to default for unknown ids."""
    known = get_pipeline("advanced_playwright")
    unknown = get_pipeline("does_not_exist")

    assert known.__class__.__name__ == "AdvancedPipeline"
    assert unknown.__class__.__name__ == "DefaultPipeline"
