"""
database/intelligence_db.py — Persistent Intelligence Database
===============================================================
Manages a DuckDB on-disk database at data/intelligence.db that stores
normalised live events and exposes a combined view over GTD + live data.

Architecture
------------
- `live_events` table   : normalised rows from GDELT (GTD-compatible schema)
- `event_log` table     : ingestion run history (timestamp, source, count)
- `combined_incidents`  : virtual view = GTD CSV UNION ALL live_events

Key design decisions
--------------------
1. The GTD CSV is NOT copied into the DB — it is read via DuckDB's
   read_csv_auto() at query time so there is no data duplication.
2. Deduplication is enforced through `source_id` (SHA-256 of title+date).
3. All writes use an exclusive connection that is closed immediately to
   avoid WAL lock contention with Streamlit's multi-threaded runner.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from database.schema import normalize_live_row

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH      = PROJECT_ROOT / "data" / "intelligence.db"
GTD_CSV      = PROJECT_ROOT / "data" / "globalterrorism.csv"

# GTD columns used in the combined view (must match the CSV)
GTD_COLS = [
    "iyear", "imonth", "iday", "country_txt", "region_txt", "city",
    "attacktype1_txt", "weaptype1_txt", "targtype1_txt", "gname",
    "latitude", "longitude", "nkill", "nwound", "success", "suicide",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gtd_table_expr() -> str:
    escaped = str(GTD_CSV).replace("'", "''")
    return f"read_csv_auto('{escaped}', header=true, sample_size=-1, all_varchar=false)"


def _connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(database=str(DB_PATH), read_only=read_only)


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS live_events (
            source_id        VARCHAR PRIMARY KEY,
            ingested_at      VARCHAR,
            iyear            INTEGER,
            imonth           INTEGER,
            iday             INTEGER,
            country_txt      VARCHAR,
            region_txt       VARCHAR,
            city             VARCHAR,
            attacktype1_txt  VARCHAR,
            weaptype1_txt    VARCHAR,
            targtype1_txt    VARCHAR,
            gname            VARCHAR,
            latitude         DOUBLE,
            longitude        DOUBLE,
            nkill            INTEGER,
            nwound           INTEGER,
            success          INTEGER,
            suicide          INTEGER,
            source_label     VARCHAR,
            original_title   VARCHAR,
            severity         VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            run_id       VARCHAR,
            run_at       VARCHAR,
            source       VARCHAR,
            rows_added   INTEGER
        )
    """)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Initialise the intelligence database (idempotent)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _ensure_tables(conn)
    logger.info("Intelligence DB initialised at %s", DB_PATH)


def ingest_live_events(
    df: pd.DataFrame,
    source: str = "GDELT",
) -> int:
    """Normalise and insert live events into the database.

    Duplicate rows (same source_id) are silently ignored.

    Parameters
    ----------
    df      : DataFrame from fetch_gdelt_events / enrich_live_events
    source  : Label to store in event_log

    Returns
    -------
    int — number of new rows actually inserted.
    """
    if df.empty:
        return 0

    init_db()

    # Normalise each row to GTD-compatible schema
    rows: list[dict] = []
    for record in df.to_dict(orient="records"):
        try:
            rows.append(normalize_live_row(record))
        except Exception as exc:
            logger.warning("Skipped row during normalisation: %s", exc)

    if not rows:
        return 0

    new_df = pd.DataFrame(rows)

    with _connect() as conn:
        _ensure_tables(conn)

        # Load existing IDs to detect duplicates
        existing_ids: set[str] = set(
            conn.execute("SELECT source_id FROM live_events").fetchdf()["source_id"].tolist()
        )

        fresh = new_df[~new_df["source_id"].isin(existing_ids)]
        fresh = fresh.drop_duplicates(subset=["source_id"])
        count = len(fresh)

        if count > 0:
            conn.register("_incoming", fresh)
            conn.execute("INSERT INTO live_events SELECT * FROM _incoming ON CONFLICT (source_id) DO NOTHING")
            conn.execute(
                "INSERT INTO event_log VALUES (?, ?, ?, ?)",
                [
                    pd.util.hash_pandas_object(fresh).sum().__str__()[:12],
                    datetime.now(tz=timezone.utc).isoformat(),
                    source,
                    count,
                ],
            )

    logger.info("Ingested %d new live events from %s", count, source)
    return count


def get_live_count() -> int:
    """Return total number of live events stored in the DB."""
    try:
        init_db()
        with _connect(read_only=True) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM live_events").fetchone()[0])
    except Exception:
        return 0


def get_live_df() -> pd.DataFrame:
    """Return all live events as a DataFrame."""
    try:
        init_db()
        with _connect(read_only=True) as conn:
            return conn.execute("SELECT * FROM live_events ORDER BY iyear DESC, imonth DESC, iday DESC").fetchdf()
    except Exception:
        return pd.DataFrame()


def get_event_log() -> pd.DataFrame:
    """Return ingestion run history."""
    try:
        init_db()
        with _connect(read_only=True) as conn:
            return conn.execute("SELECT * FROM event_log ORDER BY run_at DESC").fetchdf()
    except Exception:
        return pd.DataFrame()


def query_combined(
    sql: str,
    gtd_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Execute SQL against a combined view: GTD CSV UNION ALL live_events.

    Use ``combined_incidents`` as the table name in your SQL.

    Parameters
    ----------
    sql      : SQL query referencing ``combined_incidents``
    gtd_cols : Override the default GTD column selection if needed.

    Returns
    -------
    pd.DataFrame
    """
    init_db()
    cols = ", ".join(gtd_cols or GTD_COLS)
    gtd_expr = _gtd_table_expr()

    with _connect() as conn:
        _ensure_tables(conn)
        conn.execute(f"""
            CREATE OR REPLACE VIEW combined_incidents AS
                SELECT {cols}, 'GTD' AS data_source
                FROM {gtd_expr}
            UNION ALL
                SELECT {cols}, source_label AS data_source
                FROM live_events
        """)
        return conn.execute(sql).fetchdf()


def load_combined() -> pd.DataFrame:
    """Load the full combined (GTD + live) dataset as a DataFrame."""
    cols = ", ".join(GTD_COLS)
    return query_combined(
        f"SELECT {cols}, data_source FROM combined_incidents",
        gtd_cols=GTD_COLS,
    )


def get_db_stats() -> dict[str, Any]:
    """Return summary statistics about the intelligence database."""
    try:
        init_db()
        live_df = get_live_df()
        gtd_exists = GTD_CSV.exists()

        gtd_count = 0
        if gtd_exists:
            with _connect() as conn:
                gtd_count = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {_gtd_table_expr()}"
                    ).fetchone()[0]
                )

        return {
            "gtd_rows":       gtd_count,
            "live_rows":      len(live_df),
            "total_rows":     gtd_count + len(live_df),
            "live_countries": live_df["country_txt"].nunique() if not live_df.empty else 0,
            "db_size_kb":     round(DB_PATH.stat().st_size / 1024, 1) if DB_PATH.exists() else 0,
            "db_path":        str(DB_PATH),
            "gtd_path":       str(GTD_CSV),
            "last_ingest":    live_df["ingested_at"].max() if not live_df.empty else "Never",
        }
    except Exception as exc:
        logger.error("get_db_stats error: %s", exc)
        return {
            "gtd_rows": 0, "live_rows": 0, "total_rows": 0,
            "live_countries": 0, "db_size_kb": 0,
            "db_path": str(DB_PATH), "gtd_path": str(GTD_CSV),
            "last_ingest": "Error",
        }
