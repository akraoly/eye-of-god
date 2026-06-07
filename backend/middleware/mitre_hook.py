"""
Middleware léger MITRE — intercepte les requêtes entrantes et log en arrière-plan
l'action MITRE correspondante sans bloquer le traitement de la requête.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger("mitre_hook")

# ── Mapping chemin URL (pattern) + méthode → action_type ─────────────────────

PATH_ACTION_MAP: dict[tuple[str, str], str] = {
    ("/audio/record",                          "POST"): "audio_capture",
    ("/cameras/snapshot",                      "POST"): "camera_snapshot",
    ("/capture/start",                         "POST"): "network_sniffing",
    ("/post-exploit/keylogger/start",          "POST"): "keylogger",
    ("/post-exploit/clipboard",                "GET"):  "clipboard_capture",
    ("/post-exploit/forms",                    "GET"):  "form_grabber",
    ("/exfil/dns",                             "POST"): "exfil_dns",
    ("/exfil/icmp",                            "POST"): "exfil_icmp",
    ("/exfil/http",                            "POST"): "exfil_http",
    ("/c2",                                    "POST"): "c2_beacon",
    ("/ble/scan",                              "GET"):  "ble_scan",
    ("/ble/devices/{mac}/gatt/read",           "GET"):  "ble_gatt_read",
    ("/ble/devices/{mac}/gatt/write",          "POST"): "ble_gatt_write",
    ("/rfid/scan",                             "POST"): "rfid_scan",
    ("/rfid/clone",                            "POST"): "rfid_clone",
    ("/sdr/listen",                            "POST"): "sdr_listen",
    ("/sdr/recordings/{id}/replay",            "POST"): "sdr_replay",
}

# Pré-compiler les patterns pour les routes paramétrées
_COMPILED_PATTERNS: list[tuple[re.Pattern, str, str]] = []

for (path_template, method), action in PATH_ACTION_MAP.items():
    # Convertit {param} en [^/]+ pour le matching
    pattern_str = re.sub(r"\{[^}]+\}", r"[^/]+", path_template)
    pattern_str = "^" + pattern_str + "$"
    _COMPILED_PATTERNS.append((re.compile(pattern_str), method, action))


def identify_action(method: str, path: str) -> Optional[str]:
    """
    Retourne l'action_type correspondant à la méthode + chemin,
    ou None si le chemin n'est pas mappé.
    """
    # Normalise: supprime le préfixe /api s'il est présent
    normalized = path
    if normalized.startswith("/api"):
        normalized = normalized[4:]

    # Supprime les query strings
    if "?" in normalized:
        normalized = normalized.split("?", 1)[0]

    for pattern, pat_method, action in _COMPILED_PATTERNS:
        if pat_method == method and pattern.match(normalized):
            return action
    return None


class MitreLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware ASGI non-bloquant : log l'action MITRE en background task
    après que la réponse ait été envoyée.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Seulement si la requête a réussi (2xx) et est mappée
        if 200 <= response.status_code < 300:
            action_type = identify_action(request.method, request.url.path)
            if action_type:
                campaign_id = (
                    request.headers.get("X-Campaign-ID")
                    or request.query_params.get("campaign_id")
                )
                if campaign_id:
                    asyncio.create_task(
                        _bg_log(campaign_id, action_type, request)
                    )

        return response


async def _bg_log(campaign_id: str, action_type: str, request: Request) -> None:
    """Tâche d'arrière-plan : crée une session DB et log l'événement MITRE."""
    try:
        from database.db import SessionLocal
        from services.mitre.mitre_mapper_service import MitreMapperService

        db = SessionLocal()
        try:
            svc = MitreMapperService()
            details = {
                "method": request.method,
                "path": str(request.url.path),
                "client": request.client.host if request.client else None,
            }
            await svc.log_action(campaign_id, action_type, details=details, db=db)
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Erreur log MITRE background: %s", exc)


# Alias fonctionnel pour compatibilité (add_middleware avec fonction)
async def mitre_logging_middleware(request: Request, call_next) -> Response:
    """Version fonctionnelle du middleware (pour app.middleware('http'))."""
    response = await call_next(request)

    if 200 <= response.status_code < 300:
        action_type = identify_action(request.method, request.url.path)
        if action_type:
            campaign_id = (
                request.headers.get("X-Campaign-ID")
                or request.query_params.get("campaign_id")
            )
            if campaign_id:
                asyncio.create_task(
                    _bg_log(campaign_id, action_type, request)
                )

    return response
