# Plan: Gmail → Receipt Wrangler → UPC Lookup → Homebox Pipeline

## TL;DR
Add a new receipt-driven ingestion path: Gmail (GWS OAuth2) is polled for receipt emails, attachments are pushed to Receipt Wrangler via its `quickScan` API, then vision-pipeline pulls enriched receipt items from Receipt Wrangler, runs them through a new Receipt Pipeline (UPC Lookup → Vision OCR → Search → Scrape → Refine), creates Homebox inventory items, and uploads the original receipt image as a Homebox attachment. All backed by APScheduler for periodic Gmail polling.

## Architecture Flow
1. **Gmail (OAuth2)**: Poll inbox for receipts/invoices.
2. **Receipt Wrangler**: Push attachments to `quickScan` for line-item extraction.
3. **Receipt Pipeline**: Pull pending receipts from RW.
   - **UPC Lookup**: Enrich via Open Food Facts / UPCitemdb.
   - **Vision (OCR)**: Refine line items with OCR context.
   - **Search/Scrape**: Use SearXNG to identify vendors from search snippets.
   - **Refine**: Final data merging with "Sold By" vendor detection.
4. **Dispatched**: Create Homebox items and always attach the receipt image.
5. **Cleanup**: Mark receipt as `RESOLVED` in Receipt Wrangler.

## Phases

### Phase 1: Config Foundations
- Add secrets to [src/schemas.py](src/schemas.py): `RECEIPT_WRANGLER_API_TOKEN`, `GWS_CLIENT_ID`, `GWS_CLIENT_SECRET`, `GWS_REFRESH_TOKEN`, `UPCITEMDB_API_KEY`.
- Add `gmail_poll_interval_minutes` to `AppSetting` (default: 30).
- Update [src/requirements.txt](src/requirements.txt): `apscheduler`, `google-auth`, `google-api-python-client`.

### Phase 2: Receipt Wrangler Client (`src/services/receipt_wrangler.py`)
- Implement `ReceiptWranglerClient` using API Key authentication.
- Methods: `get_pending_receipts()`, `quick_scan(image_bytes)`, `download_image(image_id)`, `update_receipt_status()`.

### Phase 3: UPC Lookup Node (`src/pipelines/nodes.py`)
- New `upc_lookup_node(barcode, is_food, log_cb)`.
- Query Open Food Facts (food) or UPCitemdb (general).

### Phase 4: Receipt Pipeline (`src/pipelines/receipt.py`)
- Create `ReceiptPipeline(BasePipeline)`.
- Node chain: UPC Lookup → Vision → Search → Scrape → Refine.
- Custom OCR-focused Vision prompt.

### Phase 5: Gmail/GWS Ingestion (`src/services/gmail_ingestor.py`)
- Handle OAuth2 handshake and token storage.
- Search query: `has:attachment (subject:receipt OR subject:"order confirmation" OR subject:invoice)`.
- Use APScheduler in [src/app.py](src/app.py) for periodic sync.

### Phase 6: Homebox Receipt Attachment
- Extend `execute()` in [src/services/homebox.py](src/services/homebox.py) to always upload the receipt image as an attachment for these items.

### Phase 7: Frontend
- **Settings**: Add config fields for RW and GWS (with "Connect Gmail" button).
- **Receipts Tab**: New UI to monitor syncs, view pending receipts, and trigger batch processing.

## Decisions
- **Auth**: Use API Key for Receipt Wrangler.
- **Attachments**: Always attach receipts to Homebox items.
- **Vendor Detection**: Use SearXNG snippets to confirm merchants.
- **Search Scope**: Wide net on Gmail subjects to ensure coverage.