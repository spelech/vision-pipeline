# Available Pipelines

The system supports multiple pre-configured pipelines and a dynamic builder.

## 1. Default Vision Pipeline
The standard workflow for rapid product entry.
- **Nodes**: `Barcode` -> `Vision` -> `Search` -> `Refine`.
- **Use Case**: Everyday pantry items, general household products.

## 2. Advanced Pipeline (Playwright)
Deep enrichment using full web scraping.
- **Nodes**: `Barcode` -> `Vision` -> `Search` -> `Scrape` -> `Refine`.
- **Use Case**: Electronics with complex specifications, items requiring official MSRP verification, and food items needing full ingredient/nutrition extraction.

## 3. Custom Composable Pipeline
A fully user-defined sequence managed via the UI.
- **Configurable Nodes**: Toggle any combination of the 5 core nodes.
- **Dynamic Prompts**: Independently adjust the system prompts for the `Vision` and `Refine` stages.
- **Model Selection**: Switch between high-performance vision models (e.g., Qwen 2.5 VL, Gemini 2.0).

---

## Service Export Pipelines
Once identification is complete, data can be dispatched to the following home infrastructure services:

- **Homebox**: Creates inventory items with attachments, locations, and technical metadata.
- **Mealie**: Pushes food items into the recipe and pantry management system.
- **PriceBuddy**: Monitors product URLs for price changes.
- **ChangeDetection**: Sets up automated visual or JSON-LD monitoring for target websites.
