"""Organization-scoped SQLAlchemy storage, schema version 1."""

import os
import time
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


def new_id() -> str:
    return uuid.uuid4().hex


def data_dir() -> Path:
    return Path(os.getenv("BAYLAB_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data")))


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(180))
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf: Mapped[str] = mapped_column(String(80))
    expires: Mapped[float] = mapped_column(Float)


class Attempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket: Mapped[str] = mapped_column(String(255), index=True)
    created: Mapped[float] = mapped_column(Float, default=time.time)


class Record(Base):
    __tablename__ = "workspace_records"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created: Mapped[float] = mapped_column(Float, default=time.time)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    record_id: Mapped[str] = mapped_column(String(80), default="")
    created: Mapped[float] = mapped_column(Float, default=time.time)


@lru_cache
def engine():
    path = Path(os.getenv("BAYLAB_DB", str(data_dir() / "workspace.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    result = create_engine(
        "sqlite:///" + str(path), connect_args={"check_same_thread": False, "timeout": 20}
    )

    @event.listens_for(result, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(result)
    return result


@contextmanager
def database():
    with Session(engine(), expire_on_commit=False) as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


def audit(db: Session, org: str, actor: str, action: str, record: str = "") -> None:
    db.add(Audit(org_id=org, actor=actor, action=action, record_id=record))
