"""
RBAC — Gestion des rôles et permissions.

Rôles : admin, auditor, client, viewer
"""
from __future__ import annotations

import fnmatch
import logging

logger = logging.getLogger(__name__)

ROLES: dict[str, dict] = {
    "admin": {
        "permissions": ["*"],
        "description": "Accès total à toutes les fonctionnalités",
        "color": "#ff4444",
    },
    "auditor": {
        "permissions": [
            "soc.*", "offensive.*", "reports.*", "rag.*",
            "ble.*", "sdr.*", "rfid.*", "cameras.*", "audio.*",
            "chat.*", "terminal.*", "code.*", "vision.*",
            "knowledge.*", "memory.*", "autonomy.*",
            "aegis.*", "osint.*", "credentials.*", "threat-intel.*",
            "forensics.*", "privesc.*", "lateral.*", "post-exploit.*",
            "exfil.*", "lab.*", "fuzzing.*", "mitre.*",
            "sentinel.*", "system.read", "user.read",
        ],
        "description": "Accès complet aux outils de pentest et SOC",
        "color": "#ff8800",
    },
    "client": {
        "permissions": [
            "reports.read", "reports.download",
            "soc.read", "soc.alerts",
            "dashboard.read", "mitre.read",
            "user.me",
        ],
        "description": "Accès limité aux rapports et au suivi",
        "color": "#4488ff",
    },
    "viewer": {
        "permissions": [
            "dashboard.read", "reports.read", "user.me",
        ],
        "description": "Lecture seule du dashboard et des rapports",
        "color": "#888888",
    },
}

# Mapping route prefix → permission namespace
ROUTE_PERMISSIONS: dict[str, str] = {
    "/api/chat":         "chat",
    "/api/soc":          "soc",
    "/api/offensive":    "offensive",
    "/api/reports":      "reports",
    "/api/rag":          "rag",
    "/api/ble":          "ble",
    "/api/sdr":          "sdr",
    "/api/rfid":         "rfid",
    "/api/cameras":      "cameras",
    "/api/audio":        "audio",
    "/api/terminal":     "terminal",
    "/api/code":         "code",
    "/api/vision":       "vision",
    "/api/knowledge":    "knowledge",
    "/api/memory":       "memory",
    "/api/autonomy":     "autonomy",
    "/api/aegis":        "aegis",
    "/api/osint":        "osint",
    "/api/credentials":  "credentials",
    "/api/threat-intel": "threat-intel",
    "/api/forensics":    "forensics",
    "/api/privesc":      "privesc",
    "/api/lateral":      "lateral",
    "/api/post-exploit": "post-exploit",
    "/api/exfil":        "exfil",
    "/api/lab":          "lab",
    "/api/fuzzing":      "fuzzing",
    "/api/mitre":        "mitre",
    "/api/sentinel":     "sentinel",
    "/api/system":       "system",
    "/api/user":         "user",
    "/api/users":        "user",
}


class RBACManager:

    @staticmethod
    def check_permission(user_role: str, required_permission: str) -> bool:
        role = ROLES.get(user_role)
        if not role:
            return False
        for perm in role["permissions"]:
            if perm == "*":
                return True
            if fnmatch.fnmatch(required_permission, perm):
                return True
        return False

    @staticmethod
    def get_user_permissions(user_role: str) -> list[str]:
        role = ROLES.get(user_role)
        return role["permissions"] if role else []

    @staticmethod
    def get_available_roles() -> dict:
        return {
            name: {
                "description": info["description"],
                "color": info["color"],
                "permission_count": len(info["permissions"]),
            }
            for name, info in ROLES.items()
        }

    @staticmethod
    def permission_for_path(path: str, method: str = "GET") -> str:
        """Retourne la permission requise pour un chemin API."""
        for prefix, namespace in ROUTE_PERMISSIONS.items():
            if path.startswith(prefix):
                action = "read" if method == "GET" else "write"
                return f"{namespace}.{action}"
        return "unknown"

    @staticmethod
    def can_access_path(user_role: str, path: str, method: str = "GET") -> bool:
        if user_role == "admin":
            return True
        perm = RBACManager.permission_for_path(path, method)
        if perm == "unknown":
            return True  # Routes non mappées restent accessibles
        return RBACManager.check_permission(user_role, perm)


rbac = RBACManager()
