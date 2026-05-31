#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d ".venv" ]; then
    echo "⚠️  Environnement virtuel absent — lance d'abord : bash scripts/setup.sh"
    exit 1
fi

source .venv/bin/activate

echo "🧠 L'Œil de Dieu — Mode développement (auto-reload)"
echo "📡 Backend  → http://localhost:8001"
echo "📖 Docs API → http://localhost:8001/docs"
echo ""

export PYTHONPATH="$ROOT/backend"
cd backend

uvicorn app.main:app \
    --host "0.0.0.0" \
    --port "8001" \
    --reload \
    --reload-dir .
