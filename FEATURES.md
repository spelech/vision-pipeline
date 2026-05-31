# Vision Pipeline v3.6.1

# Project Features

This file tracks the current capabilities and planned enhancements for the Vision Pipeline.

## Current Features

### 📸 Capture & Identification
- **Single Capture:** Real-time photo capture and upload for single-item identification.
- **Precision Lasso:** Interactive image cropping and rotation using `Cropper.js` to focus the AI on specific details.
- **Vision ID:** Multi-modal identification using high-parameter Vision LLMs (e.g., Qwen2.5-VL).
- **Barcode Scanning:** Automated EAN/UPC extraction with multi-pass image preprocessing.
- **Web Enrichment:** Automatic data fetching from SearxNG for MSRP, specs, and official URLs.
- **Stealth Scraping:** Integrated Playwright microservice for bypassing bot detection on JavaScript-heavy sites.

### 📦 Batch Processing
- **Batch Upload:** Support for uploading multiple images simultaneously.
- **Background Processing:** Asynchronous pipeline execution for batches using FastAPI BackgroundTasks.
- **Queue Management:** UI for monitoring, rerunning, or deleting items in the processing queue.
- **Pre-flight Previews:** UI modal to review and edit exact JSON payloads before dispatching to external services.

### 🔌 Integrations
- **Homebox Service:** Automated item creation, metadata updates (manufacturer, model, serial), and image attachment uploads.
- **Mealie Service:** Native support for pushing food/recipe data with unit awareness.
- **PriceBuddy Service:** Automated price tracking via barcode or product URL with smart shopping-site filtering.
- **ChangeDetection.io:** Automated website change monitoring with JSON-LD price data tracking enabled.
- **Search Enrichers:** Integration with SearxNG for deep product lookups.
- **Service Mapping:** Persistent tracking of links between local items and external service unique identifiers.

### 🛠 System & UI
- **Composable Pipelines:** Visual Drag-and-drop style node builder for creating custom workflow sequences (e.g., Barcode -> Vision -> Scrape).
- **Real-time Logging:** Custom session-based logger providing live feedback to the UI during pipeline execution.
- **Responsive PWA UI:** Apple-style dark mode interface optimized for mobile use.
- **SQLite Persistence:** Async database storage for batches, items, and AI outputs.
- **Configurable LLM Gateway:** Supports OpenAI-compatible endpoints (including local LiteLLM) without hardcoding OpenRouter URLs.

### 🧾 Receipt Automation (New)
- **Dedicated Receipt Pipeline:** New receipt-specific pipeline class and registration for OCR-oriented extraction flows.
- **Receipt Wrangler Processing:** API and UI support for pending Receipt Wrangler processing actions.
- **Gmail Connect Flow:** Settings UI now includes a direct "Connect Gmail" action.
- **Secret Compatibility:** Added fallback support for receipt/Gmail secret key aliases to reduce config breakage.
## Planned Features
- [x] **Virtual Environment Setup:**
    - Plan: Establish a dedicated `venv` (manually handling `ensurepip` missing).
    - Status: Completed.
- [x] **Full Dependency Installation:**
    - Plan: Install all packages from `src/requirements.txt`.
    - Status: Completed.
- [x] **Testing Infrastructure Setup:**
    - Plan: Install `pytest`, `pytest-asyncio`, `pytest-mock`, `httpx`.
    - Status: Completed.
- [x] **API Test Suite Refresh:**
    - Plan: Align `src/tests/test_api.py` with `app.py`.
    - Coverage: `/health`, `/identify`, `/execute`, `/locations`, `/preview`, `/batch-upload`, `/queue`, `/bulk-approve`.
    - Status: Completed.
- [ ] Advanced User Overrides UI.
- [ ] Integration with additional home services (e.g., Grocy, Home Assistant).

