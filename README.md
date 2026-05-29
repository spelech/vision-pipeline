# Vision Pipeline v3.3.0

An automated product identification and enrichment system that bridges physical items with digital home services.

## ✨ New in V3
- **Composable Pipelines**: Build custom workflows using building block nodes in the UI.
- **Stealth Scraping**: Integrated Playwright microservice for bypassing bot detection on JavaScript-heavy sites.
- **True Lasso Select**: Freehand HTML5 Canvas tool for precise object isolation.
- **Pre-flight Previews**: Review and edit exact JSON payloads before dispatching to external services.
- **Modular Registry**: Easily add new pipelines and nodes via the new Python class registry.

## 🏗 System Architecture
The system is built as a set of linked functional nodes:
1. **Barcode Scan**: Multi-pass EAN/UPC extraction.
2. **Vision ID**: LLM-based modal identification.
3. **Web Search**: Real-world data via SearxNG.
4. **Web Scrape**: Stealth rendering via Playwright.
5. **Data Refinement**: Final LLM-based logic merge.

See [Architecture Documentation](docs/ARCHITECTURE.md) for more details.

## 🚀 Getting Started

### 1. Requirements
- Docker & Docker Compose
- OpenRouter API Key
- SearxNG Instance (local or remote)

### 2. Setup
The easiest way to get started is to use the included Python setup script:

```bash
python3 setup.py
```

This will:
- Create your `.env` file from the template.
- Generate a unique `ENCRYPTION_KEY` for your database secrets.
- Prepare necessary data directories with correct permissions.
- Build the Docker containers.

Once the script finishes, edit the `.env` file with your specific API keys.

### 🐳 Docker Images
The system is automatically built and published to **GitHub Container Registry (GHCR)**:
- **Main App**: `ghcr.io/spelech/vision-pipeline:latest`
- **Playwright Scraper**: `ghcr.io/spelech/vision-playwright:latest`

To pull the latest images:
```bash
docker pull ghcr.io/spelech/vision-pipeline:latest
docker pull ghcr.io/spelech/vision-playwright:latest
```

### 3. Build & Run
```bash
docker compose up -d --build
```
Access the UI at `http://localhost:8460`.

## ✅ Quality Checks
Run the same core gates used in CI before pushing:

```bash
node scripts/update-test-requirements-index.mjs --check
python -m pytest src/tests --cov=src --cov-fail-under=80 --cov-report=term --cov-report=xml:coverage/python-coverage.xml
```

For local VS Code task runs, `Python: Run Tests` now auto-refreshes the test requirements index first,
which reduces docs-sync drift during normal development.

## 📖 Documentation
- [Architecture & Design](docs/ARCHITECTURE.md)
- [Pipeline Registry](docs/PIPELINES.md)
- [Building Block Nodes](docs/NODES.md)
- [Service Integrations](src/services/README.md) (In Progress)

## 🛠 Tech Stack
- **Backend**: FastAPI, SQLAlchemy, SQLite, OpenCV, pyzbar
- **AI**: OpenRouter (Qwen 2.5 VL, Gemini 2.0)
- **Frontend**: Alpine.js, Tailwind CSS, HTML5 Canvas
- **Infrastructure**: Playwright, SearxNG, Docker
