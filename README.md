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
Create a `.env` file in the root directory:
```env
OPENROUTER_API_KEY=your_key_here
SEARXNG_URL=http://your_searxng:8080
HOMEBOX_API_KEY=your_key
MEALIE_API_TOKEN=your_token
```

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
