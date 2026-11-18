"""A SQLite backup before applying a pending schema migration to existing data."""

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from sqlalchemy import inspect, text
from alembic.script import ScriptDirectory
from .db import engine, STORAGE


def backup_before_upgrade(config):
    if (
        engine.dialect.name != "sqlite"
        or not engine.url.database
        or engine.url.database == ":memory:"
    ):
        return
    path = Path(engine.url.database).resolve()
    with engine.connect() as db:
        if "alembic_version" not in inspect(db).get_table_names():
            return
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar()
    head = ScriptDirectory.from_config(config).get_current_head()
    if not revision or revision == head:
        return
    destination = (
        STORAGE
        / "backups"
        / f'{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}_before_{revision}_to_{head}.sqlite3'
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
