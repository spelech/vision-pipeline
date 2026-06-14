import os
from typing import Callable

from openai import OpenAI


def _get_first_non_empty(secret_getter: Callable[[str], str], keys: list[str]) -> str:
    for key in keys:
        value = str(secret_getter(key) or "").strip()
        if value:
            return value
    return ""


def resolve_llm_base_url(secret_getter: Callable[[str], str], llm_provider: str = "auto") -> str:
    # Order supports app-specific keys first, then common OpenAI-compatible naming.
    if llm_provider == "openrouter":
        return "https://openrouter.ai/api/v1"
        
    configured = _get_first_non_empty(
        secret_getter,
        ["LLM_BASE_URL", "OPENAI_BASE_URL", "OPENAI_API_BASE"],
    )
    if configured:
        return configured
    return "https://openrouter.ai/api/v1"


def resolve_llm_api_key(secret_getter: Callable[[str], str], llm_provider: str, base_url: str) -> str:
    if llm_provider == "openrouter":
        configured = _get_first_non_empty(secret_getter, ["OPENROUTER_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"])
    elif llm_provider == "litellm":
        configured = _get_first_non_empty(secret_getter, ["LLM_API_KEY", "OPENAI_API_KEY"])
    else:
        configured = _get_first_non_empty(secret_getter, ["LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"])
        
    if configured:
        return configured

    if "openrouter.ai" in base_url.lower():
        raise ValueError("Missing LLM API key (set LLM_API_KEY or OPENROUTER_API_KEY)")

    # LiteLLM and other local OpenAI-compatible gateways commonly accept any key
    # or no auth; provide a stable default token for local development.
    return "local-dev-key"


def create_openai_client(secret_getter: Callable[[str], str], llm_provider: str = "auto") -> OpenAI:
    base_url = resolve_llm_base_url(secret_getter, llm_provider)
    api_key = resolve_llm_api_key(secret_getter, llm_provider, base_url)
    return OpenAI(base_url=base_url, api_key=api_key)


def create_openai_client_from_env(llm_provider: str = "auto") -> OpenAI:
    return create_openai_client(lambda key: os.getenv(key, ""), llm_provider)

import httpx
import logging

logger = logging.getLogger("VisionAPI.llm_client")

async def fetch_models_from_gateway(secret_getter: Callable[[str], str], llm_provider: str) -> list[dict]:
    """
    Queries the LLM gateway's /v1/models endpoint to discover available models.
    """
    base_url = resolve_llm_base_url(secret_getter, llm_provider)
    api_key = resolve_llm_api_key(secret_getter, llm_provider, base_url)
    
    # Ensure URL ends with /v1 if it's missing but expected
    models_url = base_url.rstrip("/")
    if not models_url.endswith("/models"):
        models_url = f"{models_url}/models"
        
    api_key_prefix = api_key[:8] + "..." if api_key else "None"
    logger.info("Fetching models from gateway: %s (using API key starting with %s)", models_url, api_key_prefix)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            # OpenAI / LiteLLM format is usually {"data": [...]}
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            # Some implementations might return a list directly
            if isinstance(data, list):
                return data
                
            logger.warning("Unexpected response format from gateway models endpoint: %s", data)
            return []
    except Exception as e:
        logger.error("Failed to fetch models from gateway: %s", e)
        return []

async def test_llm_connection(base_url: str, api_key: str) -> dict:
    """
    Tests connectivity and authentication to the LLM gateway.
    """
    if not base_url or not api_key:
        return {"success": False, "error": "LLM Base URL and API Key cannot be empty."}

    # Attempt to fetch models to verify connectivity and auth
    try:
        async with httpx.AsyncClient() as client:
            models_url = base_url.rstrip("/")
            if not models_url.endswith("/models"):
                models_url = f"{models_url}/models"
                
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
                return {"success": True, "message": f"Successfully connected to {base_url} and found {len(data['data'])} models."}
            elif isinstance(data, list) and len(data) > 0:
                 return {"success": True, "message": f"Successfully connected to {base_url} and found {len(data)} models."}
            else:
                return {"success": False, "error": f"Connected to {base_url}, but no models were returned or response format was unexpected."}
    except httpx.ConnectError as e:
        return {"success": False, "error": f"Connection error: Could not connect to {base_url}. Please check the URL and network connectivity."}
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 401:
            return {"success": False, "error": f"Authentication error: API Key is invalid for {base_url}. Status: {status_code}"}
        elif status_code == 404:
            return {"success": False, "error": f"Not Found error: Models endpoint not found at {base_url}. Status: {status_code}"}
        else:
            return {"success": False, "error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {e}"}

async def test_llm_connection(base_url: str, api_key: str, llm_provider: str = "auto") -> dict:
    """
    Tests connectivity and authentication to the LLM gateway.
    """
    if not base_url or not api_key:
        return {"success": False, "error": "LLM Base URL and API Key cannot be empty."}

    # Attempt to fetch models to verify connectivity and auth
    try:
        async with httpx.AsyncClient() as client:
            models_url = base_url.rstrip("/")
            if not models_url.endswith("/models"):
                models_url = f"{models_url}/models"
                
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
                return {"success": True, "message": f"Successfully connected to {base_url} and found {len(data['data'])} models."}
            elif isinstance(data, list) and len(data) > 0:
                 return {"success": True, "message": f"Successfully connected to {base_url} and found {len(data)} models."}
            else:
                return {"success": False, "error": f"Connected to {base_url}, but no models were returned or response format was unexpected."}
    except httpx.ConnectError as e:
        return {"success": False, "error": f"Connection error: Could not connect to {base_url}. Please check the URL and network connectivity."}
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        if status_code == 401:
            return {"success": False, "error": f"Authentication error: API Key is invalid for {base_url}. Status: {status_code}"}
        elif status_code == 404:
            return {"success": False, "error": f"Not Found error: Models endpoint not found at {base_url}. Status: {status_code}"}
        else:
            return {"success": False, "error": f"HTTP error: {e.response.status_code} - {e.response.text}"}
    except Exception as e:
        return {"success": False, "error": f"An unexpected error occurred: {e}"}
