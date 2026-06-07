"""
Routes /api/users — Gestion multi-utilisateurs (admin only pour la plupart).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from core.auth.password import hash_password, verify_password
from core.security.rbac import rbac, ROLES
from database.db import get_db
from database.models import AppUser

router = APIRouter()


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    is_active: Optional[bool] = None


class ChangeRoleRequest(BaseModel):
    role: str


class ChangePasswordRequest(BaseModel):
    new_password: str


class MyPasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _user_dict(u: AppUser) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "display_name": u.display_name or u.username,
        "role": u.role or "admin",
        "organization": u.organization,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
    }


def _require_admin(current_user: AppUser):
    if (current_user.role or "admin") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )


# ── Admin CRUD ────────────────────────────────────────────────────────────────

@router.get("")
def list_users(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Liste tous les utilisateurs (admin only)."""
    _require_admin(current_user)
    users = db.query(AppUser).order_by(AppUser.created_at).all()
    return [_user_dict(u) for u in users]


@router.get("/me")
def get_me(current_user: AppUser = Depends(get_current_user)):
    """Profil de l'utilisateur connecté."""
    return _user_dict(current_user)


@router.put("/me/password")
def change_my_password(
    body: MyPasswordRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Changer son propre mot de passe."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(400, detail="Mot de passe actuel incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(400, detail="Nouveau mot de passe trop court")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Mot de passe modifié"}


@router.get("/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Détail d'un utilisateur (admin only)."""
    _require_admin(current_user)
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Utilisateur introuvable")
    return _user_dict(user)


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Modifier un utilisateur (admin only)."""
    _require_admin(current_user)
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Utilisateur introuvable")

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.organization is not None:
        user.organization = body.organization
    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)
    return _user_dict(user)


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Supprimer un utilisateur (admin only)."""
    _require_admin(current_user)
    if user_id == current_user.id:
        raise HTTPException(400, detail="Vous ne pouvez pas supprimer votre propre compte")
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Utilisateur introuvable")
    db.delete(user)
    db.commit()
    return {"message": f"Utilisateur '{user.username}' supprimé"}


@router.put("/{user_id}/role")
def change_role(
    user_id: int,
    body: ChangeRoleRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Changer le rôle d'un utilisateur (admin only)."""
    _require_admin(current_user)
    if body.role not in ROLES:
        raise HTTPException(400, detail=f"Rôle invalide. Valeurs : {list(ROLES.keys())}")
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Utilisateur introuvable")
    user.role = body.role
    db.commit()
    return _user_dict(user)


@router.put("/{user_id}/password")
def reset_user_password(
    user_id: int,
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
):
    """Réinitialiser le mot de passe d'un utilisateur (admin only)."""
    _require_admin(current_user)
    if len(body.new_password) < 6:
        raise HTTPException(400, detail="Mot de passe trop court (min 6 caractères)")
    user = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Utilisateur introuvable")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Mot de passe réinitialisé"}


# ── Roles info ────────────────────────────────────────────────────────────────

@router.get("/roles/list")
def list_roles(current_user: AppUser = Depends(get_current_user)):
    """Liste les rôles disponibles et leurs permissions."""
    _require_admin(current_user)
    return rbac.get_available_roles()
