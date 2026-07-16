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

import numpy as np
import pandas as pd

# ── Weights ────────────────────────────────────────────────────────────────
W_KILL    = 0.50
W_WOUND   = 0.30
W_SUCCESS = 0.15
W_CLAIMED = 0.05


def compute_tsi(df: pd.DataFrame) -> pd.Series:
    """
    Compute TSI for each row in *df*.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: nkill, nwound, success, claimed
        (missing values are filled with 0)

    Returns
    -------
    pd.Series of float  — TSI score normalised to [0, 100]
    """
    kill    = pd.to_numeric(df.get("nkill",    0), errors="coerce").fillna(0).clip(lower=0)
    wound   = pd.to_numeric(df.get("nwound",   0), errors="coerce").fillna(0).clip(lower=0)
    success = pd.to_numeric(df.get("success",  0), errors="coerce").fillna(0).clip(lower=0, upper=1)
    claimed = pd.to_numeric(df.get("claimed",  0), errors="coerce").fillna(0).clip(lower=0, upper=1)

    raw = (
        W_KILL    * np.log1p(kill)    +
        W_WOUND   * np.log1p(wound)   +
        W_SUCCESS * success           +
        W_CLAIMED * claimed
    )

    mn, mx = raw.min(), raw.max()
    if mx == mn:
        return pd.Series(np.zeros(len(raw)), index=df.index)
    return ((raw - mn) / (mx - mn) * 100).round(2)


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
