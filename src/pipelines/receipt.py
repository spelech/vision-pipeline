from .composable import ComposablePipeline


class ReceiptPipeline(ComposablePipeline):
    """Dedicated receipt processing pipeline with OCR-friendly defaults."""

    @classmethod
    def get_id(cls) -> str:
        return "receipt"

    @classmethod
    def get_name(cls) -> str:
        return "Receipt Pipeline"

    @classmethod
    def get_settings_schema(cls) -> dict:
        schema = super().get_settings_schema()
        schema["active_nodes"]["default"] = [
            "upc_lookup",
            "vision",
            "search",
            "scrape",
            "refine",
        ]
        schema["vision_prompt"]["default"] = (
            "You are extracting receipt line items and merchant context. "
            "Prioritize item names, unit quantities, barcodes, vendor clues, "
            "and per-line pricing. Return strict JSON metadata suitable for "
            "inventory creation and downstream refinement."
        )
        schema["refine_prompt"]["default"] = (
            "Refine receipt metadata using OCR output, UPC lookup, search, "
            "and scraped merchant context. Preserve the original JSON schema, "
            "keep item-level fields intact, and only correct values when the "
            "evidence is strong."
        )
        return schema
