# scraper/storage.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    JSON,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# --------------------------------------------------------------------- #
#  Engine + Base
# --------------------------------------------------------------------- #
DB_PATH = Path("/app/data/horse_bets.sqlite")        # matches volume mount
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

ENGINE = create_engine(f"sqlite:///{DB_PATH}", future=True, echo=False)
SessionLocal = sessionmaker(bind=ENGINE, future=True)

Base = declarative_base()

TZ = ZoneInfo("Europe/Paris")

# --------------------------------------------------------------------- #
#  Models
# --------------------------------------------------------------------- #
class Race(Base):
    __tablename__ = "races"
    id        = Column(Integer, primary_key=True)
    race_id   = Column(String,  nullable=False, unique=True)
    post_time = Column(DateTime(timezone=True), nullable=False)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id         = Column(Integer, primary_key=True)
    race_id    = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True),
                        default=lambda: datetime.now(tz=TZ),
                        nullable=False)
    payload    = Column(JSON, nullable=False)


# --------------------------------------------------------------------- #
#  Helpers called by other modules
# --------------------------------------------------------------------- #
def upsert_race(race_id: str, post_time: datetime) -> None:
    with SessionLocal() as db:
        race = db.query(Race).filter_by(race_id=race_id).one_or_none()
        if race:
            race.post_time = post_time
        else:
            db.add(Race(race_id=race_id, post_time=post_time))
        db.commit()


def store_snapshot(race_id: str, payload: dict) -> None:
    with SessionLocal() as db:
        db.add(Snapshot(race_id=race_id, payload=payload))
        db.commit()


# --------------------------------------------------------------------- #
#  Create tables on first run
# --------------------------------------------------------------------- #
Base.metadata.create_all(ENGINE)
