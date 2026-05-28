# Pipeline Building Blocks (Nodes)

Nodes are the atomic units of execution in the Vision Pipeline. Each node performs a specific task and passes its output to the next stage.

## 🔍 Barcode Scan Node
**Technology**: `pyzbar` + `PIL`
**Function**: Extracts EAN/UPC barcodes from images.
- **Preprocessing**: Performs a 3-pass scan (Raw -> Grayscale -> High-Contrast/Sharpen) to ensure detection even in blurry or low-light conditions.

## 🤖 Vision Identify Node
**Technology**: Multi-modal LLMs (via OpenRouter)
**Default Model**: `qwen/qwen2.5-vl-72b-instruct`
**Input**: Image, User Context, System Prompt.
**Output Fields**:
- `product_name`: Full descriptive name.
- `brand`: Brand/Manufacturer.
- `category`: Classification (e.g., Electronics, Pantry).
- `msrp`: Estimated retail price.
- `is_food`: Boolean flag for food-specific logic.
- `search_query`: Optimized query for web enrichment.

## 🌐 Web Search Node
**Technology**: SearxNG (Meta-search)
**Function**: Fetches real-world data based on the identified product or barcode.
- **Results**: Returns the top 5 results including Titles, URLs, and Snippets.

## 🕸️ Web Scrape Node
**Technology**: Playwright + Stealth
**Function**: Performs full JavaScript rendering of a target URL (usually the top search result).
- **Stealth**: Uses browser fingerprints and behavior patterns to bypass bot detection on major e-commerce sites (Amazon, Target, etc.).
- **Output**: Extracted text content from the page body, providing deep technical specs or ingredient lists.

## 🧠 Data Refine Node
**Technology**: Text-based LLMs
**Default Model**: `qwen/qwen3-235b-a22b-2507`
**Function**: Merges the initial Vision data with the Search and Scrape context.
- **Logic**: Corrects errors from the Vision pass, fills in missing MSRP/URL fields, and formats ingredient lists or technical specs into clean, structured JSON.
