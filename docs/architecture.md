# Architecture — L'Œil de Dieu

## Flux principal

```
User → POST /api/chat/ → ChatService → ContextBuilder → LLMClient (Claude)
                                    ↓                          ↓
                              MemoryEngine              (réponse brute)
                                    ↓                          ↓
                              Storage (SQLite)    ← context_builder.add_message
                                                           ↓
                                                      Response JSON
```

## Couches

| Couche | Responsabilité |
|--------|---------------|
| `api/routes/` | HTTP uniquement — parsing, validation, réponse |
| `services/` | Logique métier — orchestration |
| `core/llm/` | Intégration Claude API — client, prompts, contexte |
| `core/memory/` | Mémoire 3 niveaux — storage + engine |
| `core/agents/` | Agents spécialisés — cyber, life, system |
| `core/tools/` | Interaction OS — terminal, fichiers, sécurité |
| `database/` | Modèles SQLAlchemy + connexion SQLite |

## Mémoire 3 niveaux

```
Mémoire courte (RAM)
  → context_builder._sessions[session_id]
  → Limite : SHORT_TERM_LIMIT * 2 messages
  → Perdue au redémarrage

Mémoire utilisateur (DB)
  → table memories WHERE type = 'user'
  → Extraite automatiquement des messages
  → Triée par importance décroissante
  → Injectée dans chaque prompt système

Mémoire long terme (DB)
  → table conversations
  → Tout l'historique
  → Base pour future recherche vectorielle
```

## Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| POST | `/api/chat/` | Conversation avec Claude |
| DELETE | `/api/chat/session/{id}` | Vider la mémoire courte |
| POST | `/api/memory/save` | Sauvegarder une mémoire |
| GET | `/api/memory/get` | Lister les mémoires |
| DELETE | `/api/memory/{id}` | Supprimer une mémoire |
| GET | `/api/memory/profile` | Profil utilisateur |
| POST | `/api/memory/profile` | Mettre à jour profil |
| GET | `/api/user/profile` | Profil complet |
| GET | `/api/system/health` | Santé du système |
| GET | `/api/system/metrics` | CPU/RAM/Disk |
| GET | `/api/system/agents` | Liste des agents |
| POST | `/api/system/agents/dispatch` | Dispatcher une tâche |
