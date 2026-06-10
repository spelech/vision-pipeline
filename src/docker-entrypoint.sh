#!/usr/bin/env bash
set -euo pipefail

python -c "from database import run_migrations; run_migrations()"
LOG_LEVEL_LOWER=$(echo "${LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')
exec uvicorn app:app --host 0.0.0.0 --port 8501 --log-level $LOG_LEVEL_LOWER
