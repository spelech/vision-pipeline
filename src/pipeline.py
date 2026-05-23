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

    def scan_barcode(self, image):
        """Extract barcodes from an image using pyzbar with multi-pass preprocessing."""
        if image is None: return None
        try:
            # Pass 1: Raw
            barcodes = decode(image)
            if barcodes: return barcodes[0].data.decode("utf-8")
            
            # Pass 2: Grayscale
            gray = image.convert('L')
            barcodes = decode(gray)
            if barcodes: return barcodes[0].data.decode("utf-8")
                
            # Pass 3: High Contrast
            enhancer = ImageEnhance.Contrast(gray)
            sharp = enhancer.enhance(2.5).filter(ImageFilter.SHARPEN)
            barcodes = decode(sharp)
            if barcodes: return barcodes[0].data.decode("utf-8")
            
            return None
        except Exception as e:
            logger.error(f"Error during barcode scanning: {e}")
            return None

    def _prepare_image_for_llm(self, image):
        """Convert PIL Image to base64 data URL."""
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_str}"

    def call_vision_llm(self, image=None, text_description=None, model="qwen/qwen2.5-vl-72b-instruct"):
        """Identify the product from image and/or text."""
        if not self.openrouter_api_key:
            return {"error": "API Key not found"}

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
            logger.info(f"Calling Vision LLM...")
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content_list}],
            )
            content = response.choices[0].message.content
            # Basic JSON extraction
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group())
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {"product_name": "Error", "description": str(e), "confidence_score": 0.0}

    def search_searxng(self, query):
        """Search local SearxNG for product enrichment."""
        if not self.searxng_url: return []
        try:
            params = {"q": query, "format": "json", "categories": "general"}
            response = requests.get(f"{self.searxng_url}/search", params=params, timeout=5)
            data = response.json()
            return [{"title": r['title'], "url": r['url']} for r in data.get('results', [])[:3]]
        except Exception as e:
            logger.error(f"SearxNG search failed: {e}")
            return []

    def enrich_data(self, current_data, search_results):
        """Refine data using search results via high-parameter LLM."""
        enrich_prompt = f"Refine this product data using these search results:\nData: {json.dumps(current_data)}\nResults: {json.dumps(search_results)}\nReturn EXACT same JSON schema."
        try:
            response = self.client.chat.completions.create(
                model="qwen/qwen3-235b-a22b-07-25",
                messages=[{"role": "user", "content": enrich_prompt}],
            )
            content = response.choices[0].message.content
            match = re.search(r'\{.*\}', content, re.DOTALL)
            refined = json.loads(match.group()) if match else json.loads(content)
            # Patch missing critical fields
            for k, v in current_data.items():
                if refined.get(k) in [None, "Unknown"]: refined[k] = v
            return refined
        except Exception:
            return current_data

    def run_pipeline(self, image=None, text_description=None):
        """Run the core extraction pipeline."""
        results = {"barcode": None, "llm_output": None, "searxng_results": []}

        if image: results["barcode"] = self.scan_barcode(image)
        
        results["llm_output"] = self.call_vision_llm(image, text_description)

        # Barcode fallback/sanitization
        if not results["barcode"]: results["barcode"] = results["llm_output"].get("barcode")
        if results["barcode"]:
            clean = re.sub(r'[\s-]', '', str(results["barcode"]))
            match = re.search(r'\d{6,}', clean)
            results["barcode"] = match.group() if match else None

        # Enrichment
        query = results["barcode"] or results["llm_output"].get("search_query") or results["llm_output"].get("product_name")
        if query and query not in ["Unknown", "Error"]:
            results["searxng_results"] = self.search_searxng(query)
            if results["searxng_results"]:
                results["llm_output"] = self.enrich_data(results["llm_output"], results["searxng_results"])

        return results
