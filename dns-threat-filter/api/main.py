"""
main.py — FastAPI microservice for dns-threat-filter.

Milestone 2 feed implementation:
  - Downloads the URLhaus 'text_online' bulk feed on startup.
    Feed format: one URL per line (e.g. http://malicioushost.com/payload).
    The parser extracts the hostname from each URL using urlparse.
  - Loads extracted hostnames into an in-memory set for O(1) lookup.
  - Caches the raw file to api/data/urlhaus_blocklist.txt.
  - Refreshes every hour via an asyncio background task (non-blocking).
  - Tracks feed state: "OK", "STALE:<ISO-timestamp>", or "UNAVAILABLE".
    If a refresh fails, the last-known-good in-memory set stays live.
    Every /check response and SQLite row records the real feed state.

Background refresh mechanism: asyncio.create_task() in the startup lifecycle
event. The refresh loop runs as a native asyncio coroutine, sleeping between
refreshes with asyncio.sleep(). This never blocks the request-handling event
loop — uvicorn serves /check concurrently while a refresh is in progress.
"""

import asyncio
from urllib.parse import urlparse
import logging
from datetime import datetime, timezone
from pathlib import Path
import threading

from dga_classifier import classifier

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from cachetools import TTLCache

from db import init_db, log_event

# ---------------------------------------------------------------------------
# Response cache: TTL = 60 seconds, max 2048 entries
# Thread-safe with a lock since uvicorn uses multiple threads via lifespan
# ---------------------------------------------------------------------------
_response_cache: TTLCache = TTLCache(maxsize=2048, ttl=60)
_cache_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Typosquatting detector — known-safe apex domains to compare against
# ---------------------------------------------------------------------------
_KNOWN_SAFE_DOMAINS = {
    "google.com", "github.com", "pypi.org", "microsoft.com", "apple.com",
    "amazon.com", "cloudflare.com", "fastly.com", "akamai.com", "meta.com",
    "twitter.com", "linkedin.com", "youtube.com", "reddit.com", "wikipedia.org",
    "streamlit.io", "render.com", "openai.com", "huggingface.co", "anaconda.com",
}

def _levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein edit distance between two strings."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev if a[i-1] == b[j-1] else 1 + min(prev, dp[j], dp[j-1])
            prev = temp
    return dp[n]

def _is_typosquat(domain: str) -> str | None:
    """
    Check if a domain is suspiciously close to a known-safe domain.
    Returns the spoofed target domain if detected, else None.
    Threshold: Levenshtein distance ≤ 2 but not an exact match.
    """
    apex = ".".join(domain.split(".")[-2:]) if domain.count(".") >= 1 else domain
    for safe in _KNOWN_SAFE_DOMAINS:
        dist = _levenshtein(apex, safe)
        if 0 < dist <= 2:  # 0 = exact match (legitimate), 1-2 = suspicious
            return safe
    return None

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
URLHAUS_FEED_URL = "https://urlhaus.abuse.ch/downloads/text_online/"
CACHE_PATH = Path(__file__).parent / "data" / "urlhaus_blocklist.txt"
REFRESH_INTERVAL_SECONDS = 3600  # 1 hour

logger = logging.getLogger("dns-threat-filter")
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# Shared mutable feed state — reads are lock-free (GIL protected for set swap)
# ---------------------------------------------------------------------------
_blocklist: set[str] = set()
_urlhaus_status: str = "UNAVAILABLE"   # updated after first successful load


# ---------------------------------------------------------------------------
# Feed loader
# ---------------------------------------------------------------------------
def _parse_feed(raw: str) -> set[str]:
    """
    Parse the URLhaus 'text_online' bulk feed.

    Feed format: one full URL per line, e.g.:
        http://192.168.1.1:4444/malware.exe
        http://evil-domain.com/payload

    We extract the hostname from each URL via urlparse and store it
    in a lowercase set. IP addresses are included as-is (for future
    use); domain names are stored as the full host string.
    Comment lines (starting with #) and blank lines are skipped.
    """
    hosts: set[str] = set()
    for line in raw.splitlines():
        line = line.strip().rstrip("\r")
        if not line or line.startswith("#"):
            continue
        try:
            host = urlparse(line).hostname
            if host:
                hosts.add(host.lower())
        except Exception:
            pass  # malformed line — skip silently
    return hosts


async def _download_and_refresh(*, url: str = URLHAUS_FEED_URL) -> None:
    """
    Download the URLhaus blocklist, update the in-memory set, and cache to disk.
    If the download fails:
      - Keep the existing in-memory blocklist (last-known-good).
      - Set status to "UNAVAILABLE" if we have never had a good copy,
        or "STALE:<last-ok-timestamp>" if we have a cached copy to fall back to.
    """
    global _blocklist, _urlhaus_status

    logger.info("URLhaus feed refresh starting (url=%s)", url)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            raw = resp.text

        new_set = _parse_feed(raw)
        if len(new_set) < 50:
            # Sanity-check: the live URLhaus feed currently resolves to ~1,700 unique
            # hosts extracted from ~15,000 URLs. A tiny set (<50) is almost certainly
            # an error page being parsed, not a real feed — reject it.
            raise ValueError(
                f"Feed too small ({len(new_set)} hosts) — likely a feed error, not replacing."
            )

        # Atomic swap — Python's GIL makes this safe for the simple reads in /check
        _blocklist = new_set
        now_iso = datetime.now(timezone.utc).isoformat()
        _urlhaus_status = "OK"
        logger.info("URLhaus feed refreshed: %d domains (at %s)", len(_blocklist), now_iso)

        # Cache to disk (background write — failures are non-fatal)
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(raw, encoding="utf-8")
        except OSError as e:
            logger.warning("Could not write feed cache: %s", e)

    except Exception as e:
        logger.error("URLhaus feed refresh FAILED: %s", e)

        # Try loading the on-disk cache as a fallback
        if not _blocklist and CACHE_PATH.exists():
            logger.info("Loading blocklist from disk cache: %s", CACHE_PATH)
            cached_raw = CACHE_PATH.read_text(encoding="utf-8")
            _blocklist = _parse_feed(cached_raw)
            mtime = datetime.fromtimestamp(CACHE_PATH.stat().st_mtime, tz=timezone.utc)
            _urlhaus_status = f"STALE:{mtime.isoformat()}"
            logger.info(
                "Loaded %d domains from stale cache (last modified %s)",
                len(_blocklist),
                mtime.isoformat(),
            )
        elif _blocklist:
            # Already had a good in-memory set from a previous successful refresh
            mtime_str = (
                CACHE_PATH.stat().st_mtime
                if CACHE_PATH.exists()
                else "unknown"
            )
            _urlhaus_status = (
                f"STALE:{datetime.fromtimestamp(float(mtime_str), tz=timezone.utc).isoformat()}"
                if isinstance(mtime_str, float)
                else "STALE:unknown"
            )
        else:
            _urlhaus_status = "UNAVAILABLE"


async def _refresh_loop() -> None:
    """Background asyncio task: refresh the feed once, then loop every hour."""
    await _download_and_refresh()      # initial load at startup
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        await _download_and_refresh()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="DNS Threat Filter API", version="0.2.0-milestone2")


@app.on_event("startup")
async def startup() -> None:
    init_db()
    # Fire-and-forget the refresh loop — runs concurrently with request handling
    asyncio.create_task(_refresh_loop())


# ---------------------------------------------------------------------------
# API models
# ---------------------------------------------------------------------------
class CheckRequest(BaseModel):
    domain: str


class CheckResponse(BaseModel):
    domain: str
    verdict: str            # "BLOCKED" | "ALLOW"
    source: str | None      # "urlhaus" | "clean"
    dga_score: float | None
    urlhaus_status: str     # "OK" | "STALE:<iso>" | "UNAVAILABLE"
    blocklist_size: int     # informational — lets the caller see feed size


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/check", response_model=CheckResponse)
async def check_domain(req: CheckRequest) -> CheckResponse:
    domain = req.domain.lower().rstrip(".")

    # --- TTL Cache hit ---
    with _cache_lock:
        if domain in _response_cache:
            return _response_cache[domain]

    # Lookup: check the exact queried hostname first, then the apex domain
    apex = ".".join(domain.split(".")[-2:]) if domain.count(".") >= 1 else domain
    in_blocklist = domain in _blocklist or apex in _blocklist

    dga_score = None
    typosquat_of = None

    if in_blocklist:
        verdict = "BLOCKED"
        source = "urlhaus"
    else:
        # Typosquatting check (before DGA — lower computational cost)
        typosquat_of = _is_typosquat(domain)
        if typosquat_of:
            verdict = "BLOCKED"
            source = "typosquatting"
            dga_score = None
        else:
            # DGA classifier — threshold raised to 0.80
            dga_score = classifier.predict(domain)
            if dga_score >= 0.80:
                verdict = "BLOCKED"
                source = "dga_classifier"
            else:
                verdict = "ALLOW"
                source = "clean"

    resp = CheckResponse(
        domain=domain,
        verdict=verdict,
        source=source,
        dga_score=dga_score,
        urlhaus_status=_urlhaus_status,
        blocklist_size=len(_blocklist),
    )

    # Cache the response
    with _cache_lock:
        _response_cache[domain] = resp

    log_event(
        domain=domain,
        verdict=verdict,
        source=source,
        dga_score=dga_score,
        urlhaus_status=_urlhaus_status,
    )

    return resp


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "milestone": 2,
        "urlhaus_status": _urlhaus_status,
        "blocklist_size": len(_blocklist),
    }


@app.get("/feed/status")
async def feed_status() -> dict:
    """Detailed feed status endpoint for debugging."""
    return {
        "urlhaus_status": _urlhaus_status,
        "blocklist_size": len(_blocklist),
        "cache_exists": CACHE_PATH.exists(),
        "cache_path": str(CACHE_PATH),
        "refresh_interval_seconds": REFRESH_INTERVAL_SECONDS,
    }
