"""
SQLite persistence layer (SQLAlchemy 2.0 style).

• `upsert_race(url, post_time)`   – add or update a race row, returns race_id
• `store_snapshot(url, payload)`  – JSON blob when we scrape 3 min pre‑off
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Integer, JSON, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ---------- database bootstrap ------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ENGINE = create_engine(f"sqlite:///{DATA_DIR/'horse_bets.sqlite'}", future=True)
SessionLocal = sessionmaker(bind=ENGINE, expire_on_commit=False)

Base = declarative_base()


class Race(Base):
    __tablename__ = "races"
    id = Column(Integer, primary_key=True)
    race_id = Column(String, unique=True, nullable=False)   # <— now named race_id
    post_time = Column(DateTime(timezone=True), nullable=False)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True)
    race_id = Column(Integer, nullable=False)
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    payload = Column(JSON, nullable=False)


Base.metadata.create_all(ENGINE)  # run migrations later with Alembic

# ---------- CRUD helpers ------------------------------------------------------


def _get_session() -> Session:
    return SessionLocal()


def upsert_race(url: str, post_time: datetime) -> int:
    with _get_session() as db:
        race = db.query(Race).filter_by(url=url).one_or_none()
        if race:
            race.post_time = post_time
        else:
            race = Race(url=url, post_time=post_time)
            db.add(race)
        db.commit()
        return race.id


def store_snapshot(url: str, payload: dict[str, Any]) -> None:
    with _get_session() as db:
        race = db.query(Race).filter_by(url=url).one_or_none()
        if race is None:
            raise RuntimeError(f"Race {url} not in DB – did collect_today() run?")
        snap = Snapshot(race_id=race.id, payload=payload)
        db.add(snap)
        db.commit()
