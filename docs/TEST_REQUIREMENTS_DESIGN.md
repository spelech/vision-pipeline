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

<!-- AUTO-GENERATED-TEST-INDEX:START -->
## 9. Auto-Generated Test Index
Updated by script: scripts/update-test-requirements-index.mjs

### 9.1 Frontend Feature Tests
- web/src/test/App.test.tsx
  - identify-shell | renders progress text and header
  - review-navigation | fetches and displays the queue
  - review-empty-state | shows empty state when queue is empty
  - review-filters | changes queue filter from review controls
  - identify-upload-single | uploads a single file and fetches item details
  - batch-upload | uploads batch files in batch tab
  - review-bulk-approve | approves selected pending items in bulk
  - camera-open-close | opens camera modal and closes it cleanly
  - pipeline-fallback | falls back to default pipeline option when pipeline fetch fails
  - identify-upload-failure | handles failed identify upload response
  - camera-fallback-input | falls back to capture input when camera access fails
  - camera-capture-not-ready | shows readiness error when capture is attempted too early
  - batch-upload-failure | shows error toast when batch upload request fails
  - camera-no-media-devices-fallback | uses capture file input when media devices are unavailable
  - review-bulk-approve-error | surfaces error toast when bulk approve endpoint returns non-OK
- web/src/test/AssetCard.test.tsx
  - asset-card-collapsed | renders collapsed state correctly
  - asset-card-expand | expands when clicking the chevron
  - asset-card-execute | updates edit data and fires onExecute with overrides
  - asset-card-select | toggles selection
  - asset-card-preview | uses first selected service for preview
  - asset-card-technical-toggle | shows technical payload JSON when toggled
  - asset-card-service-empty | disables actions when no services are selected
- web/src/test/PipelineEditor.test.tsx
  - pipeline-editor-list | renders pipelines
  - pipeline-editor-create | can create a new pipeline
  - pipeline-editor-sync | triggers registry sync fetch
  - pipeline-editor-edit-nodes | edits nodes by removing and adding blocks
  - pipeline-editor-save-error | shows alert when save fails
  - pipeline-editor-save-copy-success | saves a non-custom pipeline as a custom copy
  - pipeline-editor-vision-config | updates vision prompt through node settings and saves
  - pipeline-editor-helpers | resolves node lists for configured, advanced, and fallback pipelines
  - pipeline-editor-helper-prompts | detects persistence flags and prompt fallbacks
  - pipeline-editor-helper-preview | formats prompt preview text for empty and long values
- web/src/test/PreviewModal.test.tsx
  - preview-modal-render | renders correctly and shows payload
  - preview-modal-close | calls onClose when close button clicked
  - preview-modal-confirm | allows payload editing and confirms
- web/src/test/Settings.test.tsx
  - settings-load | renders correctly and loads data
  - settings-model-add | allows adding a new model
  - settings-save | allows saving settings
  - settings-derived-prompts | derives prompt templates from pipeline schema when config templates are absent
  - settings-star-remove | toggles star and removes model from registry
  - settings-save-error | shows error alert when save fails
  - settings-save-without-templates | omits prompt_templates when none are configured
  - settings-template-format-add | formats and creates prompt templates from the editor
  - settings-template-normalize | normalizes array/object and handles invalid template values
  - settings-template-derive | derives prompt templates from pipeline schema prompt keys only

### 9.2 Backend Feature Tests
- src/tests/test_advanced_pipeline.py
  - Feature labels:
    - run advanced pipeline end-to-end with search/scrape/refine context path.
    - guard search/scrape path when query cannot be trusted.
    - skip scraping/refine when search returns no candidate URLs.
  - Test functions:
    - test_advanced_pipeline_runs_full_search_scrape_refine_flow
    - test_advanced_pipeline_skips_search_when_query_unknown
    - test_advanced_pipeline_handles_no_search_results
- src/tests/test_api.py
  - Test functions:
    - test_health_endpoint
    - test_identify_endpoint
    - test_get_locations_endpoint
    - test_preview_endpoint
    - test_execute_endpoint
    - test_batch_upload_endpoint
    - test_bulk_approve_endpoint
    - test_queue_endpoint_all_status_returns_items
    - test_get_item_endpoint_returns_item
    - test_update_and_rerun_item_endpoints
    - test_identify_returns_500_when_pipeline_run_fails
    - test_models_endpoint_returns_catalog
    - test_pipelines_endpoint_handles_success_and_error
    - test_get_config_masks_and_preserves_url_secrets
    - test_update_config_persists_custom_pipelines_and_secret
    - test_search_endpoint_returns_merged_item_data
    - test_logs_endpoint_wraps_messages
    - test_locations_endpoint_handles_missing_headers
    - test_pipelines_endpoint_merges_custom_from_config_file
    - test_preview_endpoint_item_not_found
    - test_delete_item_endpoint_deletes_files_and_item
    - test_update_config_handles_legacy_homebox_email
- src/tests/test_app_utils.py
  - Feature labels:
    - normalize mixed prompt template representations into stable objects.
    - convert prompt maps into UI-friendly template arrays.
    - collect deduplicated configured model favorites from legacy and nested config shapes.
    - safely parse config files while tolerating missing and malformed content.
    - merge legacy/current user config and dedupe templates and model favorites.
    - keep Homebox username/email environment variables in sync.
    - select composable pipeline when custom pipeline id is configured.
    - resolve registered pipeline ids and fallback to default for unknown ids.
  - Test functions:
    - test_normalize_prompt_templates_from_list_and_dict
    - test_normalize_prompt_templates_from_mapping
    - test_merge_unique_and_extract_model_favorites
    - test_load_json_file_handles_missing_invalid_and_nondict
    - test_load_merged_user_config_merges_and_dedupes
    - test_secret_get_set_homebox_username
    - test_get_pipeline_uses_custom_pipeline_when_config_matches
    - test_get_pipeline_uses_registry_and_default_fallback
- src/tests/test_composable_pipeline.py
  - Test functions:
    - test_pipeline_respects_custom_order
    - test_pipeline_skips_search_if_no_query
    - test_pipeline_skips_scrape_if_no_url
    - test_double_refinement_pass
- src/tests/test_enrichers.py
  - Test functions:
    - test_pricebuddy_execution
    - test_changedetection_execution
    - test_enrichers_pre_enrichment
- src/tests/test_homebox.py
  - Test functions:
    - test_homebox_execution_new_item
    - test_homebox_execution_update_item
    - test_homebox_auth_email_password
    - test_homebox_get_payload
- src/tests/test_ingestion.py
  - Test functions:
    - test_pipeline_logic
    - test_api_endpoint
- src/tests/test_mealie.py
  - Test functions:
    - test_mealie_execution_new_recipe
    - test_mealie_pre_enrichment
    - test_mealie_get_payload
- src/tests/test_validation.py
  - Test functions:
    - test_pipeline_validation_logic
- src/tests/test_vision_v2.py
  - Test functions:
    - test_homebox_execution
    - test_concurrent_execution

### 9.3 End-to-End Scenarios
- e2e/ingestion.spec.ts
  - Complete End-to-End Flow
- e2e/live_integrations.spec.ts
  - Complete End-to-End Flow with Mealie and Homebox
- web/e2e/app.spec.ts
  - should display assets in the queue
  - should expand asset card and edit fields
  - should open and close the preview modal
  - should execute and remove item from queue
- web/e2e/integration.spec.ts
  - should upload an image and appear in queue
  - should allow editing and executing an asset
<!-- AUTO-GENERATED-TEST-INDEX:END -->
