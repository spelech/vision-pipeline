#!/usr/bin/env bash
# Start the debug environment and the application server

# Ensure we are in the project root
cd "$(dirname "$0")/.."

echo "🚀 Starting debug containers..."
docker compose up -d

echo "🔧 Running migrations..."
docker exec vision-pipeline-dev python -c "from database import run_migrations; run_migrations()"

echo "⚡ Starting application server (uvicorn) in debug mode..."
echo "📍 Access UI at http://localhost:8461"
docker exec vision-pipeline-dev uvicorn app:app --host 0.0.0.0 --port 8501 --log-level debug --reload
