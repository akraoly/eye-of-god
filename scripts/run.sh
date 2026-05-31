#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

source .venv/bin/activate

echo "🧠 L'Œil de Dieu — Production"
export PYTHONPATH="$ROOT/backend"
cd backend

uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8001}" \
    --workers 1
