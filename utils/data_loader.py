"""Efficient GTD data access helpers backed by DuckDB."""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "globalterrorism.csv"
TABLE_TOKEN = "'data/globalterrorism.csv'"


def _dataset_sql() -> str:
    """Return a DuckDB table expression for the configured CSV."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {DB_PATH}. Add the GTD CSV at data/globalterrorism.csv."
        )
    escaped = str(DB_PATH).replace("'", "''")
    return f"read_csv_auto('{escaped}', header=true, sample_size=-1, all_varchar=false)"


@st.cache_data(show_spinner=False)
def query_data(sql_query: str) -> pd.DataFrame:
    """Run SQL directly against the GTD CSV without first loading it into pandas.

    Queries should refer to ``'data/globalterrorism.csv'`` as the table. The
    token is replaced with DuckDB's ``read_csv_auto`` table function.
    """
    if TABLE_TOKEN not in sql_query:
        raise ValueError(f"Query must reference {TABLE_TOKEN}.")
    resolved_query = sql_query.replace(TABLE_TOKEN, _dataset_sql())
    with duckdb.connect(database=":memory:") as connection:
        return connection.execute(resolved_query).fetch_df()


@st.cache_data(show_spinner="Loading GTD dataset...")
def load_data() -> pd.DataFrame:
    """Load the complete dataset only for legacy pages that require it."""
    return query_data(f"SELECT * FROM {TABLE_TOKEN}")
