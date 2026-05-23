import os
import json
import base64
import requests
import logging
import re
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from pyzbar.pyzbar import decode
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("VisionPipeline")

class VisionPipeline:
    """
    The Core Extractor. Responsible for:
    1. Barcode scanning (pyzbar)
    2. Primary Vision identification (OpenRouter)
    3. Web search enrichment (SearxNG)
    4. Data refinement (Secondary LLM call)
    """
    
    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.searxng_url = os.getenv("SEARXNG_URL")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
        )

    def scan_barcode(self, image, log_cb=None):
        """Extract barcodes from an image using pyzbar with multi-pass preprocessing."""
        if image is None: return None
        if log_cb: log_cb("🔍 Scanning for barcodes...")
        try:
            # Pass 1: Raw
            barcodes = decode(image)
            if barcodes: 
                res = barcodes[0].data.decode("utf-8")
                if log_cb: log_cb(f"✅ Barcode found: {res}")
                return res
            
            # Pass 2: Grayscale
            gray = image.convert('L')
            barcodes = decode(gray)
            if barcodes: 
                res = barcodes[0].data.decode("utf-8")
                if log_cb: log_cb(f"✅ Barcode found (grayscale pass): {res}")
                return res
                
            # Pass 3: High Contrast
            enhancer = ImageEnhance.Contrast(gray)
            sharp = enhancer.enhance(2.5).filter(ImageFilter.SHARPEN)
            barcodes = decode(sharp)
            if barcodes: 
                res = barcodes[0].data.decode("utf-8")
                if log_cb: log_cb(f"✅ Barcode found (high-contrast pass): {res}")
                return res
            
            if log_cb: log_cb("⚠️ No barcode detected in image.")
            return None
        except Exception as e:
            logger.error(f"Error during barcode scanning: {e}")
            if log_cb: log_cb(f"❌ Barcode scan error: {str(e)}")
            return None

    def _prepare_image_for_llm(self, image):
        """Convert PIL Image to base64 data URL."""
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_str}"

    def call_vision_llm(self, image=None, text_description=None, model="qwen/qwen2.5-vl-72b-instruct", log_cb=None):
        """Identify the product from image and/or text."""
        if not self.openrouter_api_key:
            return {"error": "API Key not found"}

        if log_cb: log_cb(f"🤖 Calling Vision LLM ({model})...")
        content_list = []
        prompt = """
        Analyze the provided input (image and/or description) of a product, toy, or food item.
        Extract the following information in strict JSON format:
        {
            "product_name": "string",
            "brand": "string",
            "manufacturer": "string",
            "model_number": "string",
            "serial_number": "string",
            "category": "string",
            "description": "string (a rich, detailed description)",
            "technical_details": "string (specs: dimensions, weight, material)",
            "quantity_info": "string (e.g. 500g, 12 pack)",
            "barcode": "string (numerical barcode if visible)",
            "msrp": "string (estimated retail price)",
            "is_food": boolean,
            "recipe_ingredients": ["string"],
            "recipe_instructions": ["string"],
            "yield": "string",
            "product_url": "string (official site)",
            "search_query": "string (optimized for product lookup)",
            "confidence_score": float (0-1)
        }
        Be extremely thorough. For non-food items, focus on model numbers and specs. For food, include ingredients.
        """
        content_list.append({"type": "text", "text": prompt})

        if text_description:
            content_list.append({"type": "text", "text": f"User context: {text_description}"})

        if image:
            image_data_url = self._prepare_image_for_llm(image)
            content_list.append({"type": "image_url", "image_url": {"url": image_data_url}})
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content_list}],
            )
            content = response.choices[0].message.content
            
            # Robust JSON extraction
            json_str = content
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                json_str = match.group()
            
            # Remove dangerous control characters but preserve common whitespace
            # Preserves \n (0x0A), \r (0x0D), \t (0x09)
            json_str = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', json_str)
                
            res = json.loads(json_str)
            if log_cb: log_cb(f"✨ LLM identified: {res.get('product_name')} ({round(res.get('confidence_score', 0)*100)}% confidence)")
            return res
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            if log_cb: log_cb(f"❌ Identification Error: {str(e)}")
            return {"product_name": "Error", "description": str(e), "confidence_score": 0.0}

    def search_searxng(self, query, log_cb=None):
        """Search local SearxNG for product enrichment."""
        if not self.searxng_url: return []
        if log_cb: log_cb(f"🌐 Searching Web for '{query}'...")
        try:
            params = {"q": query, "format": "json", "categories": "general"}
            response = requests.get(f"{self.searxng_url}/search", params=params, timeout=5)
            data = response.json()
            results = [{"title": r['title'], "url": r['url']} for r in data.get('results', [])[:3]]
            if log_cb: log_cb(f"🔗 Found {len(results)} relevant search results.")
            return results
        except Exception as e:
            logger.error(f"SearxNG search failed: {e}")
            if log_cb: log_cb(f"⚠️ Search failed: {str(e)}")
            return []

    def enrich_data(self, current_data, search_results, log_cb=None):
        """Refine data using search results via high-parameter LLM."""
        if log_cb: log_cb("🧠 Performing deep data refinement...")
        enrich_prompt = f"Refine this product data using these search results:\nData: {json.dumps(current_data)}\nResults: {json.dumps(search_results)}\nReturn EXACT same JSON schema."
        try:
            response = self.client.chat.completions.create(
                model="qwen/qwen3-235b-a22b-07-25",
                messages=[{"role": "user", "content": enrich_prompt}],
            )
            content = response.choices[0].message.content
            
            match = re.search(r'\{.*\}', content, re.DOTALL)
            json_str = match.group() if match else content
            json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
            
            refined = json.loads(json_str)
            # Patch missing critical fields
            for k, v in current_data.items():
                if refined.get(k) in [None, "Unknown"]: refined[k] = v
            if log_cb: log_cb("✅ Data enrichment complete.")
            return refined
        except Exception as e:
            if log_cb: log_cb(f"⚠️ Enrichment failed: {str(e)}")
            return current_data

    def run_pipeline(self, image=None, text_description=None, log_cb=None):
        """Run the core extraction pipeline."""
        results = {"barcode": None, "llm_output": None, "searxng_results": []}

        if image: results["barcode"] = self.scan_barcode(image, log_cb=log_cb)
        
        results["llm_output"] = self.call_vision_llm(image, text_description, log_cb=log_cb)

        # Barcode fallback/sanitization
        if not results["barcode"]: results["barcode"] = results["llm_output"].get("barcode")
        if results["barcode"]:
            clean = re.sub(r'[\s-]', '', str(results["barcode"]))
            match = re.search(r'\d{6,}', clean)
            results["barcode"] = match.group() if match else None

        # Enrichment
        query = results["barcode"] or results["llm_output"].get("search_query") or results["llm_output"].get("product_name")
        if query and query not in ["Unknown", "Error"]:
            results["searxng_results"] = self.search_searxng(query, log_cb=log_cb)
            if results["searxng_results"]:
                results["llm_output"] = self.enrich_data(results["llm_output"], results["searxng_results"], log_cb=log_cb)

        if log_cb: log_cb("🏁 Pipeline finished.")
        return results
