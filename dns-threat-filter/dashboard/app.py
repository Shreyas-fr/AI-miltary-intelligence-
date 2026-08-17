"""
app.py — DNS Threat Filter dashboard (Milestone 2).

Reads dns_events.db (written by FastAPI service) and renders a live event table.
Refresh every 5 seconds via st.rerun().
"""
import sqlite3
import time
from pathlib import Path

import pandas as pd
import streamlit as st

# Add dashboard root to sys.path so utils/ resolves
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils.ui_components import inject_global_css, kpi_card, urlhaus_feed_badge

st.set_page_config(
    page_title="DNS Threat Filter",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_global_css()

DB_PATH = Path(__file__).parent.parent / "data" / "dns_events.db"
REFRESH_SEC = 5


def load_events() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame(columns=["id", "ts", "domain", "verdict", "source", "dga_score", "urlhaus_status"])
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query(
        "SELECT * FROM dns_events ORDER BY id DESC LIMIT 500",
        conn,
    )
    conn.close()
    return df


# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("## 🛡️ DNS Threat Filter — Live Events")
st.caption("Milestone 2 — Live URLhaus feed • Real-time DGA classifier scoring")

df = load_events()

# ── KPI row ─────────────────────────────────────────────────────────────────
total     = len(df)
blocked   = int((df["verdict"] == "BLOCKED").sum()) if total else 0
allowed   = int((df["verdict"] == "ALLOW").sum())   if total else 0
feed_status = df["urlhaus_status"].iloc[0] if total else "UNKNOWN"

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Total Queries",  str(total),   icon="📡")
with c2: kpi_card("Blocked",        str(blocked),  icon="🚫")
with c3: kpi_card("Allowed",        str(allowed),  icon="✅")
with c4:
    kpi_card("Feed Status", "", icon="📋")
    urlhaus_feed_badge(feed_status)

st.divider()

# ── Event table ─────────────────────────────────────────────────────────────
st.markdown("### Recent DNS Events")

if df.empty:
    st.info("No events yet — start the API service and CoreDNS, then run a dig query.")
else:
    # Colour-code the verdict column
    def colour_verdict(val: str) -> str:
        if val == "BLOCKED":
            return "color: #f87171; font-weight: 600"
        elif val == "ALLOW":
            return "color: #4ade80"
        return "color: #facc15"

    def format_dga(val):
        if pd.isna(val) or val is None:
            return ""
        return f"{val:.1%}"
        
    def colour_dga(val):
        if pd.isna(val) or val is None:
            return ""
        if val >= 0.75:
            return "color: #f87171; font-weight: 600"
        elif val >= 0.5:
            return "color: #facc15"
        return "color: #4ade80"

    styled = df[["ts", "domain", "verdict", "source", "dga_score", "urlhaus_status"]].style\
        .applymap(colour_verdict, subset=["verdict"])\
        .applymap(colour_dga, subset=["dga_score"])\
        .format({"dga_score": format_dga})
        
    st.dataframe(styled, use_container_width=True, height=400)

# ── Auto-refresh ─────────────────────────────────────────────────────────────
st.caption(f"Auto-refreshing every {REFRESH_SEC}s")
time.sleep(REFRESH_SEC)
st.rerun()
