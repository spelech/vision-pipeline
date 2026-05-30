import logging
from .base import BasePipeline
from .nodes import scan_barcode, vision_identify, web_search, data_refine

logger = logging.getLogger("DefaultPipeline")


class DefaultPipeline(BasePipeline):
    """
    The standard 4-stage pipeline using reusable nodes.
    """

    @classmethod
    def get_id(cls) -> str:
        return "default"

    @classmethod
    def get_name(cls) -> str:
        return "Default Vision Pipeline"

    @classmethod
    def get_settings_schema(cls) -> dict:
        return {
            "vision_model": {
                "type": "string",
                "label": "Vision Model",
                "default": "qwen/qwen2.5-vl-72b-instruct",
                "options": [
                    "qwen/qwen2.5-vl-72b-instruct",
                    "google/gemini-2.0-flash-001"]},
            "refine_model": {
                "type": "string",
                "label": "Refine Model",
                "default": "qwen/qwen3-235b-a22b-2507",
                "options": [
                    "qwen/qwen3-235b-a22b-2507",
                    "qwen/qwen2.5-vl-72b-instruct",
                    "google/gemini-2.0-flash-001",
                    "anthropic/claude-3.5-sonnet"]},
            "custom_prompt": {
                "type": "textarea",
                "label": "System Prompt Override",
                "default": (
                    "Analyze the image and return strict JSON product metadata "
                    "for inventory ingestion."
                )},
            "vision_prompt": {
                "type": "textarea",
                "label": "Vision Prompt",
                "default": (
                    "Analyze the image and return strict JSON product metadata "
                    "for inventory ingestion."
                )
            },
            "refine_prompt": {
                "type": "textarea",
                "label": "Refine Prompt",
                "default": (
                    "Refine the metadata using search results and preserve "
                    "the existing JSON schema."
                )
            },
            "search_results_limit": {
                "type": "number",
                "label": "Search Results Limit",
                "default": 7
            }}

    def run(
            self,
            image=None,
            text_description=None,
            settings=None,
            log_cb=None):
        results = {"barcode": None, "llm_output": None, "searxng_results": []}

        # 1. Barcode
        if image:
            results["barcode"] = scan_barcode(image, log_cb=log_cb)

        # 2. Vision
        model = settings.get(
            "vision_model",
            "qwen/qwen2.5-vl-72b-instruct") if settings else "qwen/qwen2.5-vl-72b-instruct"
        prompt = None
        if settings:
            prompt = settings.get("vision_prompt") or settings.get("custom_prompt")
        results["llm_output"] = vision_identify(
            image, text_description, model=model, prompt=prompt, log_cb=log_cb)

        # Sync barcode
        if not results["barcode"]:
            results["barcode"] = results["llm_output"].get("barcode")

        # 3. Search
        query = results["barcode"] or results["llm_output"].get(
            "search_query") or results["llm_output"].get("product_name")
        if query and query not in ["Unknown", "Error"]:
            search_results_limit = settings.get("search_results_limit", 7) if settings else 7
            results["searxng_results"] = web_search(
                query,
                max_results=search_results_limit,
                log_cb=log_cb,
            )

            # 4. Refine
            if results["searxng_results"]:
                refine_model = settings.get("refine_model") if settings else None
                refine_prompt = settings.get("refine_prompt") if settings else None
                results["llm_output"] = data_refine(
                    results["llm_output"],
                    results["searxng_results"],
                    model=refine_model,
                    prompt=refine_prompt,
                    log_cb=log_cb,
                )

        if log_cb:
            log_cb("🏁 Default Pipeline finished.")
        return results
