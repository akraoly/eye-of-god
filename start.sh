#!/bin/bash
# L'Œil de Dieu — démarrage rapide

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend/web"
LOG_BACK="/tmp/eog_backend.log"
LOG_FRONT="/tmp/eog_frontend.log"

# ── Couleurs ──────────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; C='\033[0;36m'; B='\033[1m'; N='\033[0m'

echo -e "${C}${B}"
echo "  👁️  L'Œil de Dieu — démarrage"
echo -e "${N}"

# ── Vérifications ─────────────────────────────────────────────────────────────
if [ ! -f "$VENV/bin/activate" ]; then
  echo -e "${R}❌ Virtualenv introuvable : $VENV${N}"
  echo "   Lance d'abord : python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo -e "${Y}⚠️  node_modules absent — installation en cours...${N}"
  cd "$FRONTEND" && npm install --silent
fi

# ── Arrêter les anciens processus ─────────────────────────────────────────────
pkill -f "uvicorn app.main" 2>/dev/null
pkill -f "vite.*3001"       2>/dev/null
sleep 1

# ── Backend ───────────────────────────────────────────────────────────────────
echo -e "${B}[1/2]${N} Démarrage du backend..."
source "$VENV/bin/activate"
export PYTHONPATH="$BACKEND"
cd "$BACKEND"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > "$LOG_BACK" 2>&1 &
BACK_PID=$!

# Attendre que le backend soit prêt
for i in $(seq 1 15); do
  sleep 1
  if curl -s http://localhost:8001/ > /dev/null 2>&1; then
    echo -e "    ${G}✅ Backend prêt${N}  (pid $BACK_PID) — http://localhost:8001"
    break
  fi
  if [ $i -eq 15 ]; then
    echo -e "    ${R}❌ Backend n'a pas démarré. Logs : $LOG_BACK${N}"
    tail -5 "$LOG_BACK"
    exit 1
  fi
done

# ── Frontend ──────────────────────────────────────────────────────────────────
echo -e "${B}[2/2]${N} Démarrage du frontend..."
cd "$FRONTEND"
nohup npm run dev > "$LOG_FRONT" 2>&1 &
FRONT_PID=$!

for i in $(seq 1 15); do
  sleep 1
  if curl -s http://localhost:3001/ > /dev/null 2>&1; then
    echo -e "    ${G}✅ Frontend prêt${N} (pid $FRONT_PID) — http://localhost:3001"
    break
  fi
  if [ $i -eq 15 ]; then
    echo -e "    ${R}❌ Frontend n'a pas démarré. Logs : $LOG_FRONT${N}"
    tail -5 "$LOG_FRONT"
    exit 1
  fi
done

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${G}${B}  🚀 L'Œil de Dieu est en ligne !${N}"
echo -e "  ${B}→ Application :${N}  http://localhost:3001"
echo -e "  ${B}→ API docs    :${N}  http://localhost:8001/docs"
echo -e "  ${B}→ Login       :${N}  admin / oeil2026"
echo ""
echo -e "  Logs : $LOG_BACK"
echo -e "         $LOG_FRONT"
echo ""
echo -e "  ${Y}Pour arrêter :${N} pkill -f 'uvicorn app.main'; pkill -f 'vite.*3001'"
