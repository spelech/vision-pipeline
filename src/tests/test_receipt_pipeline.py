from pipelines.receipt import ReceiptPipeline


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
