import logging
from .base import BasePipeline
from .nodes import scan_barcode, vision_identify, web_search, web_scrape, data_refine

logger = logging.getLogger("AdvancedPipeline")


class AdvancedPipeline(BasePipeline):
    """
    An advanced pipeline that uses Playwright to scrape content from official product URLs.
    """

    @classmethod
    def get_id(cls) -> str:
        return "advanced_playwright"

    @classmethod
    def get_name(cls) -> str:
        return "Advanced Pipeline (Playwright Scraping)"

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
            "vision_prompt": {
                "type": "textarea",
                "label": "Vision Prompt",
                "default": (
                    "Analyze the image and return strict JSON product metadata "
                    "with product_name, brand, category, and search_query."
                )
            },
            "refine_prompt": {
                "type": "textarea",
                "label": "Refine Prompt",
                "default": (
                    "Refine metadata using search and scraped page context while "
                    "preserving JSON schema and factual consistency."
                )
            },
            "scrape_wait_time": {
                "type": "string",
                "label": "Playwright JS Wait Time (ms)",
                "default": "2000",
                "options": [
                    "1000",
                    "2000",
                    "5000"]}}

    def run(
            self,
            image=None,
            text_description=None,
            settings=None,
            log_cb=None):
        results = {
            "barcode": None,
            "llm_output": None,
            "searxng_results": [],
            "scraped_content": None}

        # 1. Barcode & Initial LLM
        if image:
            results["barcode"] = scan_barcode(image, log_cb=log_cb)

        model = settings.get(
            "vision_model",
            "qwen/qwen2.5-vl-72b-instruct") if settings else "qwen/qwen2.5-vl-72b-instruct"
        vision_prompt = settings.get("vision_prompt") if settings else None
        results["llm_output"] = vision_identify(
            image,
            text_description,
            model=model,
            prompt=vision_prompt,
            log_cb=log_cb,
        )

        if not results["barcode"]:
            results["barcode"] = results["llm_output"].get("barcode")

        # 2. SearxNG
        query = results["barcode"] or results["llm_output"].get(
            "search_query") or results["llm_output"].get("product_name")
        if query and query not in ["Unknown", "Error"]:
            results["searxng_results"] = web_search(query, log_cb=log_cb)

            # 3. Playwright Scraping
            best_url = None
            if results["searxng_results"]:
                best_url = results["searxng_results"][0]["url"]

            if best_url:
                wait_time = settings.get(
                    "scrape_wait_time", 2000) if settings else 2000
                results["scraped_content"] = web_scrape(
                    best_url, wait_time=wait_time, log_cb=log_cb)

            # 4. Refinement
            if results["searxng_results"] or results["scraped_content"]:
                context = {
                    "search": results["searxng_results"],
                    "scrape": results["scraped_content"]}
                refine_model = settings.get("refine_model") if settings else None
                refine_prompt = settings.get("refine_prompt") if settings else None
                results["llm_output"] = data_refine(
                    results["llm_output"],
                    context,
                    model=refine_model,
                    prompt=refine_prompt,
                    log_cb=log_cb,
                )

        if log_cb:
            log_cb("🏁 Advanced Pipeline finished.")
        return results
