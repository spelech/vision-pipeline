# Changelog

All notable changes to this project are documented in this file.

## [3.6.1] - 2026-05-31

### Added
- Review queue items can now be deleted directly from the review page.

### Changed
- Item deletion now removes stored upload files when present.
- Visible version labels now match the current release version.

### Tests
- Added coverage for the review-page delete action, queue-card callback wiring, and delete cleanup behavior.

## [3.6.0] - 2026-05-31

### Added
- Configurable OpenAI-compatible LLM client resolution with support for `LLM_BASE_URL` and `LLM_API_KEY`.
- Backend and Gmail OCR paths now support local LiteLLM-style gateways without code changes.
- Additional test coverage for configurable LLM client behavior in node and Gmail OCR flows.

### Changed
- Pipeline and OCR client initialization now use shared LLM client construction with OpenRouter backward-compatible fallbacks.
- Settings/config secret surfaces now include generic LLM endpoint and key fields for migration-safe configuration.

### Migration Guidance
- No Alembic or database migration is required for this release.
- Existing OpenRouter deployments continue to work with `OPENROUTER_API_KEY`.
- To move to local LiteLLM, set `LLM_BASE_URL` and optionally `LLM_API_KEY`.

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