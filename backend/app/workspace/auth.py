"""Server-owned accounts, Argon2 passwords, opaque sessions, and CSRF checks."""

import hashlib
import os
import secrets
import time
from contextvars import ContextVar
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .db import Attempt, LoginSession, Organization, User, audit, database

router = APIRouter(prefix="/api/auth", tags=["organization-auth"])
COOKIE = "baylab_session"
LIFETIME = 8 * 60 * 60
hasher = PasswordHasher()
DUMMY = hasher.hash(secrets.token_urlsafe(24))
current_org: ContextVar[str] = ContextVar("current_org", default="lkpi")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Login(StrictModel):
    organization: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,39}$")
    email: str = Field(min_length=3, max_length=180, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)


class CreateUser(Login):
    name: str = Field(min_length=2, max_length=120)
    role: Literal["admin", "formulator", "viewer"] = "formulator"
    password: str = Field(min_length=12, max_length=128)


class ChangePassword(StrictModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify(encoded: str, password: str) -> bool:
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def public_user(user: User, organization: Organization) -> dict:
    return {
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "organization": {"slug": organization.id, "name": organization.name},
    }


def identity(request: Request) -> tuple[dict, str]:
    token = request.cookies.get(COOKIE, "")
    if not 20 <= len(token) <= 128:
        raise HTTPException(401, "Silakan masuk dengan akun organisasi.")
    with database() as db:
        session = db.get(LoginSession, digest(token))
        if not session or session.expires <= time.time():
            raise HTTPException(401, "Sesi habis. Silakan masuk kembali.")
        user = db.get(User, session.user_id)
        if not user or not user.active:
            raise HTTPException(401, "Akun tidak aktif.")
        org = db.get(Organization, user.org_id)
        return {**public_user(user, org), "id": user.id, "org_id": user.org_id}, session.csrf


def require_editor(request: Request) -> dict:
    user = request.state.user
    if user["role"] not in {"admin", "formulator"}:
        raise HTTPException(403, "Akses ini memerlukan peran formulator atau admin.")
    return user


def require_admin(request: Request) -> dict:
    user = request.state.user
    if user["role"] != "admin":
        raise HTTPException(403, "Hanya admin organisasi yang dapat mengelola akun.")
    return user


def permitted_origin(request: Request) -> bool:
    allowed = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }
    allowed.update(filter(None, os.getenv("BAYLAB_ALLOWED_ORIGINS", "").split(",")))
    origin = request.headers.get("origin")
    return not origin or origin in allowed


@router.post("/login")
def login(payload: Login, request: Request, response: Response) -> dict:
    if not permitted_origin(request):
        raise HTTPException(403, "Origin tidak diizinkan.")
    ip = request.client.host if request.client else "unknown"
    buckets = ["ip:" + ip, "account:" + digest(payload.organization + payload.email.lower())]
    now = time.time()
    with database() as db:
        db.execute(delete(Attempt).where(Attempt.created < now - 900))
        for bucket, limit in zip(buckets, [30, 10], strict=True):
            count = db.scalar(
                select(func.count()).select_from(Attempt).where(Attempt.bucket == bucket)
            )
            if count >= limit:
                raise HTTPException(429, "Terlalu banyak percobaan masuk. Tunggu 15 menit.")
        for bucket in buckets:
            db.add(Attempt(bucket=bucket))
    with database() as db:
        user = db.scalar(
            select(User).where(
                User.org_id == payload.organization, User.email == payload.email.lower()
            )
        )
        valid = verify(user.password_hash if user else DUMMY, payload.password)
        if not valid or not user or not user.active:
            raise HTTPException(401, "Organisasi, email, atau kata sandi tidak sesuai.")
        old = request.cookies.get(COOKIE)
        if old:
            db.execute(delete(LoginSession).where(LoginSession.token_hash == digest(old)))
        db.execute(delete(LoginSession).where(LoginSession.expires < now))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.add(
            LoginSession(
                token_hash=digest(token), user_id=user.id, csrf=csrf, expires=now + LIFETIME
            )
        )
        audit(db, user.org_id, user.id, "login")
        profile = public_user(user, db.get(Organization, user.org_id))
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=os.getenv("BAYLAB_SECURE_COOKIES") == "true",
        samesite="strict",
        max_age=LIFETIME,
        path="/",
    )
    return {"user": profile, "csrf_token": csrf}


@router.get("/session")
def session(request: Request) -> dict:
    user = request.state.user
    return {
        "user": {k: v for k, v in user.items() if k not in {"id", "org_id"}},
        "csrf_token": request.state.csrf,
    }


@router.post("/logout")
def logout(request: Request, response: Response) -> dict:
    with database() as db:
        db.execute(
            delete(LoginSession).where(
                LoginSession.token_hash == digest(request.cookies.get(COOKIE, ""))
            )
        )
        audit(db, request.state.user["org_id"], request.state.user["id"], "logout")
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=os.getenv("BAYLAB_SECURE_COOKIES") == "true",
    )
    return {"ok": True}


@router.get("/users")
def users(request: Request) -> list[dict]:
    actor = require_admin(request)
    with database() as db:
        org = db.get(Organization, actor["org_id"])
        return [public_user(u, org) for u in db.scalars(select(User).where(User.org_id == org.id))]


@router.post("/users", status_code=201)
def create_user(payload: CreateUser, request: Request) -> dict:
    actor = require_admin(request)
    if payload.organization != actor["org_id"]:
        raise HTTPException(403, "Akun hanya dapat dibuat dalam organisasi sendiri.")
    try:
        with database() as db:
            user = User(
                org_id=actor["org_id"],
                email=payload.email.lower(),
                name=payload.name,
                role=payload.role,
                password_hash=hasher.hash(payload.password),
            )
            db.add(user)
            db.flush()
            audit(db, user.org_id, actor["id"], "create_user", user.id)
            return public_user(user, db.get(Organization, user.org_id))
    except IntegrityError as exc:
        raise HTTPException(409, "Email sudah memiliki akun dalam organisasi ini.") from exc


@router.post("/password")
def change_password(payload: ChangePassword, request: Request, response: Response) -> dict:
    actor = request.state.user
    with database() as db:
        user = db.get(User, actor["id"])
        if not verify(user.password_hash, payload.old_password):
            raise HTTPException(400, "Kata sandi lama tidak sesuai.")
        user.password_hash = hasher.hash(payload.new_password)
        db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
        audit(db, user.org_id, user.id, "change_password")
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True, "message": "Kata sandi diganti. Masuk kembali."}
