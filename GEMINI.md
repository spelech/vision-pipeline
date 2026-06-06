# Vision Pipeline

An automated product identification and enrichment system that bridges physical items with digital home services. Our goal is to create a **one-stop site/PWA** for capturing photos and adding data to any part of a home tracking ecosystem.

## Core Mandates

- **One-Stop UI:** We are developing a single React/TypeScript frontend for all interactions.
- **Service Standard:** All external integrations must use clean service wrappers with explicit interfaces.
- **Pydantic & Typing:** ALL new Python code MUST use Pydantic models for data validation and complete type hinting (`typing`).
- **Validation:** Every change MUST be verified through unit/E2E tests, `pylint`, and `mypy` before being considered complete.
- **Feature Preservation:** NEVER remove existing features or logic unless explicitly instructed by the user.
- **No Legacy Shims:** Do not maintain shims or unused code. Prioritize a lean codebase.

## Feature Development Workflow

For every new request (feature, bug fix, or refactor):
1.  **Branching:** ALWAYS create a new feature branch from the latest `master` (e.g., `feat/my-new-capability`).
2.  **Implementation:**
    -   Follow the Research -> Strategy -> Execution cycle.
    -   Use **atomic commits** that capture single logical changes.
3.  **Verification:**
    -   Add or update unit/E2E tests to verify the change.
    -   Verify that the Docker images build successfully (`docker compose build`).
    -   Verify all quality gates (tests, linting) pass **inside the container environment** (`docker exec vision-pipeline pytest tests/`).
4.  **Versioning:**
    -   BEFORE merging, bump the version in `package.json` and `web/package.json`.
    -   Follow SemVer (typically a patch bump `x.x.+1` for minor features/fixes).
5.  **Merging:**
    -   Merge the feature branch back into `master` using **no-squash merge** (`git merge --no-ff`) to preserve the atomic commit history.
6.  **Tracking:** Update `FEATURES.md` with the new capability and its status.

## Project Overview

Vision Pipeline captures or uploads images, processes them through a multi-stage pipeline, and pushes high-fidelity structured data to various home management platforms.

### Core Pipeline Stages
1.  **Barcode Scanning:** Uses `pyzbar` with multi-pass image preprocessing (grayscale, high contrast) to extract EAN/UPC codes.
2.  **Vision Identification:** Employs Vision LLMs (default: `qwen2.5-vl-72b-instruct` via OpenRouter) to identify products, brands, models, and ingredients.
3.  **Web Enrichment:** Uses `SearxNG` to find official product URLs, MSRPs, and technical specifications.
4.  **Data Refinement:** A secondary LLM pass refines and merges vision data with search results for maximum accuracy.

## Architecture

-   **Backend:** FastAPI (Python) with asynchronous task handling for batch processing.
-   **Frontend:** A modern, Apple-style SPA built with **Alpine.js**, **Tailwind CSS**, and **Cropper.js**.
-   **Persistence:** SQLite via **SQLAlchemy** (Async) for tracking processing batches and item states.
-   **Service Registry:** A modular architecture in `src/services/` for easy integration of new external platforms.

## Tech Stack

-   **Language:** Python 3.x, TypeScript
-   **Web Framework:** FastAPI + Uvicorn
-   **Database:** PostgreSQL + SQLAlchemy + Asyncpg
-   **Image Processing:** OpenCV, Pillow, pyzbar
-   **AI/LLM:** OpenRouter (OpenAI-compatible SDK)
-   **Frontend:** React 18+ (Vite), Tailwind CSS

## Getting Started

### Environment Setup
Create a `.env` file in the root directory (refer to `docker-compose.yaml` for required variables):
- `OPENROUTER_API_KEY`: Required for vision and enrichment.
- `SEARXNG_URL`: Local or remote SearxNG instance.
- `HOMEBOX_URL` / `HOMEBOX_API_KEY`: For inventory integration.
- `MEALIE_URL` / `MEALIE_API_TOKEN`: For recipe/food integration.

### Building and Running

**Using Docker (Recommended):**
```bash
docker compose up --build
```
The app will be available at `http://localhost:8460`.

**Manual Development (using venv):**
```bash
# Setup (already completed)
python3 -m venv --without-pip venv
curl -sSL https://bootstrap.pypa.io/get-pip.py -o get-pip.py
./venv/bin/python3 get-pip.py
./venv/bin/pip install -r src/requirements.txt pytest pytest-asyncio pytest-mock httpx

# Running
cd src
../venv/bin/python3 app.py

# Testing
../venv/bin/python3 -m pytest tests/test_api.py
```

## Directory Structure

-   `src/`: Main application source code.
    -   `app.py`: API routes and service orchestration.
    -   `pipeline.py`: The `VisionPipeline` core logic.
    -   `database.py`: SQLAlchemy models and DB initialization.
    -   `services/`: Integration wrappers (Homebox, Mealie, etc.).
    -   `templates/`: HTML/Alpine.js frontend.
-   `data/`: Persistent storage for the SQLite database and uploaded images.
-   `config/`: Configuration files for the application.

## Development Conventions

-   **Service Integration:** New services should inherit from `BaseService` in `src/services/base.py`.
-   **Async First:** Use `async/await` for all I/O bound operations (DB, API calls).
-   **Logging:** Use the custom `session_logger` in `src/logger.py` to provide real-time feedback to the UI during pipeline execution.
-   **Hot Reloading:** The `docker-compose.yaml` mounts the `src/` directory to `/app`, facilitating development.

## TODO / Future Enhancements
- [ ] Implement unit tests for the pipeline logic.
- [ ] Add support for more specialized enrichers (e.g., BrickLink for LEGO).
- [ ] Improve the Batch Review UI for high-volume uploads.
