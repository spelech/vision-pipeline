# Test-Scraped Requirements and Design Document

Generated: 2026-05-25
Source of truth: automated test suite names, feature labels, and pytest feature metadata conventions.

## 1. Scope and Intent
This document captures product requirements and design constraints inferred from tests across:
- Backend unit/integration tests: `src/tests`
- Frontend unit/component tests: `web/src/test`
- End-to-end tests: `web/e2e`, `e2e`

The purpose is to keep feature intent synchronized with executable verification as the system evolves.

## 2. Feature Documentation Contract
Current test documentation model:
- Frontend tests use `Feature: <name> | <behavior>` naming in test titles.
- Backend tests include feature docstrings in newer files and descriptive function names in legacy files.
- Pytest enforces a feature marker convention via `pytest.ini` and collection hooks.

Design requirement:
- Every new test must include explicit feature intent, either through `Feature:` in title or an explicit test docstring.
- Prefer stable, behavior-oriented names over implementation details.

## 3. Frontend Requirements (from unit/component tests)

### 3.1 App Shell and Navigation
Requirements:
- The identify shell renders with primary header and default pipeline display.
- Navigation to review tab triggers queue fetch for `status=all`.
- Review filters switch data fetches among `all`, `pending`, and `approved`.

Design implications:
- Tab navigation must remain deterministic and data-driven.
- Review controls are a functional contract; labels and actions should remain testable.

Evidence:
- `Feature: identify-shell`
- `Feature: review-navigation`
- `Feature: review-filters`

### 3.2 Queue States and Bulk Review
Requirements:
- Empty queue state displays correct waiting message.
- Pending queue supports select-all and bulk approve.
- Bulk approve error responses surface an error toast.

Design implications:
- Queue state messaging must be explicit per state.
- Selection and bulk actions need clear feedback and error handling.

Evidence:
- `Feature: review-empty-state`
- `Feature: review-bulk-approve`
- `Feature: review-bulk-approve-error`

### 3.3 Identify and Upload Flows
Requirements:
- Single-file identify upload calls `/api/identify` and then fetches item details.
- Failed identify upload responses surface failure behavior.
- Batch upload supports multi-file submission.
- Failed batch upload responses surface an error toast.

Design implications:
- Upload UX must handle both happy-path and non-OK API responses.
- Follow-up item retrieval for identify is part of expected behavior.

Evidence:
- `Feature: identify-upload-single`
- `Feature: identify-upload-failure`
- `Feature: batch-upload`
- `Feature: batch-upload-failure`

### 3.4 Camera Capture and Fallbacks
Requirements:
- Camera modal opens/closes cleanly and stops media tracks on close.
- Permission-denied camera access falls back to capture file input.
- Missing mediaDevices API falls back to capture file input.
- Capture before video readiness surfaces a clear readiness error.

Design implications:
- Progressive enhancement is required for camera features.
- Capture flow must remain robust across browser capability differences.

Evidence:
- `Feature: camera-open-close`
- `Feature: camera-fallback-input`
- `Feature: camera-no-media-devices-fallback`
- `Feature: camera-capture-not-ready`

### 3.5 Pipeline Discovery and Fallback
Requirements:
- Pipeline fetch failures preserve default pipeline option availability.

Design implications:
- Default pipeline is a hard fallback and must always be selectable.

Evidence:
- `Feature: pipeline-fallback`

### 3.6 Asset Card Interactions
Requirements:
- Asset cards support collapsed/expanded state.
- Edited overrides are passed to execute callbacks.
- Selection toggles must function.
- Preview uses selected service.
- Technical payload visibility toggles.
- Action controls are disabled when selected services are empty.

Design implications:
- Asset card is a critical interaction contract for review/execution workflows.

Evidence:
- `Feature: asset-card-collapsed`
- `Feature: asset-card-expand`
- `Feature: asset-card-execute`
- `Feature: asset-card-select`
- `Feature: asset-card-preview`
- `Feature: asset-card-technical-toggle`
- `Feature: asset-card-service-empty`

### 3.7 Pipeline Editor Behavior
Requirements:
- Pipeline list and create flow must render and open editing UI.
- Registry sync must trigger fetch.
- Node add/remove operations are editable.
- Save failure path alerts user.
- Save-as-custom-copy path persists a custom pipeline id/name.
- Vision node configuration updates prompt content in saved payload.
- Helper logic must correctly resolve node defaults, persistence identity, and prompt preview behavior.

Design implications:
- Pipeline editor persistence strategy and helper logic are core behavioral contracts.
- Prompt and node helpers are tested as pure logic and should remain deterministic.

Evidence:
- `Feature: pipeline-editor-list`
- `Feature: pipeline-editor-create`
- `Feature: pipeline-editor-sync`
- `Feature: pipeline-editor-edit-nodes`
- `Feature: pipeline-editor-save-error`
- `Feature: pipeline-editor-save-copy-success`
- `Feature: pipeline-editor-vision-config`
- `Feature: pipeline-editor-helpers`
- `Feature: pipeline-editor-helper-prompts`
- `Feature: pipeline-editor-helper-preview`

### 3.8 Settings Behavior
Requirements:
- Settings load config/models/pipelines and render defaults.
- Model registry supports add/star/remove behaviors.
- Save path posts config and reports success.
- Save failure path reports error.
- Prompt templates are derived from pipeline schema when config templates are absent.
- Save payload omits `prompt_templates` when none are configured.
- Template formatting trims whitespace and supports create/delete flows.
- Template normalize/derive helper behavior is deterministic for array/object/invalid inputs.

Design implications:
- Settings is both configuration UI and migration bridge between legacy/current config shapes.

Evidence:
- `Feature: settings-load`
- `Feature: settings-model-add`
- `Feature: settings-save`
- `Feature: settings-save-error`
- `Feature: settings-derived-prompts`
- `Feature: settings-star-remove`
- `Feature: settings-save-without-templates`
- `Feature: settings-template-format-add`
- `Feature: settings-template-normalize`
- `Feature: settings-template-derive`

### 3.9 Preview Modal
Requirements:
- Preview modal renders payload.
- Close action invokes callback.
- Confirm action supports edited payload and callback propagation.

Evidence:
- `Feature: preview-modal-render`
- `Feature: preview-modal-close`
- `Feature: preview-modal-confirm`

## 4. Backend Requirements (from pytest)

### 4.1 API Surface
Requirements:
- Health endpoint returns service health.
- Identify endpoint handles image ingestion and pipeline execution behavior.
- Queue endpoint supports status filtering and returns expected item sets.
- Item fetch/update/rerun operations must function.
- Preview endpoint returns service payload and handles item-not-found.
- Execute endpoint submits to service integrations.
- Batch upload endpoint handles multi-file ingest.
- Bulk approve endpoint processes multiple item ids.
- Delete item endpoint removes files and DB record.
- Models endpoint returns catalog.
- Pipelines endpoint supports success/error handling and custom pipeline merge.
- Config endpoints mask secrets, preserve URL-like values, persist custom pipeline settings, and support legacy homebox email mapping.
- Search endpoint returns merged item data.
- Logs endpoint wraps messages.
- Locations endpoint handles missing header scenarios.

Evidence:
- `src/tests/test_api.py` test functions (`test_health_endpoint`, `test_identify_endpoint`, etc.)

### 4.2 App Utility and Config Logic
Requirements:
- Prompt templates normalize from list and mapping forms.
- Model favorites merge and deduplicate across legacy/current config layouts.
- JSON config loading tolerates missing/invalid/non-dict content.
- Merged user config deduplicates templates/favorites.
- Secret setter/getter keeps Homebox username/email synchronized.
- Pipeline resolution supports custom pipeline selection, registry lookup, and fallback behavior.

Evidence:
- `src/tests/test_app_utils.py` feature docstrings and test names

### 4.3 Pipeline Execution Strategies
Requirements:
- Advanced pipeline supports full search/scrape/refine path.
- Advanced pipeline guards unknown query cases and no-search-result cases.
- Composable pipeline supports custom order, conditional node skipping, and double refinement pass.

Evidence:
- `src/tests/test_advanced_pipeline.py`
- `src/tests/test_composable_pipeline.py`

### 4.4 Service Integration Contracts
Requirements:
- Homebox service supports new/update item execution and email/password auth path.
- Mealie service supports recipe creation and pre-enrichment behavior.
- Enrichment services (pricebuddy/changedetection) execute and support pre-enrichment.
- Payload construction helpers for services remain stable.

Evidence:
- `src/tests/test_homebox.py`
- `src/tests/test_mealie.py`
- `src/tests/test_enrichers.py`

### 4.5 Legacy and Concurrency Flows
Requirements:
- Validation and ingestion logic remain intact.
- Concurrent execution path remains supported.

Evidence:
- `src/tests/test_ingestion.py`
- `src/tests/test_validation.py`
- `src/tests/test_vision_v2.py`

## 5. End-to-End Requirements (Playwright)
Requirements:
- Queue displays assets and supports review-card expansion/editing.
- Preview modal opens/closes from review workflow.
- Execute action removes item from queue.
- Upload flow results in item visibility in queue.
- Live integration flow with Mealie and Homebox completes successfully.

Evidence:
- `web/e2e/app.spec.ts`
- `web/e2e/integration.spec.ts`
- `e2e/ingestion.spec.ts`
- `e2e/live_integrations.spec.ts`

## 6. Design Principles Implied by Tests
- API resilience: error and fallback paths are required behavior, not optional.
- Backward compatibility: legacy config keys and structures must still be honored.
- Deterministic transformation: prompt/template/pipeline helper logic must remain pure and predictable.
- Progressive enhancement: camera and pipeline-selection workflows need capability fallbacks.
- User feedback contract: operational failures must surface clear user-visible alerts/toasts.

## 7. Coverage and Verification Snapshot
Latest validated frontend coverage:
- Statements: 76.41%
- Branches: 71.50%
- Functions: 70.43%
- Lines: 78.21%

Latest validated backend coverage:
- Total: 80% (previous validated run in session)

## 8. Recommended Next Documentation/Testing Steps
- Add explicit `Feature:` docstrings to older backend tests in `test_api.py`, `test_homebox.py`, `test_mealie.py`, `test_enrichers.py`, etc., for consistency.
- Add an automated CI check that fails if new tests are missing feature metadata.
- Generate this document from a script (parsing test titles/docstrings) to keep it always current.
