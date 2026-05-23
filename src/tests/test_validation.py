import pytest
from unittest.mock import MagicMock

def test_pipeline_validation_logic():
    # Mocking the frontend logic behavior
    model_favorites = ["qwen/qwen2.5-vl-72b-instruct", "google/gemini-2.0-flash-001"]
    
    # Case 1: Valid Pipeline
    p_valid = {
        "id": "default",
        "schema": {"vision_model": {"default": "qwen/qwen2.5-vl-72b-instruct"}}
    }
    
    # Frontend logic: isPipelineInvalid()
    selected_pipeline = "default"
    p = p_valid if selected_pipeline == "default" else None
    model = p["schema"]["vision_model"]["default"]
    is_invalid = model not in model_favorites
    assert is_invalid is False

    # Case 2: Invalid Pipeline (Model not in favorites)
    p_invalid = {
        "id": "custom-123",
        "schema": {"vision_model": {"default": "anthropic/claude-3-opus"}}
    }
    selected_pipeline = "custom-123"
    p = p_invalid if selected_pipeline == "custom-123" else None
    model = p["schema"]["vision_model"]["default"]
    is_invalid = model not in model_favorites
    assert is_invalid is True

if __name__ == "__main__":
    test_pipeline_validation_logic()
    print("Validation logic test passed.")
