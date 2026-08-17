"""
db.py — SQLite writer for dns-threat-filter API.
The FastAPI service owns all writes; the dashboard is read-only.
"""
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

# Resolve path relative to this file's location so it works regardless of cwd
_DB_PATH = Path(__file__).parent.parent / "data" / "dns_events.db"
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they do not exist. Called once at startup."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        conn = _get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dns_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT    NOT NULL,
                domain      TEXT    NOT NULL,
                verdict     TEXT    NOT NULL,
                source      TEXT,
                dga_score   REAL,
                urlhaus_status TEXT NOT NULL DEFAULT 'OK'
            )
        """)
        conn.commit()
        conn.close()


def log_event(
    domain: str,
    verdict: str,
    source: str | None,
    dga_score: float | None,
    urlhaus_status: str,
) -> None:
    """Append one DNS event. Thread-safe."""
    ts = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO dns_events (ts, domain, verdict, source, dga_score, urlhaus_status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (ts, domain, verdict, source, dga_score, urlhaus_status),
        )
        conn.commit()
        conn.close()
