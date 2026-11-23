import os
import sqlite3
from typing import Optional, Any, List, Union
from flask import g, current_app


def get_db_path() -> str:
    """Return the absolute or relative path to the SQLite database file."""
    if current_app:
        return current_app.config.get("DATABASE_PATH", "polling.db")
    return os.getenv("DATABASE_PATH", "polling.db")


def get_db() -> sqlite3.Connection:
    """
    Open a database connection if none exists for the current application context.
    Configures row factory to sqlite3.Row and enables foreign key enforcement.
    """
    if "db" not in g:
        db_path = get_db_path()
        g.db = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(e: Optional[BaseException] = None) -> None:
    """Close the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(db_path: Optional[str] = None) -> None:
    """
    Execute the schema.sql script to initialize or update tables.
    Works both within Flask app context and standalone (e.g. from seed.py).
    """
    schema_file = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
