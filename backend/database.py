"""Database models and helpers for user, plan, and usage tracking."""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


# ---------------------------------------------------------------------------
# Engine & session configuration
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path(__file__).parent / "outputs" / "alcient.db"
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

connect_args: Dict[str, Any] = {}
if DATABASE_URL.startswith("sqlite"):
    # Needed so SQLite plays nicely with threads in Flask dev server.
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def generate_uuid() -> str:
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------


class Plan(Base):
    __tablename__ = "plans"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    monthly_price_cents = Column(Integer, nullable=False)
    tokens_included = Column(Integer, nullable=False)
    seconds_included = Column(Integer, nullable=False)
    overage_tokens_per_minute = Column(Integer, nullable=False, default=3)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="plan", cascade="all, delete")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=True)
    plan_id = Column(String, ForeignKey("plans.id"), nullable=True)
    tokens_balance = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    plan = relationship("Plan", back_populates="users")
    usage_entries = relationship("UsageEntry", back_populates="user", cascade="all, delete")
    ledger_entries = relationship("TokenLedgerEntry", back_populates="user", cascade="all, delete")


class UsageEntry(Base):
    __tablename__ = "usage_entries"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action_type = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    tokens_input = Column(Integer, default=0, nullable=False)
    tokens_output = Column(Integer, default=0, nullable=False)
    tokens_total = Column(Integer, default=0, nullable=False)
    duration_seconds = Column(Float, default=0.0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="usage_entries")


class TokenLedgerEntry(Base):
    __tablename__ = "token_ledger"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    delta = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    reference = Column(String, nullable=True)
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="ledger_entries")


DEFAULT_PLANS = [
    {
        "id": "starter",
        "name": "Starter",
        "monthly_price_cents": 500,
        "tokens_included": 100,
        "seconds_included": 600,
        "overage_tokens_per_minute": 3,
    },
    {
        "id": "builder",
        "name": "Builder",
        "monthly_price_cents": 1500,
        "tokens_included": 400,
        "seconds_included": 2400,
        "overage_tokens_per_minute": 3,
    },
    {
        "id": "creator",
        "name": "Creator",
        "monthly_price_cents": 4000,
        "tokens_included": 1400,
        "seconds_included": 8400,
        "overage_tokens_per_minute": 3,
    },
    {
        "id": "pro",
        "name": "Pro",
        "monthly_price_cents": 10000,
        "tokens_included": 4000,
        "seconds_included": 24000,
        "overage_tokens_per_minute": 3,
    },
]


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create tables and seed default plan data."""

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        ensure_default_plans(session)


def ensure_default_plans(session) -> None:
    existing = {plan.id for plan in session.query(Plan).all()}
    created = False
    for definition in DEFAULT_PLANS:
        if definition["id"] in existing:
            continue
        session.add(Plan(**definition))
        created = True
    if created:
        session.commit()


def get_session():
    return SessionLocal()


def get_or_create_user(
    session,
    *,
    email: str,
    display_name: Optional[str] = None,
    default_plan_id: Optional[str] = "starter",
) -> User:
    user = session.query(User).filter_by(email=email).one_or_none()
    if user:
        return user
    new_user = User(id=generate_uuid(), email=email, display_name=display_name)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    if default_plan_id:
        plan = session.query(Plan).filter_by(id=default_plan_id).one_or_none()
        if plan:
            new_user.plan = plan
            session.commit()
            session.refresh(new_user)
            allocate_plan_tokens(session, user=new_user, plan=plan)
            session.refresh(new_user)
    return new_user


def adjust_tokens(
    session,
    *,
    user: User,
    delta: int,
    reason: str,
    reference: Optional[str] = None,
) -> TokenLedgerEntry:
    user.tokens_balance += delta
    entry = TokenLedgerEntry(
        user_id=user.id,
        delta=delta,
        reason=reason,
        reference=reference,
        balance_after=user.tokens_balance,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def log_usage(
    session,
    *,
    user: User,
    action_type: str,
    provider: str,
    model: str,
    tokens_input: int = 0,
    tokens_output: int = 0,
    duration_seconds: float = 0.0,
    cost_usd: float = 0.0,
    payload: Optional[Dict[str, Any]] = None,
) -> UsageEntry:
    tokens_total = (tokens_input or 0) + (tokens_output or 0)
    entry = UsageEntry(
        user_id=user.id,
        action_type=action_type,
        provider=provider,
        model=model,
        tokens_input=tokens_input or 0,
        tokens_output=tokens_output or 0,
        tokens_total=tokens_total,
        duration_seconds=duration_seconds or 0.0,
        cost_usd=cost_usd or 0.0,
        payload=payload or {},
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def allocate_plan_tokens(session, *, user: User, plan: Plan) -> TokenLedgerEntry:
    delta = plan.tokens_included
    return adjust_tokens(session, user=user, delta=delta, reason=f"plan:{plan.id}")


def reset_user_tokens(session, *, user: User) -> None:
    user.tokens_balance = 0
    session.query(TokenLedgerEntry).filter(TokenLedgerEntry.user_id == user.id).delete()
    session.commit()
