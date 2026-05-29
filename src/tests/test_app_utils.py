import pytest
from types import SimpleNamespace

from app import (
    apply_service_output_feedback_fallbacks,
    build_service_feedback_context,
    extract_search_candidates,
    get_item_base_data,
    get_service_context_from_item,
    get_service_prompt_config,
    get_service_specific_item_data,
    get_secret_value,
    infer_model_provider,
    merge_service_prompt_configs,
    merge_unique_str_lists,
    normalize_app_setting,
    normalize_pipeline_list,
    normalize_pipeline_schema,
    normalize_pipeline_settings,
    normalize_prompt_templates,
    normalize_service_prompts,
    should_run_service_feedback_pass,
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


@pytest.mark.feature("model-provider")
def test_infer_model_provider_handles_known_custom_and_blank() -> None:
    """Feature: infer provider routing from model ids."""
    assert infer_model_provider("google/gemini-2.0-flash-001") == "openrouter"
    assert infer_model_provider("local_model") == "local_model"
    assert infer_model_provider("   ") == "custom"


@pytest.mark.feature("settings-normalization")
def test_normalize_app_setting_routes_by_key() -> None:
    """Feature: route setting normalization to key-specific transformers."""
    assert normalize_app_setting("model_favorites", ["a", "a", 1, "b"]) == ["a", "b"]
    assert normalize_app_setting("image_optimization", {"quality": 80}) == {"quality": 80}
    assert normalize_app_setting("unknown_key", {"raw": True}) == {"raw": True}


@pytest.mark.feature("pipeline-normalization")
def test_normalize_pipeline_schema_settings_and_list_apply_model_aliases() -> None:
    """Feature: normalize legacy model ids in pipeline schema and settings."""
    legacy = "qwen/qwen2.5-72b-instruct"
    expected = "qwen/qwen3-235b-a22b-2507"

    schema = {
        "vision_model": {"default": legacy},
        "refine_model": {"default": legacy},
    }
    normalized_schema = normalize_pipeline_schema(schema)
    assert normalized_schema["vision_model"]["default"] == expected
    assert normalized_schema["refine_model"]["default"] == expected

    settings = normalize_pipeline_settings({"vision_model": legacy, "refine_model": legacy})
    assert settings["vision_model"] == expected
    assert settings["refine_model"] == expected

    normalized_list = normalize_pipeline_list([
        {"id": "x", "schema": schema},
        "skip",
    ])
    assert len(normalized_list) == 1
    assert normalized_list[0]["schema"]["vision_model"]["default"] == expected


@pytest.mark.feature("service-feedback-loop")
def test_service_feedback_gate_and_fallback_population() -> None:
    """Feature: run feedback pass only for supported services and fill URL fallbacks."""
    feedback_context = {
        "candidate_urls": ["https://example.com/a", "https://example.com/b"],
        "retailer_urls": ["https://retailer.example/p"],
    }

    assert should_run_service_feedback_pass("changedetection", feedback_context)
    assert should_run_service_feedback_pass("pricebuddy", feedback_context)
    assert not should_run_service_feedback_pass("homebox", feedback_context)

    refined = apply_service_output_feedback_fallbacks(
        "pricebuddy",
        {"monitor_urls": ["https://existing.example/1"]},
        feedback_context,
    )
    assert refined["product_url"] == "https://retailer.example/p"
    assert "https://existing.example/1" in refined["monitor_urls"]
    assert "https://retailer.example/p" in refined["monitor_urls"]


@pytest.mark.feature("service-prompts")
def test_get_service_prompt_config_overlays_defaults_and_overrides() -> None:
    """Feature: resolve service config from defaults plus stored overrides."""
    config = get_service_prompt_config(
        "homebox",
        {"homebox": {"prompt": "custom prompt", "enabled": False}},
    )
    assert config["service"] == "homebox"
    assert config["prompt"] == "custom prompt"
    assert config["enabled"] is False


@pytest.mark.feature("item-data-projection")
def test_item_data_helpers_project_base_context_and_service_data() -> None:
    """Feature: build item payloads for service preview/execute paths."""
    item = SimpleNamespace(
        user_overrides=None,
        ai_output={
            "llm_output": {"product_name": "Widget", "brand": "ACME"},
            "searxng_results": [{"url": "https://example.com"}],
            "scraped_content": "details",
            "service_outputs": {
                "homebox": {
                    "data": {"storage_location": "Garage"},
                }
            },
            "service_enrichments": {
                "homebox": {"location_id": "123"},
            },
        },
    )

    base = get_item_base_data(item)
    assert base["product_name"] == "Widget"
    assert isinstance(base["searxng_results"], list)

    service_data = get_service_specific_item_data(item, "homebox")
    assert service_data["storage_location"] == "Garage"

    context = get_service_context_from_item(item, "homebox")
    assert isinstance(context["search"], list)
    assert context["service_enrichment"]["location_id"] == "123"
