"""
app.py — DNS Threat Filter dashboard.

Auto-scans open Chrome tabs every 30 seconds via a background daemon thread.
Reads dns_events.db (written by FastAPI service) and renders a live event table.
"""
import sqlite3
import time
import threading
import subprocess
import urllib.parse
import json
import urllib.request
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

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
CHROME_SCAN_INTERVAL = 30  # seconds

# ---------------------------------------------------------------------------
# Shared state for background Chrome scanner (module-level, daemon thread)
# ---------------------------------------------------------------------------
_scan_lock = threading.Lock()
_scan_results: dict = {
    "last_scan": None,
    "total_domains": 0,
    "blocked": [],    # list of {"domain": ..., "source": ..., "dga_score": ...}
    "allowed": [],
    "error": None,
}

def _do_chrome_scan() -> None:
    """Runs in background thread every CHROME_SCAN_INTERVAL seconds."""
    applescript = """
    tell application "Google Chrome"
        set urlList to ""
        repeat with w in windows
            repeat with t in tabs of w
                set urlList to urlList & URL of t & "\\n"
            end repeat
        end repeat
        return urlList
    end tell
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")

        urls = [u.strip() for u in result.stdout.split("\\n") if u.strip()]
        domains: set[str] = set()
        for url in urls:
            parsed = urllib.parse.urlparse(url)
            if parsed.hostname and not parsed.hostname.startswith("chrome"):
                domains.add(parsed.hostname.lower())

        blocked, allowed = [], []
        for domain in domains:
            try:
                req = urllib.request.Request(
                    "http://localhost:8000/check",
                    data=json.dumps({"domain": domain}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=3) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    if res.get("verdict") == "BLOCKED":
                        blocked.append({
                            "domain": domain,
                            "source": res.get("source"),
                            "dga_score": res.get("dga_score"),
                        })
                    else:
                        allowed.append(domain)
            except Exception:
                pass  # API unreachable — skip quietly

        with _scan_lock:
            _scan_results.update({
                "last_scan": datetime.now().strftime("%H:%M:%S"),
                "total_domains": len(domains),
                "blocked": blocked,
                "allowed": allowed,
                "error": None,
            })
    except Exception as e:
        with _scan_lock:
            _scan_results["error"] = str(e)
            _scan_results["last_scan"] = datetime.now().strftime("%H:%M:%S")


def _start_scanner_daemon() -> None:
    """Launch the background Chrome scanner loop as a daemon thread."""
    def loop():
        while True:
            _do_chrome_scan()
            time.sleep(CHROME_SCAN_INTERVAL)

    t = threading.Thread(target=loop, daemon=True, name="chrome-tab-scanner")
    t.start()


# Only start once per process
if "scanner_started" not in st.session_state:
    _start_scanner_daemon()
    st.session_state["scanner_started"] = True


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def load_events() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame(columns=["id", "ts", "domain", "verdict", "source", "dga_score", "urlhaus_status"])
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql_query("SELECT * FROM dns_events ORDER BY id DESC LIMIT 500", conn)
    conn.close()
    return df


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("## 🛡️ DNS Threat Filter — Live Events")
st.caption("Auto-scanning Chrome tabs every 30s • Live URLhaus feed • DGA classifier v2 (bigram + consonant features)")

# ---------------------------------------------------------------------------
# Browser Safety Panel (auto-scan results)
# ---------------------------------------------------------------------------
with _scan_lock:
    scan = dict(_scan_results)

if scan["error"]:
    st.warning(f"🔍 **Tab Scanner:** Chrome not reachable — `{scan['error']}`")
elif scan["last_scan"] is None:
    st.info("🔍 **Tab Scanner:** First scan in progress...")
else:
    if scan["blocked"]:
        for b in scan["blocked"]:
            score_str = f" | DGA: {b['dga_score']:.0%}" if b.get("dga_score") else ""
            st.error(f"🚨 **DANGEROUS TAB DETECTED:** `{b['domain']}` — Source: `{b['source']}`{score_str}")
    else:
        st.success(
            f"✅ **Browser Safety:** {scan['total_domains']} tab domain(s) scanned at {scan['last_scan']} — all safe"
        )

st.divider()

df = load_events()

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------
total      = len(df)
blocked    = int((df["verdict"] == "BLOCKED").sum()) if total else 0
allowed    = int((df["verdict"] == "ALLOW").sum()) if total else 0
feed_status = df["urlhaus_status"].iloc[0] if total else "UNKNOWN"

c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("Total Queries", str(total), icon="📡")
with c2: kpi_card("Blocked", str(blocked), icon="🚫")
with c3: kpi_card("Allowed", str(allowed), icon="✅")
with c4:
    kpi_card("Feed Status", "", icon="📋")
    urlhaus_feed_badge(feed_status)

st.divider()

# ---------------------------------------------------------------------------
# Event table
# ---------------------------------------------------------------------------
st.markdown("### Recent DNS Events")

if df.empty:
    st.info("No events yet — start the API service and CoreDNS, then run a dig query.")
else:
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
        if val >= 0.80:
            return "color: #f87171; font-weight: 600"
        elif val >= 0.5:
            return "color: #facc15"
        return "color: #4ade80"

    # Fixed: use .map() instead of deprecated .applymap()
    styled = df[["ts", "domain", "verdict", "source", "dga_score", "urlhaus_status"]].style \
        .map(colour_verdict, subset=["verdict"]) \
        .map(colour_dga, subset=["dga_score"]) \
        .format({"dga_score": format_dga})

    st.dataframe(styled, use_container_width=True, height=400)

# ---------------------------------------------------------------------------
# Auto-refresh
# ---------------------------------------------------------------------------
st.caption(f"Auto-refreshing every {REFRESH_SEC}s")
time.sleep(REFRESH_SEC)
st.rerun()
