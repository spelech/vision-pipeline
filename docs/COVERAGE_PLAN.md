# Coverage Plan and Status

## Target
- Backend (pytest + coverage): >= 90% statements
- Frontend (vitest coverage): >= 90% statements

## Current Baseline (latest run)
- Backend statements: 83% (1553/1791)
- Frontend statements: 82.70% (684/827)

## Commands
- Backend coverage:
  - `./venv/Scripts/python.exe -m pytest src/tests --cov=src --cov-report=term --cov-report=xml:coverage/python-coverage.xml`
- Frontend coverage:
  - `cd web && npm run test:coverage`

## High-Impact Gaps
### Backend
- Primary gap: `src/app.py` at ~77%
- Hotspot groups with largest misses:
  - Pipeline/config endpoints around `/api/pipelines`, `/api/models`, `/api/config`
  - Batch/queue lifecycle endpoints
  - SPA fallback and error branches

### Frontend
- Primary gaps:
  - `web/src/components/AssetCard.tsx`
  - `web/src/components/PipelineEditor.tsx`
  - `web/src/components/Settings.tsx`
  - `web/src/App.tsx`

## Work Completed in This Pass
- Added backend endpoint-coverage tests in `src/tests/test_app_config_endpoints.py`.
- Added frontend tab/wrapper/queue coverage tests in `web/src/test/AppTabsAndQueueCards.test.tsx`.
- Coverage improved from previous baseline:
  - Backend statements: 80% -> 83%
  - Frontend statements: 81.86% -> 82.70%

## Next Steps to Reach >= 90%
1. Backend:
   - Add tests for queue endpoints and batch processing error paths in `src/app.py`.
   - Add API-level tests for scrape endpoint success/failure branches.
2. Frontend:
   - Add interaction-path tests for `AssetCard` service states and technical/error branches.
   - Expand `PipelineEditor` and `Settings` branch coverage for validation/save failure states.
3. Enforce threshold after passing:
   - Backend: set `--cov-fail-under=90` in CI backend gate.
   - Frontend: configure vitest coverage threshold to 90 in `web/vite.config.ts`.
