from pathlib import Path

import pytest

from app import (
    extract_model_favorites,
    get_secret_value,
    load_json_file,
    load_merged_user_config,
    merge_unique_str_lists,
    normalize_prompt_templates,
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
def test_merge_unique_and_extract_model_favorites() -> None:
    """Feature: collect deduplicated configured model favorites from legacy and nested config shapes."""
    merged = merge_unique_str_lists(["a", "b"], ["b", "c"], "skip")
    assert merged == ["a", "b", "c"]

    config_data = {
        "model_favorites": ["openai/gpt-4"],
        "configured_models": ["qwen/qwen2.5-vl-72b-instruct"],
        "model_registry": [
            {"id": "google/gemini-2.0-flash-001"},
            {"id": "qwen/qwen2.5-vl-72b-instruct"},
        ],
    }

    favorites = extract_model_favorites(config_data)
    assert favorites == [
        "openai/gpt-4",
        "qwen/qwen2.5-vl-72b-instruct",
        "google/gemini-2.0-flash-001",
    ]


@pytest.mark.feature("config-files")
def test_load_json_file_handles_missing_invalid_and_nondict(tmp_path: Path) -> None:
    """Feature: safely parse config files while tolerating missing and malformed content."""
    missing_path = tmp_path / "missing.json"
    assert load_json_file(str(missing_path)) == {}

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{oops", encoding="utf-8")
    assert load_json_file(str(bad_path)) == {}

    list_path = tmp_path / "list.json"
    list_path.write_text('[1, 2, 3]', encoding="utf-8")
    assert load_json_file(str(list_path)) == {}


@pytest.mark.feature("config-merge")
def test_load_merged_user_config_merges_and_dedupes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: merge legacy/current user config and dedupe templates and model favorites."""
    legacy = {
        "model_favorites": ["a"],
        "starred_models": ["s1"],
        "prompts": {"base": "Legacy prompt"},
        "image_optimization": {"max_dimension": 1000, "quality": 80},
        "custom_pipelines": [{"id": "legacy-pipeline"}],
    }
    current = {
        "configured_models": ["b"],
        "prompt_templates": [
            {"id": "base", "name": "Base", "prompt": "Current prompt"},
            {"id": "extra", "name": "Extra", "prompt": "Extra prompt"},
        ],
        "custom_pipelines": [{"id": "current-pipeline"}],
    }

    def fake_load(path: str):
        if path.endswith("user_settings.json"):
            return legacy
        if path.endswith("user_config.json"):
            return current
        return {}

    monkeypatch.setattr("app.load_json_file", fake_load)

    merged = load_merged_user_config()

    assert merged["model_favorites"] == ["a", "b"]
    assert merged["starred_models"] == ["s1"]
    assert {tpl["id"] for tpl in merged["prompt_templates"]} == {"base", "extra"}
    assert merged["image_optimization"] == {"max_dimension": 1000, "quality": 80}
    assert merged["custom_pipelines"] == [{"id": "current-pipeline"}]


@pytest.mark.feature("config-secrets")
def test_secret_get_set_homebox_username(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: keep Homebox username/email environment variables in sync."""
    monkeypatch.delenv("HOMEBOX_USERNAME", raising=False)
    monkeypatch.setenv("HOMEBOX_EMAIL", "legacy@example.com")

    assert get_secret_value("HOMEBOX_USERNAME") == "legacy@example.com"

    set_secret_value("HOMEBOX_USERNAME", "new@example.com")
    assert get_secret_value("HOMEBOX_USERNAME") == "new@example.com"


@pytest.mark.feature("pipeline-selection")
def test_get_pipeline_uses_custom_pipeline_when_config_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: select composable pipeline when custom pipeline id is configured."""
    monkeypatch.setattr("app.os.path.exists", lambda p: p == "config/user_config.json")

    class _FakeFile:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return "{}"

    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: _FakeFile())
    monkeypatch.setattr("app.json.load", lambda _f: {"custom_pipelines": [{"id": "my_custom"}]})

    pipeline = get_pipeline("my_custom")
    assert pipeline.__class__.__name__ == "ComposablePipeline"


@pytest.mark.feature("pipeline-selection")
def test_get_pipeline_uses_registry_and_default_fallback() -> None:
    """Feature: resolve registered pipeline ids and fallback to default for unknown ids."""
    known = get_pipeline("advanced_playwright")
    unknown = get_pipeline("does_not_exist")

    assert known.__class__.__name__ == "AdvancedPipeline"
    assert unknown.__class__.__name__ == "DefaultPipeline"
