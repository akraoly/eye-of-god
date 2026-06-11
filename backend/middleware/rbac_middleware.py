"""
Middleware RBAC — vérifie les permissions par rôle sur chaque requête.

En mode actuel : info uniquement (log warning, pas de blocage).
Mettre RBAC_ENFORCE=True dans .env pour activer le blocage strict.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Désactivé par défaut pour ne pas casser la session admin existante
RBAC_ENFORCE = os.getenv("RBAC_ENFORCE", "false").lower() == "true"

# Routes publiques exclues du RBAC
_PUBLIC_PATHS = {"/api/auth/login", "/api/auth/refresh", "/", "/docs", "/openapi.json"}
_PUBLIC_PREFIXES = ("/docs", "/openapi", "/redoc", "/api/auth/login")


def register_rbac_middleware(app):
    """Enregistre le middleware RBAC sur l'app FastAPI."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from core.security.rbac import rbac

    class RBACMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if request.scope.get("type") == "websocket":
                return await call_next(request)
            path = request.url.path

            # Routes publiques toujours autorisées
            if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
                return await call_next(request)

            # Extraire le rôle du token JWT
            user_role = "admin"  # fallback si pas de role dans le token
            try:
                from core.auth.jwt_handler import decode_access_token
                auth_header = request.headers.get("Authorization", "")
                token = auth_header.replace("Bearer ", "").strip()
                if token:
                    payload = decode_access_token(token)
                    user_role = payload.get("role", "admin") if isinstance(payload, dict) else "admin"
            except Exception:
                pass

            # Vérification RBAC
            can_access = rbac.can_access_path(user_role, path, request.method)

            if not can_access:
                if RBAC_ENFORCE:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": f"Permission refusée — rôle '{user_role}' insuffisant pour {path}"
                        },
                    )
                else:
                    logger.warning(
                        "RBAC [non-enforced]: rôle '%s' n'a pas accès à %s %s",
                        user_role, request.method, path,
                    )

            return await call_next(request)

    app.add_middleware(RBACMiddleware)
    logger.info("RBAC middleware enregistré (enforce=%s)", RBAC_ENFORCE)
