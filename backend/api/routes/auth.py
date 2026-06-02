from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import AppUser
from core.auth.password import verify_password, hash_password
from core.auth.jwt_handler import create_access_token
from core.auth.dependencies import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(AppUser).filter(AppUser.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants incorrects")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé")

    user.last_login = datetime.now(timezone.utc)
    db.commit()

    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "username": user.username,
        "display_name": user.display_name or user.username,
    }


@router.get("/me")
def me(current_user: AppUser = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "display_name": current_user.display_name or current_user.username,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    }


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe actuel incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mot de passe trop court (min 6 caractères)")

    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Mot de passe modifié"}
