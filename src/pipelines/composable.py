import logging
from .base import BasePipeline
from .nodes import scan_barcode, vision_identify, web_search, web_scrape, data_refine

logger = logging.getLogger("ComposablePipeline")

class ComposablePipeline(BasePipeline):
    """
    A fully customizable pipeline that executes nodes in a user-defined sequence.
    """

    @classmethod
    def get_id(cls) -> str:
        return "composable"

    @classmethod
    def get_name(cls) -> str:
        return "Custom Composable Pipeline"

    @classmethod
    def get_settings_schema(cls) -> dict:
        return {
            "active_nodes": {
                "type": "multiselect",
                "label": "Pipeline Nodes",
                "default": ["barcode", "vision", "search", "refine"],
                "options": ["barcode", "vision", "search", "scrape", "refine"]
            },
            "vision_model": {
                "type": "string",
                "label": "Vision Model",
                "default": "qwen/qwen2.5-vl-72b-instruct",
                "options": ["qwen/qwen2.5-vl-72b-instruct", "google/gemini-2.0-flash-001"]
            },
            "vision_prompt": {
                "type": "textarea",
                "label": "Vision Prompt Node",
                "default": ""
            },
            "refine_prompt": {
                "type": "textarea",
                "label": "Refinement Prompt Node",
                "default": ""
            }
        }

    def run(self, image=None, text_description=None, settings=None, log_cb=None):
        if not settings: settings = {}
        nodes = settings.get("active_nodes", ["barcode", "vision", "search", "refine"])
        
        results = {"barcode": None, "llm_output": {}, "searxng_results": [], "scraped_content": None}

        # 1. Barcode
        if "barcode" in nodes and image:
            results["barcode"] = scan_barcode(image, log_cb=log_cb)

        # 2. Vision
        if "vision" in nodes and image:
            model = settings.get("vision_model", "qwen/qwen2.5-vl-72b-instruct")
            prompt = settings.get("vision_prompt")
            results["llm_output"] = vision_identify(image, text_description, model=model, prompt=prompt, log_cb=log_cb)
            
            # Sync barcode if found by LLM but not scan
            if not results["barcode"]: results["barcode"] = results["llm_output"].get("barcode")

        # 3. Search
        if "search" in nodes:
            query = results["barcode"] or results["llm_output"].get("search_query") or results["llm_output"].get("product_name")
            if query and query not in ["Unknown", "Error"]:
                results["searxng_results"] = web_search(query, log_cb=log_cb)

        # 4. Scrape
        if "scrape" in nodes:
            best_url = None
            if results["searxng_results"]: best_url = results["searxng_results"][0]["url"]
            elif results["llm_output"].get("product_url"): best_url = results["llm_output"]["product_url"]
            
            if best_url:
                results["scraped_content"] = web_scrape(best_url, log_cb=log_cb)

        # 5. Refine
        if "refine" in nodes and results["llm_output"]:
            context = {"search": results["searxng_results"], "scrape": results["scraped_content"]}
            prompt = settings.get("refine_prompt")
            results["llm_output"] = data_refine(results["llm_output"], context, prompt=prompt, log_cb=log_cb)

        if log_cb: log_cb("🏁 Custom Pipeline finished.")
        return results
