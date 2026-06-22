"""Password hashing (bcrypt) + JWT tokens + auth guards.
No endpoint returns data without a valid token -> no data extraction without authorization.
"""
import os
import datetime as dt
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .db import get_db
from . import models

SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
ALGO = "HS256"
TOKEN_HOURS = 12

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Every action a non-admin can be granted. Admin always has all of them.
PERMISSIONS = [
    "creators.view", "creators.edit",
    "executions.view", "executions.edit",
    "brands.view",
    "reports.view",
    "finance.view", "finance.edit",
    "sheets.manage",
    "instagram.sync",
    "users.manage",
]


def perms_of(user) -> set:
    if user.role == "admin":
        return set(PERMISSIONS)
    return {p for p in (user.permissions or "").split(",") if p}


def user_dict(user) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role,
            "approved": user.approved, "permissions": sorted(perms_of(user))}


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def make_token(user: "models.User") -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "exp": dt.datetime.utcnow() + dt.timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> "models.User":
    cred_err = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    try:
        data = jwt.decode(token, SECRET, algorithms=[ALGO])
        uid = int(data["sub"])
    except Exception:
        raise cred_err
    user = db.query(models.User).filter(models.User.id == uid).first()
    if not user or not user.approved:
        raise cred_err
    return user


def admin_only(user: "models.User" = Depends(current_user)) -> "models.User":
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def require_perm(perm: str):
    """Use as a route dependency: only users granted `perm` (or admins) pass."""
    def dep(user: "models.User" = Depends(current_user)) -> "models.User":
        if user.role == "admin" or perm in perms_of(user):
            return user
        raise HTTPException(status_code=403, detail=f"You don't have permission: {perm}")
    return dep
