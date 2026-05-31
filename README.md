# 🧠 L'Œil de Dieu — v1.0 MVP

Compagnon numérique personnel ultra avancé. Conçu pour évoluer sur 10 ans.

## Démarrage rapide

```bash
cd /home/kali/eye-of-god

# 1. Installation
bash scripts/setup.sh

# 2. Configurer la clé API
nano .env
# → ANTHROPIC_API_KEY=sk-ant-...

# 3. Lancer
bash scripts/dev.sh
```

**Backend** → http://localhost:8001  
**Docs API** → http://localhost:8001/docs  
**Frontend** → http://localhost:3001 (après `npm install && npm run dev` dans frontend/web/)

## Architecture

```
User → FastAPI → ChatService → Claude API
                     ↓
               MemoryEngine → SQLite
                     ↓
               Context enrichi → meilleure réponse
```

## Mémoire 3 niveaux

| Niveau | Stockage | Description |
|--------|----------|-------------|
| Courte durée | RAM | Messages de la session en cours |
| Utilisateur | SQLite | Infos extraites automatiquement (nom, prefs...) |
| Long terme | SQLite | Tout l'historique des conversations |

## Endpoints principaux

```
POST /api/chat/              → parler à l'IA
POST /api/memory/save        → sauvegarder une mémoire
GET  /api/memory/get         → lister les mémoires
GET  /api/user/profile       → profil complet
GET  /api/system/health      → santé du système
```

## Structure

```
eye-of-god/
├── backend/
│   ├── app/           # FastAPI entry point + config
│   ├── api/routes/    # Endpoints HTTP
│   ├── core/
│   │   ├── llm/       # Claude API client + prompts
│   │   ├── memory/    # Moteur mémoire 3 niveaux
│   │   ├── agents/    # Agents spécialisés
│   │   └── tools/     # Terminal, fichiers, sécurité
│   ├── services/      # Logique métier
│   └── database/      # Modèles SQLAlchemy
├── frontend/web/      # React + Vite
├── scripts/           # setup.sh, dev.sh, run.sh
├── docs/              # Architecture, vision, roadmap
└── docker/            # Dockerfile + docker-compose
```

## Tests

```bash
cd backend
pip install pytest httpx
python -m pytest tests/ -v
```

## Prochaines étapes (v1.1)

- Mémoire vectorielle (ChromaDB)
- CyberAgent complet (Nmap, analyse vuln)
- Interface voix (Whisper)
- Vision (Claude Vision API)
