import logging
from .base import BasePipeline
from .nodes import (
    scan_barcode,
    vision_identify,
    web_search,
    web_scrape,
    data_refine,
    upc_lookup_node,
    gmail_search_node,
)

logger = logging.getLogger("ComposablePipeline")


class ComposablePipeline(BasePipeline):
    """
    A fully customizable pipeline that executes nodes in the EXACT sequence
    defined by the user in the UI.
    """

    @classmethod
    def get_id(cls) -> str:
        return "composable"

    @classmethod
    def get_name(cls) -> str:
        return getattr(cls, 'pipeline_name', "Custom Composable Pipeline")

    @classmethod
    def get_settings_schema(cls) -> dict:
        return {
            "active_nodes": {
                "type": "multiselect",
                "label": "Pipeline Nodes",
                "default": ["barcode", "vision", "search", "refine"],
                "options": [
                    "barcode",
                    "gmail_search",
                    "upc_lookup",
                    "vision",
                    "search",
                    "scrape",
                    "refine",
                ]
            },
            "vision_model": {
                "type": "string",
                "label": "Vision Model",
                "default": "qwen/qwen2.5-vl-72b-instruct"
            },
            "vision_prompt": {
                "type": "textarea",
                "label": "Vision Prompt",
                "default": (
                    "Analyze the image and return strict JSON product metadata "
                    "with fields like product_name, brand, category, and search_query."
                )
            },
            "refine_prompt": {
                "type": "textarea",
                "label": "Refine Prompt",
                "default": (
                    "Refine the metadata using search and scrape context while "
                    "preserving the original JSON schema and factual accuracy."
                )
            },
            "refine_model": {
                "type": "string",
                "label": "Refine Model",
                "default": "qwen/qwen3-235b-a22b-2507"
            },
            "search_results_limit": {
                "type": "number",
                "label": "Search Results Limit",
                "default": 7
            },
            "scrape_wait_time": {
                "type": "number",
                "label": "Scrape Wait (ms)",
                "default": 2000
            }
        }

    def run(
            self,
            image=None,
            text_description=None,
            settings=None,
            log_cb=None):
        # pylint: disable=too-many-branches,too-many-locals,too-many-statements
        if not settings:
            settings = {}

        # Get the ordered list of nodes from settings
        # The UI now provides an ordered list in settings['active_nodes']
        sequence = settings.get("active_nodes")
        if not sequence:
            # Fallback to default schema if not in settings (e.g. initial run)
            sequence = self.get_settings_schema()["active_nodes"]["default"]

        results = {
            "barcode": None,
            "gmail_results": [],
            "upc_lookup": {},
            "llm_output": {},
            "searxng_results": [],
            "scraped_content": None
        }

        if log_cb:
            log_cb(f"🚀 Starting Composable Sequence: {' -> '.join(sequence)}")

        for node_type in sequence:
            if node_type == "barcode" and image:
                results["barcode"] = scan_barcode(image, log_cb=log_cb)

            elif node_type == "gmail_search":
                gmail_query = settings.get("gmail_search_query") or text_description or ""
                gmail_max_results = settings.get("gmail_search_results_limit", 20)
                results["gmail_results"] = gmail_search_node(
                    gmail_query,
                    max_results=gmail_max_results,
                    log_cb=log_cb,
                )

            elif node_type == "upc_lookup":
                barcode_input = results.get("barcode")
                if not barcode_input and isinstance(results.get("llm_output"), dict):
                    barcode_input = results["llm_output"].get("barcode")
                is_food = False
                if isinstance(results.get("llm_output"), dict):
                    is_food = bool(results["llm_output"].get("is_food"))
                if barcode_input:
                    results["upc_lookup"] = upc_lookup_node(
                        barcode_input,
                        is_food=is_food,
                        log_cb=log_cb,
                    )
                elif log_cb:
                    log_cb("⚠️ [Node: UPC] Skipped: no barcode available yet.")

            elif node_type == "vision" and image:
                model = settings.get("vision_model") or self.get_settings_schema()[
                    "vision_model"]["default"]
                prompt = settings.get("vision_prompt")
                results["llm_output"] = vision_identify(
                    image, text_description, model=model, prompt=prompt, log_cb=log_cb)

                # Internal data bridge: if LLM found a barcode but scanner
                # didn't, adopt it
                if not results["barcode"] and results["llm_output"].get(
                        "barcode"):
                    results["barcode"] = results["llm_output"]["barcode"]

            elif node_type == "search":
                # Requires a query from either Barcode or Vision
                query = (
                    results["barcode"]
                    or results["llm_output"].get("search_query")
                    or results["upc_lookup"].get("product_name")
                    or results["llm_output"].get("product_name")
                )
                if query and query not in ["Unknown", "Error"]:
                    search_results_limit = settings.get("search_results_limit", 7)
                    results["searxng_results"] = web_search(
                        query,
                        max_results=search_results_limit,
                        log_cb=log_cb,
                    )
                else:
                    if log_cb:
                        log_cb(
                            "⚠️ [Node: Search] Skipped: No valid query found yet.")

            elif node_type == "scrape":
                # Requires a URL from Search or Vision
                best_url = None
                if results["searxng_results"]:
                    best_url = results["searxng_results"][0]["url"]
                elif results["llm_output"].get("product_url"):
                    best_url = results["llm_output"]["product_url"]

                if best_url:
                    wait_time = settings.get("scrape_wait_time", 2000)
                    results["scraped_content"] = web_scrape(
                        best_url, wait_time=wait_time, log_cb=log_cb)
                else:
                    if log_cb:
                        log_cb(
                            "⚠️ [Node: Scrape] Skipped: No target URL found yet.")

            elif node_type == "refine":
                # Requires existing AI output to refine
                if results["llm_output"]:
                    context = {
                        "search": results["searxng_results"],
                        "scrape": results["scraped_content"]}
                    prompt = settings.get("refine_prompt")
                    refine_model = settings.get("refine_model")
                    results["llm_output"] = data_refine(
                        results["llm_output"],
                        context,
                        model=refine_model,
                        prompt=prompt,
                        log_cb=log_cb,
                    )
                else:
                    if log_cb:
                        log_cb(
                            "⚠️ [Node: Refine] Skipped: No AI metadata to refine yet.")

        if log_cb:
            log_cb("🏁 Custom Sequence finished.")
        return results
