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
