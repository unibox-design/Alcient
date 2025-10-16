"""Database models and helpers for user, plan, and usage tracking."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from sqlalchemy.orm import declarative_base, relationship, selectinload, sessionmaker


# ---------------------------------------------------------------------------
# Engine & session configuration
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path(__file__).parent / "outputs" / "alcient.db"
DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

BACKUP_DIR = Path(__file__).parent / "outputs" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

LEGACY_PROJECT_DIR = Path(__file__).parent / "outputs" / "projects"

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
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")


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


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    prompt = Column(String, nullable=True)
    format = Column(String, nullable=False, default="landscape")
    voice_model = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    runtime_seconds = Column(Float, nullable=True)
    narration = Column(String, nullable=True)
    keywords = Column(JSON, default=list)
    project_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="projects")
    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan", order_by="Scene.order")


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    order = Column(Integer, nullable=False, default=0)
    text = Column(String, nullable=True)
    script = Column(String, nullable=True)
    duration = Column(Float, nullable=True)
    audio_duration = Column(Float, nullable=True)
    keywords = Column(JSON, default=list)
    media = Column(JSON, default=dict)
    tts_voice = Column(String, nullable=True)
    captions = Column(JSON, default=list)
    extra_metadata = Column("metadata", JSON, default=dict)

    project = relationship("Project", back_populates="scenes")


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


def init_db(default_user_email: Optional[str] = None) -> None:
    """Create tables, seed default data, run migrations, and ensure backups."""

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        ensure_default_plans(session)
        migrate_legacy_projects(session, default_user_email=default_user_email)
    maybe_backup_database()


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


def list_plans(session) -> List[Plan]:
    return session.query(Plan).order_by(Plan.monthly_price_cents.asc()).all()


def get_session():
    return SessionLocal()


def _normalise_scene_payload(scene: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "id": scene.get("id") or generate_uuid(),
        "order": int(scene.get("order") if isinstance(scene.get("order"), (int, float)) else index),
        "text": scene.get("visual") or scene.get("text"),
        "script": scene.get("script") or scene.get("text"),
        "duration": scene.get("duration"),
        "audio_duration": scene.get("audioDuration"),
        "keywords": scene.get("keywords") or [],
        "media": scene.get("media") or {},
        "tts_voice": scene.get("ttsVoice"),
        "captions": scene.get("captions") or [],
        "metadata": scene.get("metadata") or {},
    }


def save_project(
    session,
    *,
    user: User,
    project_payload: Dict[str, Any],
) -> Project:
    project_id = str(project_payload.get("id") or generate_uuid())
    project = (
        session.query(Project)
        .filter(Project.id == project_id, Project.user_id == user.id)
        .one_or_none()
    )

    if project is None:
        project = Project(id=project_id, user_id=user.id, title=project_payload.get("title") or "Untitled Project")
        session.add(project)

    project.title = project_payload.get("title") or project.title or "Untitled Project"
    project.prompt = project_payload.get("prompt")
    project.format = project_payload.get("format") or project.format or "landscape"
    project.voice_model = project_payload.get("voiceModel")
    project.duration_seconds = project_payload.get("durationSeconds")
    project.runtime_seconds = project_payload.get("runtimeSeconds")
    project.narration = project_payload.get("narration")
    project.keywords = project_payload.get("keywords") or []
    metadata_payload = project_payload.get("metadata")
    metadata = dict(metadata_payload) if isinstance(metadata_payload, dict) else {}
    if project_payload.get("captionsEnabled") is not None:
        if not isinstance(metadata.get("flags"), dict):
            metadata["flags"] = {}
        metadata["flags"]["captionsEnabled"] = bool(project_payload.get("captionsEnabled"))
    if project_payload.get("captionTemplate"):
        if not isinstance(metadata.get("captions"), dict):
            metadata["captions"] = {}
        metadata["captions"]["template"] = project_payload.get("captionTemplate")
    project.project_metadata = metadata

    scenes_payload = project_payload.get("scenes") if isinstance(project_payload.get("scenes"), list) else []

    existing_scene_ids = {scene.id: scene for scene in project.scenes}
    retained: List[Scene] = []
    for index, scene_payload in enumerate(scenes_payload):
        if not isinstance(scene_payload, dict):
            continue
        normalized = _normalise_scene_payload(scene_payload, index)
        scene_id = normalized["id"]
        scene = existing_scene_ids.pop(scene_id, None)
        if scene is None:
            scene = Scene(id=scene_id, project=project)
        scene.order = normalized["order"]
        scene.text = normalized["text"]
        scene.script = normalized["script"]
        scene.duration = normalized["duration"]
        scene.audio_duration = normalized["audio_duration"]
        scene.keywords = normalized["keywords"]
        scene.media = normalized["media"]
        scene.tts_voice = normalized["tts_voice"]
        scene.captions = normalized["captions"]
        scene.extra_metadata = normalized["metadata"]
        retained.append(scene)

    for stale in existing_scene_ids.values():
        session.delete(stale)

    project.scenes = sorted(retained, key=lambda item: item.order or 0)
    session.commit()
    session.refresh(project)
    return project


def get_project(session, *, user: User, project_id: str) -> Optional[Project]:
    return (
        session.query(Project)
        .options(selectinload(Project.scenes))
        .filter(Project.id == project_id, Project.user_id == user.id)
        .one_or_none()
    )


def serialize_project(project: Project) -> Dict[str, Any]:
    return {
        "id": project.id,
        "title": project.title,
        "prompt": project.prompt,
        "format": project.format,
        "voiceModel": project.voice_model,
        "durationSeconds": project.duration_seconds,
        "runtimeSeconds": project.runtime_seconds,
        "narration": project.narration,
        "keywords": project.keywords or [],
        "metadata": project.project_metadata or {},
        "scenes": [
            {
                "id": scene.id,
                "order": scene.order,
                "text": scene.text,
                "script": scene.script,
                "duration": scene.duration,
                "audioDuration": scene.audio_duration,
                "keywords": scene.keywords or [],
                "media": scene.media or {},
                "ttsVoice": scene.tts_voice,
                "captions": scene.captions or [],
                "metadata": scene.extra_metadata or {},
            }
            for scene in project.scenes
        ],
        "createdAt": project.created_at.isoformat() if project.created_at else None,
        "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
    }


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


def list_usage_entries(session, *, user: User, limit: int = 50) -> List[UsageEntry]:
    return (
        session.query(UsageEntry)
        .filter(UsageEntry.user_id == user.id)
        .order_by(UsageEntry.created_at.desc())
        .limit(limit)
        .all()
    )


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


def list_legacy_project_files() -> List[Path]:
    if not LEGACY_PROJECT_DIR.exists():
        return []
    return sorted(
        [path for path in LEGACY_PROJECT_DIR.glob("*.json") if path.is_file()],
        key=lambda item: item.stat().st_mtime,
    )


def migrate_legacy_projects(session, *, default_user_email: Optional[str] = None) -> int:
    files = list_legacy_project_files()
    if not files:
        return 0

    migrated_dir = LEGACY_PROJECT_DIR / "_migrated"
    migrated_dir.mkdir(parents=True, exist_ok=True)

    if default_user_email:
        user = get_or_create_user(session, email=default_user_email)
    else:
        user = session.query(User).order_by(User.created_at.asc()).first()
        if user is None:
            user = get_or_create_user(session, email="legacy@alcient.local")

    migrated_count = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            backup_path = migrated_dir / f"invalid_{path.name}"
            shutil.move(str(path), str(backup_path))
            continue

        project_payload = payload.get("project") if isinstance(payload, dict) else payload
        if not isinstance(project_payload, dict):
            backup_path = migrated_dir / f"invalid_{path.name}"
            shutil.move(str(path), str(backup_path))
            continue

        save_project(session, user=user, project_payload=project_payload)
        shutil.move(str(path), str(migrated_dir / path.name))
        migrated_count += 1

    return migrated_count


def _list_backups() -> List[Path]:
    return sorted(
        [path for path in BACKUP_DIR.glob("alcient_*.db") if path.is_file()],
        key=lambda item: item.stat().st_mtime,
    )


def backup_database(suffix: Optional[str] = None) -> Optional[Path]:
    if not DEFAULT_DB_PATH.exists():
        return None
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    suffix_part = f"_{suffix}" if suffix else ""
    dest = BACKUP_DIR / f"alcient_{timestamp}{suffix_part}.db"
    shutil.copy2(DEFAULT_DB_PATH, dest)
    return dest


def maybe_backup_database(max_keep: int = 10, min_age_hours: float = 6.0) -> Optional[Path]:
    if not DEFAULT_DB_PATH.exists():
        return None
    backups = _list_backups()
    if backups:
        latest = backups[-1]
        age_seconds = datetime.utcnow().timestamp() - latest.stat().st_mtime
        if age_seconds < (min_age_hours * 3600):
            return None

    new_backup = backup_database()
    backups = _list_backups()
    if len(backups) > max_keep:
        for old in backups[: len(backups) - max_keep]:
            try:
                old.unlink()
            except OSError:
                pass
    return new_backup
