"""
SSO Engine — configuration OAuth2/OIDC/SAML.
Gestion des providers d'authentification, config stockée en DB.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import SsoProvider
import logging

log = logging.getLogger("SOC.SSO")

PROVIDER_PRESETS = {
    "oauth2_google": {
        "name": "Google Workspace",
        "auth_url":  "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes":    ["openid", "email", "profile"],
        "doc":       "https://developers.google.com/identity/protocols/oauth2/openid-connect",
    },
    "oauth2_azure": {
        "name": "Microsoft Azure AD / Entra ID",
        "auth_url":  "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        "scopes":    ["openid", "email", "profile", "User.Read"],
        "doc":       "https://docs.microsoft.com/en-us/azure/active-directory/develop/",
    },
    "oauth2_github": {
        "name": "GitHub Enterprise",
        "auth_url":  "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "scopes":    ["user:email", "read:org"],
        "doc":       "https://docs.github.com/en/developers/apps/building-oauth-apps",
    },
    "oauth2_okta": {
        "name": "Okta",
        "auth_url":  "https://{domain}/oauth2/default/v1/authorize",
        "token_url": "https://{domain}/oauth2/default/v1/token",
        "scopes":    ["openid", "email", "profile", "groups"],
        "doc":       "https://developer.okta.com/docs/reference/api/oidc/",
    },
    "saml": {
        "name": "SAML 2.0 (générique)",
        "doc": "https://wiki.oasis-open.org/security/FrontPage",
        "note": "Fournir entity_id, SSO URL, certificat X.509",
    },
    "oidc": {
        "name": "OpenID Connect (générique)",
        "doc": "https://openid.net/connect/",
        "note": "Fournir issuer_url, client_id, client_secret",
    },
}


class SsoEngine:

    def list_providers(self, db: Session) -> list:
        providers = db.query(SsoProvider).order_by(desc(SsoProvider.created_at)).all()
        return [self._prov_dict(p) for p in providers]

    def get_presets(self) -> list:
        return [{"type": k, **{kk: vv for kk, vv in v.items() if kk != "scopes"},
                 "scopes": v.get("scopes", [])} for k, v in PROVIDER_PRESETS.items()]

    def create_provider(self, db: Session, name: str, provider_type: str,
                        client_id: str = None, client_secret: str = None,
                        tenant_id: str = None, issuer_url: str = None) -> dict:
        existing = db.query(SsoProvider).filter(SsoProvider.name == name).first()
        if existing:
            return {"error": f"Provider '{name}' déjà configuré"}
        prov = SsoProvider(
            name=name, provider_type=provider_type,
            client_id=client_id, client_secret="[REDACTED]" if client_secret else None,
            tenant_id=tenant_id, issuer_url=issuer_url, enabled=False,
        )
        db.add(prov); db.commit(); db.refresh(prov)
        log.info(f"[SSO] Provider créé: {name} ({provider_type})")
        return self._prov_dict(prov)

    def toggle_provider(self, db: Session, provider_id: int, enabled: bool) -> Optional[dict]:
        prov = db.query(SsoProvider).filter(SsoProvider.id == provider_id).first()
        if not prov: return None
        prov.enabled = enabled
        prov.last_sync = datetime.utcnow() if enabled else prov.last_sync
        db.commit()
        return self._prov_dict(prov)

    def delete_provider(self, db: Session, provider_id: int) -> bool:
        prov = db.query(SsoProvider).filter(SsoProvider.id == provider_id).first()
        if not prov: return False
        db.delete(prov); db.commit()
        return True

    def stats(self, db: Session) -> dict:
        total   = db.query(SsoProvider).count()
        enabled = db.query(SsoProvider).filter(SsoProvider.enabled == True).count()
        return {"total_providers": total, "enabled_providers": enabled,
                "available_presets": len(PROVIDER_PRESETS)}

    def _prov_dict(self, p: SsoProvider) -> dict:
        preset = PROVIDER_PRESETS.get(p.provider_type, {})
        return {"id": p.id, "name": p.name, "provider_type": p.provider_type,
                "has_client_id": bool(p.client_id), "tenant_id": p.tenant_id,
                "issuer_url": p.issuer_url, "enabled": p.enabled,
                "user_count": p.user_count,
                "last_sync": p.last_sync.isoformat() if p.last_sync else None,
                "doc": preset.get("doc"), "scopes": preset.get("scopes", [])}


sso_engine = SsoEngine()
