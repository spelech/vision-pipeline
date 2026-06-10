import os
from typing import Callable

from openai import OpenAI


def _get_first_non_empty(secret_getter: Callable[[str], str], keys: list[str]) -> str:
    for key in keys:
        value = str(secret_getter(key) or "").strip()
        if value:
            return value
    return ""


def resolve_llm_base_url(secret_getter: Callable[[str], str]) -> str:
    # Order supports app-specific keys first, then common OpenAI-compatible naming.
    configured = _get_first_non_empty(
        secret_getter,
        ["LLM_BASE_URL", "OPENAI_BASE_URL", "OPENAI_API_BASE"],
    )
    if configured:
        return configured
    return "https://openrouter.ai/api/v1"


def resolve_llm_api_key(secret_getter: Callable[[str], str], base_url: str) -> str:
    configured = _get_first_non_empty(
        secret_getter,
        ["LLM_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"],
    )
    if configured:
        return configured

    if "openrouter.ai" in base_url.lower():
        raise ValueError("Missing LLM API key (set LLM_API_KEY or OPENROUTER_API_KEY)")

    # LiteLLM and other local OpenAI-compatible gateways commonly accept any key
    # or no auth; provide a stable default token for local development.
    return "local-dev-key"


def create_openai_client(secret_getter: Callable[[str], str]) -> OpenAI:
    base_url = resolve_llm_base_url(secret_getter)
    api_key = resolve_llm_api_key(secret_getter, base_url)
    return OpenAI(base_url=base_url, api_key=api_key)


def create_openai_client_from_env() -> OpenAI:
    return create_openai_client(lambda key: os.getenv(key, ""))

import httpx
import logging

logger = logging.getLogger("VisionAPI.llm_client")

async def fetch_models_from_gateway(secret_getter: Callable[[str], str]) -> list[dict]:
    """
    Queries the LLM gateway's /v1/models endpoint to discover available models.
    """
    base_url = resolve_llm_base_url(secret_getter)
    api_key = resolve_llm_api_key(secret_getter, base_url)
    
    # Ensure URL ends with /v1 if it's missing but expected
    models_url = base_url.rstrip("/")
    if not models_url.endswith("/models"):
        models_url = f"{models_url}/models"
        
    logger.info("Fetching models from gateway: %s (using key starting with %s)", models_url, api_key[:8] if api_key else "None")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            logger.debug("Gateway response: %s", data)
            
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
