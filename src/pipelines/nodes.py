import base64
import json
import logging
import os
import re
from io import BytesIO

import requests
from openai import OpenAIError
from PIL import ImageEnhance, ImageFilter
from llm_client import create_openai_client_from_env

try:
    from pyzbar.pyzbar import decode  # type: ignore
except ImportError:
    # CI environments may not have the native zbar shared library.
    # Fallback keeps the module importable and barcode scan gracefully disabled.
    def decode(_image):  # type: ignore
        return []

logger = logging.getLogger("PipelineNodes")

DEFAULT_VISION_MODEL = os.getenv("VISION_MODEL_DEFAULT", "qwen3-vl-235b-a22b-instruct")
DEFAULT_REFINE_MODEL = os.getenv("REFINE_MODEL_DEFAULT", "qwen3-235b-a22b-2507")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
LEGACY_INVALID_MODEL_IDS = {
    "qwen/qwen2.5-72b-instruct",
    "qwen/qwen2.5-32b-instruct",
}

MODEL_ID_ALIASES = {
    "qwen/qwen2.5-vl-72b-instruct": "openrouter/qwen/qwen2.5-vl-72b-instruct",
    "qwen/qwen2.5-72b-instruct": "qwen/qwen3-235b-a22b-2507",
    "qwen/qwen2.5-32b-instruct": "qwen/qwen3-235b-a22b-2507",
}


def upc_lookup_node(barcode, is_food=False, log_cb=None):
    # pylint: disable=too-many-return-statements
    if not barcode:
        return {}

    barcode_value = str(barcode).strip()
    if not barcode_value:
        return {}

    if log_cb:
        log_cb(f"🧾 [Node: UPC] Looking up barcode {barcode_value}...")

    try:
        if bool(is_food):
            response = requests.get(
                f"https://world.openfoodfacts.org/api/v0/product/{barcode_value}.json",
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            product = payload.get("product") if isinstance(payload, dict) else {}
            if not isinstance(product, dict):
                return {}
            return {
                "barcode": barcode_value,
                "source": "openfoodfacts",
                "product_name": str(product.get("product_name") or "").strip(),
                "brand": str(product.get("brands") or "").strip(),
                "category": str(product.get("categories") or "").strip(),
                "description": str(product.get("generic_name") or "").strip(),
            }

        headers = {}
        upcitemdb_key = str(os.getenv("UPCITEMDB_API_KEY") or "").strip()
        if upcitemdb_key:
            headers["user_key"] = upcitemdb_key

        response = requests.get(
            "https://api.upcitemdb.com/prod/trial/lookup",
            params={"upc": barcode_value},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") if isinstance(payload, dict) else []
        item = items[0] if isinstance(items, list) and items else {}
        if not isinstance(item, dict):
            return {}
        offers = item.get("offers") if isinstance(item.get("offers"), list) else []
        first_offer = offers[0] if offers and isinstance(offers[0], dict) else {}

        return {
            "barcode": barcode_value,
            "source": "upcitemdb",
            "product_name": str(item.get("title") or "").strip(),
            "brand": str(item.get("brand") or "").strip(),
            "category": str(item.get("category") or "").strip(),
            "description": str(item.get("description") or "").strip(),
            "product_url": str(first_offer.get("link") or "").strip(),
        }
    except requests.RequestException as e:
        if log_cb:
            log_cb(f"⚠️ [Node: UPC] Lookup failed: {str(e)}")
        return {}


def _gmail_access_token() -> str:
    client_id = str(os.getenv("GWS_CLIENT_ID") or "").strip()
    client_secret = str(os.getenv("GWS_CLIENT_SECRET") or "").strip()
    refresh_token = str(os.getenv("GWS_REFRESH_TOKEN") or "").strip()
    if not client_id or not client_secret or not refresh_token:
        raise ValueError("Missing Gmail OAuth credentials")

    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("access_token") if isinstance(payload, dict) else ""
    if not isinstance(token, str) or not token:
        raise ValueError("Failed to resolve Gmail access token")
    return token


def gmail_search_node(query, max_results=20, log_cb=None):
    query_value = str(query or "").strip()
    if not query_value:
        return []

    if log_cb:
        log_cb(f"📨 [Node: Gmail Search] Querying Gmail for '{query_value}'...")

    try:
        token = _gmail_access_token()
        response = requests.get(
            GMAIL_MESSAGES_URL,
            params={"q": query_value, "maxResults": max(1, min(int(max_results), 100))},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        messages = payload.get("messages") if isinstance(payload, dict) else []
        if not isinstance(messages, list):
            return []
        return [
            {
                "id": str(message.get("id") or ""),
                "thread_id": str(message.get("threadId") or ""),
            }
            for message in messages
            if isinstance(message, dict)
        ]
    except (requests.RequestException, ValueError) as e:
        if log_cb:
            log_cb(f"⚠️ [Node: Gmail Search] Failed: {str(e)}")
        return []


def get_client():
    return create_openai_client_from_env()


def scan_barcode(image, log_cb=None):
    if image is None:
        return None
    if log_cb:
        log_cb("🔍 [Node: Barcode] Scanning...")
    try:
        # Pass 1: Raw
        barcodes = decode(image)
        if barcodes:
            return barcodes[0].data.decode("utf-8")

        # Pass 2: Grayscale
        gray = image.convert('L')
        barcodes = decode(gray)
        if barcodes:
            return barcodes[0].data.decode("utf-8")

        # Pass 3: High Contrast
        enhancer = ImageEnhance.Contrast(gray)
        sharp = enhancer.enhance(2.5).filter(ImageFilter.SHARPEN)
        barcodes = decode(sharp)
        if barcodes:
            return barcodes[0].data.decode("utf-8")

        return None
    except (TypeError, ValueError, AttributeError, RuntimeError) as e:
        if log_cb:
            log_cb(f"❌ [Node: Barcode] Error: {str(e)}")
        return None


def vision_identify(
        image,
        text_description=None,
        model=None,
        prompt=None,
        log_cb=None):
    if not model:
        model = DEFAULT_VISION_MODEL
    model = MODEL_ID_ALIASES.get(model, model)
    if model in LEGACY_INVALID_MODEL_IDS:
        model = DEFAULT_VISION_MODEL
    if log_cb:
        log_cb(f"🤖 [Node: Vision] Calling {model}...")
    try:
        client = get_client()
    except OpenAIError as e:
        if log_cb:
            log_cb(f"❌ [Node: Vision] Error: {str(e)}")
        return {"error": str(e)}

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

    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    image_data_url = f"data:image/jpeg;base64,{img_str}"

    content_list = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url}}
    ]
    if text_description:
        content_list.append(
            {"type": "text", "text": f"Context: {text_description}"})

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
    except (
        TypeError,
        ValueError,
        AttributeError,
        RuntimeError,
        json.JSONDecodeError,
        requests.RequestException,
        OpenAIError,
    ) as e:
        if log_cb:
            log_cb(f"❌ [Node: Vision] Error: {str(e)}")
        return {"error": str(e)}


def web_search(query, max_results=7, log_cb=None):
    searxng_url = os.getenv("SEARXNG_URL")
    if not searxng_url:
        return []
    try:
        limit = int(max_results)
    except (TypeError, ValueError):
        limit = 7
    limit = max(1, min(limit, 50))
    if log_cb:
        log_cb(f"🌐 [Node: Search] Looking up '{query}'...")
    try:
        params = {"q": query, "format": "json", "categories": "general"}
        response = requests.get(
            f"{searxng_url}/search",
            params=params,
            timeout=10)
        data = response.json()
        return [{"title": r['title'], "url": r['url'], "snippet": r.get(
            'content', '')} for r in data.get('results', [])[:limit]]
    except requests.RequestException as e:
        if log_cb:
            log_cb(f"⚠️ [Node: Search] Failed: {str(e)}")
        return []


def web_scrape(url, wait_time=2000, log_cb=None):
    if log_cb:
        log_cb(f"🕸️ [Node: Scrape] Agentic Scrape on {url}...")
    scraper_url = os.getenv(
        "PLAYWRIGHT_SCRAPER_URL",
        "http://playwright-csharp-scraper:8080",
    )
    model = os.getenv("PLAYWRIGHT_SCRAPER_MODEL", "gemini-2.5-flash")
    api_key = os.getenv("PLAYWRIGHT_SCRAPER_API_KEY", "sk-local-wileyriley-gateway-12345")
    
    # Target endpoint
    endpoint = f"{scraper_url.rstrip('/')}/api/scrape/compare?sync=true"
    
    payload = {
        "urls": [url],
        "goal": "Extract product name, price, brand, description, and specifications.",
        "model": model,
        "apiKey": api_key,
        "maxSteps": 5
    }
    
    try:
        # Give it a larger timeout since dynamic scrapes can take up to ~90-120 seconds with LiteLLM latency
        resp = requests.post(endpoint, json=payload, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        
        # Parse the structured comparative result
        results = data.get("results", [])
        if results and results[0].get("status") == "Completed":
            extracted = results[0].get("data")
            if extracted:
                return json.dumps(extracted, indent=2)
            
        error_msg = results[0].get("error") if results else "Scraping failed without error details."
        if log_cb:
            log_cb(f"⚠️ [Node: Scrape] Agent scrape failed: {error_msg}")
        return None
    except Exception as e:
        if log_cb:
            log_cb(f"⚠️ [Node: Scrape] Connection failed: {str(e)}")
        return None


def data_refine(
        current_data,
        context_data,
        model=None,
        prompt=None,
        log_cb=None):
    if not model:
        model = DEFAULT_REFINE_MODEL
    model = MODEL_ID_ALIASES.get(model, model)
    if model in LEGACY_INVALID_MODEL_IDS:
        if log_cb:
            fallback_msg = (
                f"⚠️ [Node: Refine] Model '{model}' is no longer valid. "
                f"Falling back to {DEFAULT_REFINE_MODEL}."
            )
            log_cb(
                fallback_msg
            )
        model = DEFAULT_REFINE_MODEL
    if log_cb:
        log_cb(f"🧠 [Node: Refine] Finalizing with {model}...")
    try:
        client = get_client()
    except OpenAIError as e:
        if log_cb:
            log_cb(f"⚠️ [Node: Refine] Failed: {str(e)}")
        return current_data

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
    except (
        TypeError,
        ValueError,
        AttributeError,
        RuntimeError,
        json.JSONDecodeError,
        requests.RequestException,
        OpenAIError,
    ) as e:
        if log_cb:
            log_cb(f"⚠️ [Node: Refine] Failed: {str(e)}")
        return current_data
