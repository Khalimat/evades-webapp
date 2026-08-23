import os
from contextlib import contextmanager
from datetime import datetime

from sqlmodel import Field, Session, SQLModel, create_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://evades:evades@db:5432/evades"
)

engine = create_engine(DATABASE_URL, echo=False)


class JobRecord(SQLModel, table=True):
    """Lightweight bookkeeping row per job — the real result payload
    lives in Redis (via RQ) while it's fresh; this table is mainly for
    an admin view / history / audit trail over time."""

    id: str = Field(primary_key=True)
    job_type: str
    input_filename: str
    status: str = "queued"
    created_at: datetime = Field(default_factory=datetime.utcnow)


def init_db():
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
