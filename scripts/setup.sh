#!/bin/bash
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo "🧠 L'Œil de Dieu — Installation"
echo "================================"

# Vérifier Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 requis (non trouvé)"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo "✅ Python $PYTHON_VERSION détecté"

# Créer virtualenv
if [ ! -d ".venv" ]; then
    echo "→ Création de l'environnement virtuel..."
    python3 -m venv .venv
fi
source .venv/bin/activate

# Installer dépendances
echo "→ Installation des dépendances..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✅ Dépendances installées"

# Créer répertoires data
mkdir -p data/logs data/user_files

# Copier .env si absent
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  Fichier .env créé."
    echo "   Configure ta clé Anthropic dans .env :"
    echo "   ANTHROPIC_API_KEY=sk-ant-..."
fi

echo ""
echo "✅ Installation terminée !"
echo ""
echo "👉 Étape suivante :"
echo "   1. Édite .env et ajoute ton ANTHROPIC_API_KEY"
echo "   2. Lance : bash scripts/dev.sh"
echo ""
