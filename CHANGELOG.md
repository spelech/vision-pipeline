# Changelog

All notable changes to this project are documented in this file.

## [3.5.0] - 2026-05-30

### Added
- Dedicated `ReceiptPipeline` class and pipeline registry wiring for receipt-specific workflows.
- Receipt Wrangler process support in API routes and receipts UI actions.
- Gmail connect action in settings UI.

### Changed
- Secret compatibility updates for receipt and Gmail integrations, including token/key fallback handling.
- Receipt metadata propagation improvements in helper/service data shaping.

### Tests
- Added and updated backend/frontend tests for receipt wrangler processing, gmail ingestor behavior, receipt pipeline behavior, and related UI flows.