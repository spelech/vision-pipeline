# Vision Pipeline Refactoring & Rearchitecture Implementation Guide

This document provides a highly technical, step-by-step specification for another agent to execute the refactoring of the **Vision Pipeline** codebase.

---

## Phase 1: Dynamic Configuration Resolution (Configuration Synchronization)

### Goal
Prevent external services from caching environment variables at import-time. Migrate them to resolve config values dynamically on invocation.

### Detailed Steps

#### 1. Modify `src/services/homebox.py`
Change the constructor to avoid reading `os.getenv` at initialization. Convert those fields to read dynamically via properties.
* **File to modify**: [homebox.py](file:///C:/Development/Repos/vision-pipeline/src/services/homebox.py#L22-L27)
* **Changes**:
```python
class HomeboxService(BaseService):
    def __init__(self):
        # Remove these fields from __init__:
        # self.api_url = os.getenv("HOMEBOX_URL", "...")
        # self.username = os.getenv("HOMEBOX_USERNAME")
        # self.password = os.getenv("HOMEBOX_PASSWORD")
        self._cached_token = None

    @property
    def api_url(self) -> str:
        return os.getenv("HOMEBOX_URL", "http://homebox:7745/api/v1")

    @property
    def username(self) -> Optional[str]:
        return os.getenv("HOMEBOX_USERNAME")

    @property
    def password(self) -> Optional[str]:
        return os.getenv("HOMEBOX_PASSWORD")
```

#### 2. Modify `src/services/mealie.py`
* **File to modify**: [mealie.py](file:///C:/Development/Repos/vision-pipeline/src/services/mealie.py#L12-L16)
* **Changes**:
```python
class MealieService(BaseService):
    def __init__(self):
        # Do not cache os.getenv here
        pass

    @property
    def api_url(self) -> str:
        return os.getenv("MEALIE_URL", "http://mealie:9000/api")

    @property
    def api_key(self) -> Optional[str]:
        return os.getenv("MEALIE_API_TOKEN")
```

#### 3. Modify `src/services/enrichers.py`
* **File to modify**: [enrichers.py](file:///C:/Development/Repos/vision-pipeline/src/services/enrichers.py)
* **Changes**: Apply the same pattern to `PriceBuddyService` and `ChangeDetectionService`:
```python
class PriceBuddyService(BaseService):
    @property
    def api_url(self) -> str:
        return os.getenv("PRICEBUDDY_URL", "http://pricebuddy:80/api/v1")

    @property
    def api_key(self) -> Optional[str]:
        return os.getenv("PRICEBUDDY_API_KEY")

class ChangeDetectionService(BaseService):
    @property
    def api_url(self) -> str:
        return os.getenv("CHANGEDETECTION_URL", "http://changedetection:5000/api/v1")

    @property
    def api_key(self) -> Optional[str]:
        return os.getenv("CHANGEDETECTION_API_KEY")
```

---

## Phase 2: Async Client Migration (`httpx` + `AsyncOpenAI`)

### Goal
Remove synchronous `requests` calls and transition to `httpx.AsyncClient` and `openai.AsyncOpenAI` for pooled HTTP connections.

### Detailed Steps

#### 1. Setup shared HTTPX Client in `src/services/base.py`
Avoid instantiating a client per request by defining a helper method or subclassing a shared client context. Or export an async request helper.
* **File to modify**: [base.py](file:///C:/Development/Repos/vision-pipeline/src/services/base.py)
* **Changes**:
```python
import httpx

# Shared async client for connection pooling
http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0))
```

#### 2. Convert Service Base and subclass request wrappers
Change the helper request functions to perform async requests with `httpx` instead of `requests` inside `asyncio.to_thread`.
* **Example modification in `src/services/homebox.py`**:
```python
# Before
async def _request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
    request_method = getattr(requests, method.lower())
    return await asyncio.to_thread(request_method, f"{self.api_url}{endpoint}", **kwargs)

# After
from services.base import http_client

async def _request(self, method: str, endpoint: str, **kwargs: Any) -> httpx.Response:
    url = f"{self.api_url}{endpoint}"
    # Translate requests parameters to httpx (e.g. data -> content/data, files -> files)
    response = await http_client.request(method, url, **kwargs)
    return response
```
* Convert all `requests` methods in `homebox.py`, `mealie.py`, and `enrichers.py` to `await self._request(...)` or direct `http_client` calls.

#### 3. Establish Reusable `AsyncOpenAI` client in `src/llm_client.py`
Create a client pool manager that maintains a single `AsyncOpenAI` instance and regenerates it only if the key/url variables change.
* **File to modify**: [llm_client.py](file:///C:/Development/Repos/vision-pipeline/src/llm_client.py)
* **Changes**:
```python
from openai import AsyncOpenAI

_async_openai_client: Optional[AsyncOpenAI] = None
_cached_key: Optional[str] = None
_cached_url: Optional[str] = None

def get_async_openai_client() -> AsyncOpenAI:
    global _async_openai_client, _cached_key, _cached_url
    base_url = resolve_llm_base_url(lambda k: os.getenv(k, ""))
    api_key = resolve_llm_api_key(lambda k: os.getenv(k, ""), base_url)
    
    if _async_openai_client is None or _cached_key != api_key or _cached_url != base_url:
        _async_openai_client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        _cached_key = api_key
        _cached_url = base_url
        
    return _async_openai_client
```

---

## Phase 3: Natively Async Pipeline Engine

### Goal
Transition pipeline nodes and execution runs to be fully asynchronous to eliminate the overhead of blocking threads in the pool.

### Detailed Steps

#### 1. Refactor Pipeline Nodes in `src/pipelines/nodes.py`
Change node functions to `async def` and use `get_async_openai_client()`.
* **Example (Vision Identify)**:
```python
async def vision_identify(
        image,
        text_description=None,
        model=None,
        prompt=None,
        log_cb=None):
    # ...
    client = get_async_openai_client()
    # ...
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content_list}],
        )
        content = response.choices[0].message.content
        # ... parse json
```

* **Example (Web Search)**:
```python
async def web_search(query, max_results=7, log_cb=None):
    searxng_url = os.getenv("SEARXNG_URL")
    if not searxng_url:
        return []
    # ...
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{searxng_url}/search", params=params, timeout=10.0)
        data = response.json()
        return [...]
```

#### 2. Convert base and implementations to `async def run`
Update the runner to perform native async operations.
* **File to modify**: `src/pipelines/base.py`, `src/pipelines/default.py`, `src/pipelines/composable.py`.
```python
# In default.py
async def run(self, image=None, text_description=None, settings=None, log_cb=None):
    results = {"barcode": None, "llm_output": None, "searxng_results": []}
    
    if image:
        results["barcode"] = await run_in_threadpool(scan_barcode, image, log_cb=log_cb) # scan_barcode uses OpenCV/Pillow (CPU-bound, keep in threadpool)
        
    # Async LLM
    results["llm_output"] = await vision_identify(image, text_description, model=model, prompt=prompt, log_cb=log_cb)
    
    # Async Search
    results["searxng_results"] = await web_search(query, max_results=search_results_limit, log_cb=log_cb)
    
    # Async Refine
    results["llm_output"] = await data_refine(results["llm_output"], results["searxng_results"], model=refine_model, prompt=refine_prompt, log_cb=log_cb)
    
    return results
```

---

## Phase 4: Frontend De-monolithization

### Goal
Decompose `Settings.tsx` and `App.tsx` into decoupled subcomponents and domain-driven custom React hooks.

### Detailed Steps

#### 1. Split `web/src/components/Settings.tsx`
Create a new directory structure `web/src/components/Settings/` containing:
* `SettingsContainer.tsx`: Handles settings layout, tab choices, and settings save trigger.
* `SetupGuideSection.tsx`: Form rendering for LLM Provider settings, API keys, and model roles.
* `GeneralConfigSection.tsx`: Backups, configuration imports/exports, and network auto-discovery triggers.
* `PromptSuiteSection.tsx`: Custom and system prompts templates.

#### 2. Move Settings State to a Custom Hook
Extract form handling, network discovery fetches, and settings state logic into `web/src/components/Settings/useSettings.ts`:
```typescript
export function useSettings() {
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  
  const loadConfig = async () => { ... };
  const saveSettings = async () => { ... };
  const runAutodiscover = async () => { ... };
  
  return { secrets, saving, loadConfig, saveSettings, runAutodiscover, ... };
}
```

---

## Verification & Validation Plan

Ensure the other agent executes the following quality gates:

### 1. Automated Quality Gates
* **Backend type checking**: Run `mypy src/` from the root workspace directory. Ensure it passes cleanly.
* **Backend lint check**: Run `pylint src/` and ensure the code score is `>= 9.5`.
* **Frontend building**: Run `npm run build` inside `web/` to confirm that TSX compilation (`tsc -b`) succeeds.
* **E2E tests**: Run `docker exec vision-pipeline pytest tests/` or target specific test scripts to ensure that pipelines and service mock outputs continue to generate matching JSON results.

### 2. Manual Verification
* **Settings Validation**: Update an API key in the UI, save it, and verify that the backend's `os.environ` updates immediately and is resolved on the next run.
* **Autodiscovery Check**: Trigger local autodiscovery from the settings tab to check that localhost container hostnames are resolved correctly.
