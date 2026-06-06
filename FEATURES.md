# Vision Pipeline v3.6.18

# Project Features

This file tracks the current capabilities and planned enhancements for the Vision Pipeline.

## Current Features

### 📸 Capture & Identification
- **Single Capture:** Real-time photo capture and upload for single-item identification.
- **Optimized Service Prompts:** Defined detailed JSON schemas with explicit types and home-based/retailer logic rules in the default prompts for Homebox, Mealie, PriceBuddy, and ChangeDetection to maximize extraction and field completion success.
- **Helper Text Context:** Restored helper text input during uploads and photo captures, allowing additional user instruction to guide the pipeline.
- **Initial Ingestion Context for Services:** Scanned barcodes and user helper text descriptions are now preserved and fed forward to downstream destination services for improved generation accuracy.
- **Precision Lasso:** Interactive image cropping and rotation using `Cropper.js` to focus the AI on specific details.
- **Vision ID:** Multi-modal identification using high-parameter Vision LLMs (e.g., Qwen2.5-VL).
- **Barcode Scanning:** Automated EAN/UPC extraction with multi-pass image preprocessing.
- **Web Enrichment:** Automatic data fetching from SearxNG for MSRP, specs, and official URLs.
- **Stealth Scraping:** Integrated Playwright microservice for bypassing bot detection on JavaScript-heavy sites.

### 📦 Batch Processing
- **Batch Upload:** Support for uploading multiple images simultaneously.
- **Background Processing:** Asynchronous pipeline execution for batches using FastAPI BackgroundTasks.
- **Queue Management:** UI for monitoring, rerunning, or deleting items in the processing queue.
- **Pre-flight Previews:** Interactive schema-aware Form Review modal (with fallback to raw JSON editor) to verify and edit exact payloads before dispatching to external services (Homebox, Mealie, PriceBuddy, ChangeDetection).

### 🔌 Integrations
- **Homebox Service:** Automated item creation, metadata updates (manufacturer, model, serial), and image attachment uploads with dynamic location autocomplete options populated from the active database.
- **Mealie Service:** Native support for pushing food/recipe data with unit awareness.
- **PriceBuddy Service:** Automated price tracking via barcode or product URL with smart shopping-site filtering.
- **ChangeDetection.io:** Automated website change monitoring with JSON-LD price data tracking enabled.
- **Search Enrichers:** Integration with SearxNG for deep product lookups.
- **Service Mapping:** Persistent tracking of links between local items and external service unique identifiers.

### 🛠 System & UI
- **Setup Guide & Config UI:** Comprehensive setup guide tab with provider toggling (OpenRouter vs LiteLLM), real-time database vs environment variables source indicators, and explicit role-to-model configuration dropdowns.
- **Composable Pipelines:** Visual Drag-and-drop style node builder for creating custom workflow sequences (e.g., Barcode -> Vision -> Scrape).
- **Real-time Logging:** Custom session-based logger providing live feedback to the UI during pipeline execution.
- **Progressive Web App (PWA):** Installs as a standalone web application on Android and iOS (black status bar, no browser chrome, manifest-driven icon integration).
- **Offline Ingestion & Queuing:** Cache captured item images and text locally in IndexedDB when network is offline, with a warning banner in the UI.
- **Background Auto-Sync:** Automatic background synchronization of locally queued captures to the backend when online connectivity is restored.
- **Android Web Share Target:** Support for native Android gallery sharing; selecting multiple photos and sharing to "Vision Pipeline" automatically uploads them as a batch and navigates to the review dashboard.
- **SQLite Persistence:** Async database storage for batches, items, and AI outputs.
- **Configurable LLM Gateway:** Supports OpenAI-compatible endpoints (including local LiteLLM) without hardcoding OpenRouter URLs.
- **Settings Autodiscovery:** Auto-probes local networks for container services (Homebox, Mealie, SearxNG, ChangeDetection, PriceBuddy, Receipt Wrangler) and scans for Google Workspace client credentials on disk or in shared databases to simplify setup.
- **Modular API Routers**: Decoupled monolithic backend routes into dedicated, modular API sub-routers (`config`, `pipeline`, `model`, `gmail`, `item`, `service`).
- **Encrypted Secrets Management**: Standardized secret store with Fernet encryption support (`secrets_manager.py`).
- **Development Tooling**: Enforced code quality standards with `mypy` typing, `pylint` analysis, and pre-commit automation hook configurations.
- **Strict Quality Gates CI/CD**: Enforced automated linting (ESLint, Pylint), typechecking (TypeScript, Mypy), Docker image builds, and unit testing gates in development workflows to guarantee all quality checks pass before code can be merged to master.
- **Enhanced Settings UI**: Restructured model configuration with a dropdown menu for the Gmail OCR model under Model Role Assignments, removed global show-secrets toggle, and integrated granular show/hide eye icons next to individual credential input fields.
- **High-Coverage Test Suite**: Achieved over **82%** statement/line coverage for web frontend and over **92%** statement coverage for backend Python code, introducing robust unit tests for `offlineStore`, custom pipeline nodes, and service integrations (Mealie, Homebox, PriceBuddy, ChangeDetection).

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

