"""
audit_log.py — Append-only JSON-lines audit logger for Commander actions.

Creates a non-repudiation trail for sensitive operations without storing
the actual payload contents or cryptographic keys.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Audit log lives alongside the credentials file, outside the web-served assets
_AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent / "audit.jsonl"


def log_commander_action(
    username: str,
    action: str,
    metadata: dict | None = None,
) -> None:
    """
    Write a structured audit entry.

    Args:
        username:  The authenticated username performing the action.
        action:    A short uppercase string identifying the action
                   (e.g. "COMMANDER_ENCRYPT", "COMMANDER_VIEW").
        metadata:  Optional dict of non-sensitive contextual details
                   (e.g. intel_type, payload_size). Never include raw
                   payloads, keys, or PII.
    """
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "username": username,
        "action": action,
        "pid": os.getpid(),
        **(metadata or {}),
    }
    try:
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        # Audit log write failure must never crash the application,
        # but should be loudly logged to the server console.
        logger.error("AUDIT LOG WRITE FAILURE (action=%s, user=%s): %s", action, username, e)


def get_recent_entries(n: int = 50) -> list[dict]:
    """Return the last N audit log entries in reverse-chronological order."""
    if not _AUDIT_LOG_PATH.exists():
        return []
    try:
        with open(_AUDIT_LOG_PATH, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        entries = [json.loads(line) for line in lines]
        return list(reversed(entries[-n:]))
    except Exception as e:
        logger.error("Failed to read audit log: %s", e)
        return []
