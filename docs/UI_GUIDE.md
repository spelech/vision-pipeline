# Vision Pipeline UI Guide

A tour of the advanced Vision Pipeline V3 interface.

## 📸 Capture & Lasso
- **New Photo**: Launches the system camera.
- **Upload**: Select an image from the filesystem.
- **✏️ Precision Lasso**: Enter the freehand selection mode.
    - Click and drag (or touch and drag) to draw a polygon around the item.
    - Click **Save Lasso** to generate a transparent isolation mask. This significantly improves AI identification in busy scenes.

## 🛠 Pipeline Settings
Located in the Capture tab, this menu allows for deep customization:
- **Select Pipeline**: Choose between standard, advanced, or custom workflows.
- **Pipeline Nodes (Composable Only)**: Toggle specific functional blocks (Barcode, Vision, Search, Scrape, Refine).
- **Vision/Refine Prompts**: View and edit the specific system prompts sent to the LLMs.
- **Vision Model**: Switch between supported vision models (e.g., Qwen 2.5 VL).

## 📦 Review & Execute
After identification, items appear in the **Review** tab:
- **Edit Data**: Click any item to manually correct AI findings (Product Name, Brand, MSRP, etc.).
- **Workflow Routing**: Toggle which services (Homebox, Mealie, etc.) should receive the data.
- **Pre-flight Review**: Clicking **Run Services** triggers a payload modal.
    - **Review Payload**: Inspect the exact JSON being sent to the APIs.
    - **Live Edit**: You can manually edit the JSON in the modal before final confirmation.
