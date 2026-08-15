"""
utils/tsi.py — Threat Severity Index (TSI)
===========================================
Non-linear composite scoring function for every GTD incident.

Formula
-------
    TSI_raw = w1·ln(1 + nkill) + w2·ln(1 + nwound) + w3·success + w4·claimed

    TSI (0–100) = 100 · (TSI_raw − min) / (max − min)        [min-max normalised]

Weights (tunable, sum to 1.0)
------------------------------
    w1 = 0.50  — fatalities carry highest weight
    w2 = 0.30  — injuries are serious but less terminal
    w3 = 0.15  — a successful attack signals higher operational capacity
    w4 = 0.05  — a claimed attack signals higher ideological intent

Logarithm rationale
-------------------
    log(1 + x) compresses extreme values. A single mass-casualty event
    (e.g. nkill=500) would dominate a linear sum; log keeps the scale
    interpretable across the full distribution while preserving ordinality.

References
----------
    Global Terrorism Database (GTD) codebook columns used:
        nkill, nwound, success (0/1), claimed (0/1)
"""

import json
import os
import numpy as np
import pandas as pd

# ── Weights ────────────────────────────────────────────────────────────────
W_KILL    = 0.50
W_WOUND   = 0.30
W_SUCCESS = 0.15
W_CLAIMED = 0.05

_BOUNDS_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "tsi_bounds.json")

def get_tsi_bounds() -> tuple[float, float]:
    """Return cached (min_raw, max_raw) calibration bounds if available."""
    if os.path.exists(_BOUNDS_PATH):
        try:
            with open(_BOUNDS_PATH, "r") as f:
                data = json.load(f)
                return float(data.get("min", 0.0)), float(data.get("max", 5.0))
        except Exception:
            pass
    return 0.0, 5.0

def compute_tsi(df: pd.DataFrame, use_global_bounds: bool = True) -> pd.Series:
    """
    Compute TSI for each row in *df*.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: nkill, nwound, success, claimed
        (missing values are filled with 0)
    use_global_bounds : bool
        If True, normalises against cached dataset bounds; else uses df min-max.

    Returns
    -------
    pd.Series of float  — TSI score normalised to [0, 100]
    """
    kill_series = df["nkill"] if "nkill" in df.columns else pd.Series(0, index=df.index)
    wound_series = df["nwound"] if "nwound" in df.columns else pd.Series(0, index=df.index)
    success_series = df["success"] if "success" in df.columns else pd.Series(1, index=df.index)
    claimed_series = df["claimed"] if "claimed" in df.columns else pd.Series(0, index=df.index)

    kill    = pd.to_numeric(kill_series,    errors="coerce").fillna(0).clip(lower=0)
    wound   = pd.to_numeric(wound_series,   errors="coerce").fillna(0).clip(lower=0)
    success = pd.to_numeric(success_series, errors="coerce").fillna(0).clip(lower=0, upper=1)
    claimed = pd.to_numeric(claimed_series, errors="coerce").fillna(0).clip(lower=0, upper=1)

    raw = (
        W_KILL    * np.log1p(kill)    +
        W_WOUND   * np.log1p(wound)   +
        W_SUCCESS * success           +
        W_CLAIMED * claimed
    )

    if use_global_bounds:
        mn, mx = get_tsi_bounds()
    else:
        mn, mx = raw.min(), raw.max()

    if mx == mn or mx == 0:
        return pd.Series(np.zeros(len(raw)), index=df.index)
    return (((raw - mn) / (mx - mn)) * 100).clip(lower=0, upper=100).round(2)


def compute_single_tsi(nkill: float, nwound: float, success: float = 1.0, claimed: float = 0.0) -> float:
    """Compute normalized TSI score for a single incident in O(1) time."""
    raw = (
        W_KILL * np.log1p(max(0, float(nkill))) +
        W_WOUND * np.log1p(max(0, float(nwound))) +
        W_SUCCESS * max(0, min(1, float(success))) +
        W_CLAIMED * max(0, min(1, float(claimed)))
    )
    mn, mx = get_tsi_bounds()
    if mx == mn or mx == 0:
        return 0.0
    return round(float(np.clip(((raw - mn) / (mx - mn)) * 100, 0, 100)), 2)


def tsi_label(score: float) -> tuple[str, str]:
    """
    Return (label, colour-hex) for a single TSI score.
    """
    if score >= 75:
        return "CRITICAL", "#FF2D55"
    elif score >= 50:
        return "HIGH",     "#FF6B35"
    elif score >= 25:
        return "MEDIUM",   "#FFD60A"
    else:
        return "LOW",      "#34C759"

