"""
utils/recommendations.py — Resource Recommendation Engine
==========================================================
Rule-based + severity-aware recommendation engine that suggests
operational responses based on threat scores and attack patterns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Recommendation:
    """A single operational recommendation."""
    category: str
    action: str
    priority: str  # "Routine", "Elevated", "High", "Critical"
    icon: str
    rationale: str


def generate_recommendations(
    threat_score: int,
    dominant_attack_type: str | None = None,
    recent_trend: str | None = None,  # "increasing", "stable", "decreasing"
    live_event_count: int = 0,
) -> list[Recommendation]:
    """Generate operational recommendations based on threat assessment.

    Parameters
    ----------
    threat_score : int
        Composite risk score 0-100.
    dominant_attack_type : str | None
        Most common attack type in the region.
    recent_trend : str | None
        Whether recent activity is increasing, stable, or decreasing.
    live_event_count : int
        Number of live conflict events in the monitoring window.

    Returns
    -------
    list[Recommendation]
    """
    recs: list[Recommendation] = []

    # ── Base recommendations by threat score ──────────────────────────
    if threat_score >= 75:
        recs.extend([
            Recommendation(
                "Force Protection", "Deploy rapid response teams to high-risk zones",
                "Critical", "🔴",
                f"Threat score {threat_score}/100 indicates imminent or active threat conditions."
            ),
            Recommendation(
                "ISR", "Maximize UAV surveillance and satellite monitoring",
                "Critical", "🛰️",
                "Critical threat levels require continuous intelligence, surveillance, and reconnaissance."
            ),
            Recommendation(
                "Border Security", "Establish enhanced border checkpoints and patrols",
                "Critical", "🚧",
                "High cross-border threat activity detected."
            ),
            Recommendation(
                "Command", "Prepare senior leadership briefings and escalation protocols",
                "Critical", "📋",
                "Critical situations require immediate command awareness."
            ),
        ])
    elif threat_score >= 55:
        recs.extend([
            Recommendation(
                "ISR", "Increase UAV surveillance sorties by 50%",
                "High", "🛰️",
                f"Threat score {threat_score}/100 warrants enhanced monitoring."
            ),
            Recommendation(
                "Patrol", "Deploy additional ground patrols in vulnerable sectors",
                "High", "🚔",
                "Elevated threat requires increased presence."
            ),
            Recommendation(
                "Intelligence", "Intensify HUMINT and SIGINT collection",
                "High", "📡",
                "High-threat environments benefit from multi-source intelligence fusion."
            ),
        ])
    elif threat_score >= 30:
        recs.extend([
            Recommendation(
                "Monitoring", "Maintain enhanced monitoring cadence",
                "Elevated", "👁️",
                f"Threat score {threat_score}/100 is above baseline — stay vigilant."
            ),
            Recommendation(
                "Coordination", "Coordinate with local security forces",
                "Elevated", "🤝",
                "Medium-threat regions benefit from joint intelligence sharing."
            ),
        ])
    else:
        recs.append(Recommendation(
            "Baseline", "Continue routine monitoring and periodic assessments",
            "Routine", "✅",
            f"Threat score {threat_score}/100 is within normal parameters."
        ))

    # ── Attack-type-specific recommendations ──────────────────────────
    if dominant_attack_type:
        atk_lower = dominant_attack_type.lower()
        if "bombing" in atk_lower or "explosion" in atk_lower:
            recs.append(Recommendation(
                "EOD", "Pre-position explosive ordnance disposal teams",
                "High" if threat_score >= 55 else "Elevated", "💣",
                f"Dominant attack type '{dominant_attack_type}' suggests IED/bombing risk."
            ))
        elif "armed assault" in atk_lower:
            recs.append(Recommendation(
                "Force Protection", "Reinforce perimeter security and access controls",
                "High" if threat_score >= 55 else "Elevated", "🛡️",
                f"Dominant attack type '{dominant_attack_type}' indicates direct assault risk."
            ))
        elif "assassination" in atk_lower:
            recs.append(Recommendation(
                "VIP Protection", "Enhance protective details for key personnel",
                "High" if threat_score >= 55 else "Elevated", "👤",
                f"Dominant attack type '{dominant_attack_type}' suggests targeted threats."
            ))
        elif "kidnapping" in atk_lower or "hostage" in atk_lower:
            recs.append(Recommendation(
                "Personnel", "Restrict non-essential movement and travel",
                "High" if threat_score >= 55 else "Elevated", "🚫",
                f"Dominant attack type '{dominant_attack_type}' indicates abduction risk."
            ))

    # ── Trend-based recommendations ───────────────────────────────────
    if recent_trend == "increasing":
        recs.append(Recommendation(
            "Analysis", "Investigate root causes of escalating activity",
            "High" if threat_score >= 55 else "Elevated", "📈",
            "Activity trend is increasing — proactive analysis recommended."
        ))
    elif recent_trend == "decreasing" and threat_score < 55:
        recs.append(Recommendation(
            "Assessment", "Consider gradual de-escalation of security posture",
            "Routine", "📉",
            "Activity trend is decreasing with moderate threat level."
        ))

    # ── Live event surge ──────────────────────────────────────────────
    if live_event_count >= 20:
        recs.append(Recommendation(
            "Situational Awareness", "Activate real-time event monitoring cell",
            "Critical" if threat_score >= 75 else "High", "🔄",
            f"{live_event_count} live conflict events detected — surge conditions."
        ))

    return recs


def priority_color(priority: str) -> str:
    """Return a CSS color for a priority level."""
    return {
        "Critical": "#FF2D55",
        "High": "#FF6B35",
        "Elevated": "#FFD60A",
        "Routine": "#34C759",
    }.get(priority, "#94A3B8")
