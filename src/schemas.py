from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PromptTemplateConfig(BaseModel):
    id: str
    name: str
    prompt: str


class ServicePromptConfig(BaseModel):
    service: str
    prompt: str
    model: Optional[str] = None
    enabled: bool = True


class PipelineInfo(BaseModel):
    id: str
    name: str = "Unknown Pipeline"
    description: Optional[str] = None


class PipelineListResponse(BaseModel):
    success: bool
    pipelines: List[Dict[str, Any]]
    error: Optional[str] = None


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: Optional[str] = None
    is_system: Optional[bool] = None


class ModelListResponse(BaseModel):
    success: bool
    models: List[ModelInfo]


class ConfigSecretStatus(BaseModel):
    OPENROUTER_API_KEY: str = ""
    SEARXNG_URL: str = ""
    HOMEBOX_URL: str = ""
    MEALIE_URL: str = ""
    PRICEBUDDY_URL: str = ""
    CHANGEDETECTION_URL: str = ""
    HOMEBOX_USERNAME: str = ""
    HOMEBOX_PASSWORD: str = ""
    MEALIE_API_TOKEN: str = ""
    PRICEBUDDY_API_KEY: str = ""
    CHANGEDETECTION_API_KEY: str = ""
    GWS_CLIENT_ID: str = ""
    GWS_CLIENT_SECRET: str = ""
    GWS_REFRESH_TOKEN: str = ""
    UPCITEMDB_API_KEY: str = ""
    RECEIPT_WRANGLER_URL: str = ""
    RECEIPT_WRANGLER_API_TOKEN: str = ""
    RECEIPT_WRANGLER_API_KEY: str = ""
    RECEIPT_WRANGLER_GROUP_ID: str = ""
    GMAIL_OCR_BACKEND: str = ""
    GMAIL_OCR_VISION_MODEL: str = ""


class ConfigResponse(BaseModel):
    prompt_templates: Optional[List[PromptTemplateConfig]] = None
    service_prompts: Optional[Dict[str, ServicePromptConfig]] = None
    model_favorites: Optional[List[str]] = None
    starred_models: Optional[List[str]] = None
    image_optimization: Optional[Dict[str, Any]] = None
    custom_pipelines: Optional[List[Dict[str, Any]]] = None
    gmail_auto_sync_enabled: Optional[bool] = None
    gmail_poll_interval_minutes: Optional[int] = None
    gmail_auto_sync_query: Optional[str] = None
    gmail_auto_sync_max_results: Optional[int] = None
    secrets_status: Optional[Dict[str, str]] = None


class ConfigUpdateRequest(BaseModel):
    prompt_templates: Optional[List[PromptTemplateConfig]] = None
    service_prompts: Optional[Dict[str, ServicePromptConfig]] = None
    model_favorites: Optional[List[str]] = None
    starred_models: Optional[List[str]] = None
    image_optimization: Optional[Dict[str, Any]] = None
    custom_pipelines: Optional[List[Dict[str, Any]]] = None
    gmail_auto_sync_enabled: Optional[bool] = None
    gmail_poll_interval_minutes: Optional[int] = None
    gmail_auto_sync_query: Optional[str] = None
    gmail_auto_sync_max_results: Optional[int] = None
    # Secrets
    OPENROUTER_API_KEY: Optional[str] = None
    SEARXNG_URL: Optional[str] = None
    HOMEBOX_URL: Optional[str] = None
    MEALIE_URL: Optional[str] = None
    PRICEBUDDY_URL: Optional[str] = None
    CHANGEDETECTION_URL: Optional[str] = None
    HOMEBOX_USERNAME: Optional[str] = None
    HOMEBOX_PASSWORD: Optional[str] = None
    MEALIE_API_TOKEN: Optional[str] = None
    PRICEBUDDY_API_KEY: Optional[str] = None
    CHANGEDETECTION_API_KEY: Optional[str] = None
    GWS_CLIENT_ID: Optional[str] = None
    GWS_CLIENT_SECRET: Optional[str] = None
    GWS_REFRESH_TOKEN: Optional[str] = None
    UPCITEMDB_API_KEY: Optional[str] = None
    RECEIPT_WRANGLER_URL: Optional[str] = None
    RECEIPT_WRANGLER_API_TOKEN: Optional[str] = None
    RECEIPT_WRANGLER_API_KEY: Optional[str] = None
    RECEIPT_WRANGLER_GROUP_ID: Optional[str] = None
    GMAIL_OCR_BACKEND: Optional[str] = None
    GMAIL_OCR_VISION_MODEL: Optional[str] = None


class ServiceMappingInfo(BaseModel):
    service: str
    external_id: str
    url: Optional[str] = None


class ItemSearchInfo(BaseModel):
    id: str
    status: str
    image_path: str
    raw_image_path: Optional[str] = None
    product_type: str = "unknown"
    ai_output: Optional[Dict[str, Any]] = None
    user_overrides: Optional[Dict[str, Any]] = None
    created_at: datetime
    mappings: List[ServiceMappingInfo]
    # For compatibility with frontend Asset type
    product_name: Optional[str] = None
    brand: Optional[str] = None


class SearchResponse(BaseModel):
    items: List[ItemSearchInfo]


class HealthResponse(BaseModel):
    status: str = "ok"


class LocationInfo(BaseModel):
    id: str
    name: str


class LocationsResponse(BaseModel):
    success: bool
    locations: Optional[List[Any]] = None
    error: Optional[str] = None


class SessionLogsResponse(BaseModel):
    logs: List[Dict[str, Any]]


class ServicePreviewResponse(BaseModel):
    service: str
    payload: Dict[str, Any]


class ServiceOutputGenerateRequest(BaseModel):
    item_id: int
    service_name: str
    force: bool = False


class ServiceOutputGenerateResponse(BaseModel):
    success: bool
    service_name: str
    cached: bool = False
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
