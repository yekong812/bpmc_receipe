import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

STORAGE = Path(
    os.getenv("STORAGE_DIR", str(Path(__file__).resolve().parents[2] / "storage"))
).resolve()
STORAGE.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    os.getenv("DATABASE_URL", f'sqlite:///{STORAGE / "expense.db"}'),
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def foreign_keys(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def session():
    with SessionLocal() as db:
        yield db
