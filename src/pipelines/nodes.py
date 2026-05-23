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

logger = logging.getLogger("PipelineNodes")

def get_client():
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )

def scan_barcode(image, log_cb=None):
    if image is None: return None
    if log_cb: log_cb("🔍 [Node: Barcode] Scanning...")
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
        if log_cb: log_cb(f"❌ [Node: Barcode] Error: {str(e)}")
        return None

def vision_identify(image, text_description=None, model="qwen/qwen2.5-vl-72b-instruct", prompt=None, log_cb=None):
    if log_cb: log_cb(f"🤖 [Node: Vision] Calling {model}...")
    client = get_client()
    
    if not prompt:
        prompt = """
        Analyze the provided image of a product or food item.
        Extract the following information in strict JSON format:
        {
            "product_name": "string",
            "brand": "string",
            "category": "string",
            "description": "string",
            "model_number": "string",
            "msrp": "string",
            "is_food": boolean,
            "search_query": "string (optimized for product lookup)"
        }
        """

    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    image_data_url = f"data:image/jpeg;base64,{img_str}"

    content_list = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url}}
    ]
    if text_description:
        content_list.append({"type": "text", "text": f"Context: {text_description}"})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_list}],
        )
        content = response.choices[0].message.content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        json_str = match.group() if match else content
        json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
        return json.loads(json_str)
    except Exception as e:
        if log_cb: log_cb(f"❌ [Node: Vision] Error: {str(e)}")
        return {"error": str(e)}

def web_search(query, log_cb=None):
    searxng_url = os.getenv("SEARXNG_URL")
    if not searxng_url: return []
    if log_cb: log_cb(f"🌐 [Node: Search] Looking up '{query}'...")
    try:
        params = {"q": query, "format": "json", "categories": "general"}
        response = requests.get(f"{searxng_url}/search", params=params, timeout=10)
        data = response.json()
        return [{"title": r['title'], "url": r['url'], "snippet": r.get('content', '')} for r in data.get('results', [])[:5]]
    except Exception as e:
        if log_cb: log_cb(f"⚠️ [Node: Search] Failed: {str(e)}")
        return []

def web_scrape(url, wait_time=2000, log_cb=None):
    if log_cb: log_cb(f"🕸️ [Node: Scrape] Scraping {url}...")
    try:
        resp = requests.post("http://playwright-scraper:3000/scrape", json={"url": url, "wait_time": int(wait_time)}, timeout=40)
        data = resp.json()
        if data.get("success"):
            return data.get("text", "")[:10000]
        return None
    except Exception as e:
        if log_cb: log_cb(f"⚠️ [Node: Scrape] Failed: {str(e)}")
        return None

def data_refine(current_data, context_data, model="qwen/qwen2.5-72b-instruct", prompt=None, log_cb=None):
    if log_cb: log_cb(f"🧠 [Node: Refine] Finalizing with {model}...")
    client = get_client()

    if not prompt:
        prompt = f"""
        Refine the product metadata using the context (search/scrape results).
        Maintain the input JSON schema.
        Current Data: {json.dumps(current_data)}
        Context: {json.dumps(context_data)}
        """

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content
        match = re.search(r'\{.*\}', content, re.DOTALL)
        json_str = match.group() if match else content
        json_str = re.sub(r'[\x00-\x1F\x7F]', '', json_str)
        return json.loads(json_str)
    except Exception as e:
        if log_cb: log_cb(f"⚠️ [Node: Refine] Failed: {str(e)}")
        return current_data
