#!/usr/bin/env bash
set -euo pipefail

python -c "from database import run_migrations; run_migrations()"
exec uvicorn app:app --host 0.0.0.0 --port 8501
