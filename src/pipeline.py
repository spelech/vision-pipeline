import os
import json
import base64
import requests
import logging
from io import BytesIO
from PIL import Image, ImageEnhance, ImageFilter
from pyzbar.pyzbar import decode
from openai import OpenAI
from dotenv import load_dotenv
from service_adapters import HomeboxAdapter, PriceBuddyAdapter, ChangeDetectionAdapter, MealieAdapter

load_dotenv()
logger = logging.getLogger("VisionPipeline")

class VisionPipeline:
    def __init__(self):
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.searxng_url = os.getenv("SEARXNG_URL")

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.openrouter_api_key,
        )

        self.homebox = HomeboxAdapter()
        self.pricebuddy = PriceBuddyAdapter()
        self.changedetection = ChangeDetectionAdapter()
        self.mealie = MealieAdapter()
    def scan_barcode(self, image):
        """Extract barcodes from an image using pyzbar with extensive multi-pass preprocessing."""
        if image is None:
            return None
        
        try:
            logger.info("Starting barcode scan passes...")
            
            # Pass 1: Raw
            barcodes = decode(image)
            if barcodes: 
                logger.info(f"Barcode found in Pass 1: {barcodes[0].data.decode('utf-8')}")
                return barcodes[0].data.decode("utf-8")
            
            # Pass 2: Grayscale
            gray = image.convert('L')
            barcodes = decode(gray)
            if barcodes: 
                logger.info(f"Barcode found in Pass 2 (Grayscale)")
                return barcodes[0].data.decode("utf-8")
                
            # Pass 3: High Contrast + Sharpen
            enhancer = ImageEnhance.Contrast(gray)
            sharp = enhancer.enhance(2.5).filter(ImageFilter.SHARPEN)
            barcodes = decode(sharp)
            if barcodes: 
                logger.info(f"Barcode found in Pass 3 (High Contrast)")
                return barcodes[0].data.decode("utf-8")
            
            # Pass 4: Low Contrast (sometimes helpful for glossy labels)
            dull = enhancer.enhance(0.8)
            barcodes = decode(dull)
            if barcodes: 
                logger.info(f"Barcode found in Pass 4 (Low Contrast)")
                return barcodes[0].data.decode("utf-8")

            logger.info("No barcode found in any deterministic pass.")
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
        """Call Vision/Text LLM via OpenRouter to identify the product."""
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
            "description": "string (a rich, detailed description of the item including key features)",
            "technical_details": "string (detailed specifications like dimensions, weight, material, or hardware specs)",
            "quantity_info": "string (e.g. 500g, 12 pack)",
            "barcode": "string (extract the numerical barcode if visible, otherwise null)",
            "msrp": "string (estimated or found manufacturer suggested retail price with currency)",
            "is_food": boolean,
            "recipe_ingredients": ["string"],
            "recipe_instructions": ["string"],
            "yield": "string",
            "product_url": "string (official manufacturer or product page if clearly identifiable)",
            "search_query": "string (optimized query for a search engine to find this exact product info and price)",
            "confidence_score": float (0-1)
        }
        Be extremely thorough. For non-food items, focus on model numbers, technical specs, and MSRP. For food, include ingredients and instructions.
        Be concise in the name but detailed in description and technical_details.
        If the input is a description of iconic imagery, use your knowledge to identify it. If unsure, use 'Unknown'.
        """
        content_list.append({"type": "text", "text": prompt})

        if text_description:
            content_list.append({"type": "text", "text": f"User provided description: {text_description}"})

        if image:
            image_data_url = self._prepare_image_for_llm(image)
            content_list.append({
                "type": "image_url",
                "image_url": {"url": image_data_url}
            })
        
        try:
            logger.info(f"Calling LLM ({model})...")
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": content_list,
                    }
                ],
            )
            
            content = response.choices[0].message.content
            logger.info("LLM response received.")
            
            # Cleanup potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
                
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return {
                "product_name": "Error",
                "brand": "System",
                "category": "Error",
                "description": f"LLM Failure: {str(e)}",
                "confidence_score": 0.0
            }

    def search_searxng(self, query):
        """Search local SearxNG instance for product enrichment."""
        if not self.searxng_url:
            return []
        
        try:
            logger.info(f"Searching SearxNG for: {query}")
            params = {
                "q": query,
                "format": "json",
                "categories": "general"
            }
            response = requests.get(f"{self.searxng_url}/search", params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            return [{"title": r['title'], "url": r['url']} for r in data.get('results', [])[:3]]
        except Exception as e:
            logger.error(f"SearxNG search failed: {e}")
            return []

    def enrich_data(self, current_data, search_results):
        """Perform a secondary LLM call to refine data using search results."""
        if not search_results:
            return current_data

        enrich_prompt = f"""
        You are a product data specialist. I have identified a product and found some search results.
        Refine the product information based on these results. 
        Focus on:
        1. Manufacturer/Official product URL.
        2. MSRP or typical retail price.
        3. Filling in missing specifications or model details.
        4. Correcting ingredients or cooking instructions for food.

        Current Data:
        {json.dumps(current_data, indent=2)}

        Search Results:
        {json.dumps(search_results, indent=2)}

        Return the final refined data in the EXACT same JSON schema as the current data. 
        Prioritize 'product_url' for official sources and 'msrp' for the most accurate retail pricing found.
        """

        try:
            logger.info("Performing data enrichment via secondary LLM call (Qwen 235B)...")
            response = self.client.chat.completions.create(
                model="qwen/qwen3-235b-a22b-07-25", # Precise high-parameter Qwen model
                messages=[{"role": "user", "content": enrich_prompt}],
            )
            content = response.choices[0].message.content

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()

            refined = json.loads(content)
            # Ensure we don't lose the confidence score or other critical fields if LLM missed them
            for key in current_data:
                if key not in refined or refined[key] in [None, "Unknown", "Error"]:
                    refined[key] = current_data[key]

            return refined
        except Exception as e:
            logger.error(f"Enrichment failed: {e}")
            return current_data

    def run_pipeline(self, image=None, text_description=None, model="qwen/qwen2.5-vl-72b-instruct"):
        """Run the full deterministic pipeline with LLM fallbacks and enrichment."""
        results = {
            "barcode": None,
            "llm_output": None,
            "searxng_query": None,
            "searxng_results": [],
            "duplicates": {
                "homebox": [],
                "mealie": {
                    "recipes": [],
                    "foods": []
                }
            }
        }

        # 1. Deterministic Barcode Scan
        if image:
            results["barcode"] = self.scan_barcode(image)

        # 2. Vision/Text identification
        results["llm_output"] = self.call_vision_llm(image, text_description, model=model)

        # Fallback barcode from LLM if pyzbar failed
        if not results["barcode"] and results["llm_output"].get("barcode"):
            logger.info("Using barcode from LLM observation.")
            results["barcode"] = results["llm_output"]["barcode"]

        # Sanitize barcode
        if results["barcode"]:
            import re
            cleaned = re.sub(r'[\s-]', '', str(results["barcode"]))
            matches = re.findall(r'\d+', cleaned)
            if matches:
                longest_match = max(matches, key=len)
                if len(longest_match) >= 6:
                    results["barcode"] = longest_match
                else:
                    results["barcode"] = None
            else:
                results["barcode"] = None

        product_name = results["llm_output"].get("product_name", "")
        llm_search_query = results["llm_output"].get("search_query", "")

        # 3. Search for enrichment
        if results["barcode"]:
            search_query = f"upc {results['barcode']}"
        elif llm_search_query:
            search_query = llm_search_query
        else:
            search_query = product_name

        if search_query and search_query not in ["Unknown", "Error"]:
            results["searxng_query"] = search_query
            results["searxng_results"] = self.search_searxng(search_query)

        # 4. Enrichment Step (Secondary LLM call)
        if results["llm_output"].get("product_name") not in ["Unknown", "Error"] and results["searxng_results"]:
            results["llm_output"] = self.enrich_data(results["llm_output"], results["searxng_results"])

        # 5. Deduplication Check
        if product_name and product_name not in ["Error", "Unknown"]:
            results["duplicates"]["homebox"] = self.homebox.search_items(product_name)
            if results["llm_output"].get("is_food"):
                # Check for both recipes and food items
                results["duplicates"]["mealie"] = {
                    "recipes": self.mealie.search_recipes(product_name),
                    "foods": self.mealie.search_foods(product_name)
                }

        return results
