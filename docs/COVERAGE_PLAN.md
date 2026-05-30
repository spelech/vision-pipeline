# Coverage Plan and Status

## Target
- Backend (pytest + coverage): >= 90% statements
- Frontend (vitest coverage): >= 90% statements

## Current Baseline (latest run)
- Backend statements: 87% (latest validated full run)
- Frontend statements: 90.08% (745/827)

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
- Added frontend processing state coverage tests in `web/src/test/ProcessingDashboard.test.tsx`.
- Expanded `AssetCard` branch coverage for service retries, stage status rendering, data-uri image paths, and exception recovery.
- Expanded `PipelineEditor` save/fallback branch tests and `Settings` payload persistence tests.
- Added `App` processing log polling tests for success and non-OK polling paths.
- Coverage improved from previous baseline:
  - Backend statements: 83% -> 87%
  - Frontend statements: 82.70% -> 90.08%

## Next Steps to Reach >= 90%
1. Backend:
  - Add tests for remaining queue/task branches in `src/app.py` (item reruns, edge-case queue filters, session log fallbacks).
  - Add more API-level tests for service execution and batch processing alternate error paths.
2. Frontend:
  - Keep statement threshold at >= 90% with branch-focused additions when introducing new UI paths.
  - Target remaining gaps in `web/src/components/AssetCard.tsx`, `web/src/components/PipelineEditor.tsx`, and `web/src/App.tsx` to improve resilience margin above threshold.
  - Add focused tests for queue callbacks and preview modal close/confirm regression paths when refactoring UI wrappers.
3. Enforce threshold after passing:
   - Backend: set `--cov-fail-under=90` in CI backend gate.
   - Frontend: configure vitest coverage threshold to 90 in `web/vite.config.ts`.
