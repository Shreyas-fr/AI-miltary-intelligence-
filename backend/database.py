"""DuckDB-backed data access for the FastAPI service."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "globalterrorism.csv"
TABLE_TOKEN = "'data/globalterrorism.csv'"


def dataset_sql() -> str:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DB_PATH}")
    escaped = str(DB_PATH).replace("'", "''")
    return f"read_csv_auto('{escaped}', header=true, sample_size=-1, all_varchar=false)"


def query_data(sql_query: str) -> pd.DataFrame:
    if TABLE_TOKEN not in sql_query:
        raise ValueError(f"Query must reference {TABLE_TOKEN}.")
    resolved = sql_query.replace(TABLE_TOKEN, dataset_sql())
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(resolved).fetch_df()


def load_data(columns: list[str] | None = None) -> pd.DataFrame:
    selected = "*" if columns is None else ", ".join(columns)
    return query_data(f"SELECT {selected} FROM {TABLE_TOKEN}")
