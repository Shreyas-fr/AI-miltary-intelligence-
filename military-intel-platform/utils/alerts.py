from typing import Dict, Any, Optional

def generate_threat_score_alert(
    country: str,
    score: int,
    risk_level: str,
    score_threshold: int
) -> Optional[Dict[str, Any]]:
    """Generate an alert if the threat score meets or exceeds the threshold."""
    if score >= score_threshold:
        if score >= 85 or risk_level == "Critical":
            sev = "Critical"
            sev_badge = "badge-critical"
            border_col = "#FF2D55"
        elif score >= 70 or risk_level == "High":
            sev = "High"
            sev_badge = "badge-high"
            border_col = "#FF6B35"
        else:
            sev = "Medium"
            sev_badge = "badge-medium"
            border_col = "#FFD60A"

        return {
            "country": country,
            "alert_type": "Threat Score",
            "title": "Threat Score Threshold Exceeded",
            "severity": sev,
            "badge_class": sev_badge,
            "border_color": border_col,
            "current": f"{score}/100",
            "threshold": f"{score_threshold}/100",
            "detail": f"Composite risk score reached {score}/100 (Level: {risk_level}), meeting or exceeding configured alert threshold of {score_threshold}."
        }
    return None

def generate_activity_surge_alert(
    country: str,
    act_increase_pct: float,
    activity_threshold: float,
    latest_cnt: int,
    prev_cnt: int,
    latest_yr: int | str,
    prev_yr: int | str
) -> Optional[Dict[str, Any]]:
    """Generate an alert if YoY activity increase meets or exceeds the threshold."""
    if act_increase_pct >= activity_threshold:
        if act_increase_pct >= 100:
            sev = "Critical"
            sev_badge = "badge-critical"
            border_col = "#FF2D55"
        elif act_increase_pct >= 60:
            sev = "High"
            sev_badge = "badge-high"
            border_col = "#FF6B35"
        else:
            sev = "Medium"
            sev_badge = "badge-medium"
            border_col = "#FFD60A"

        return {
            "country": country,
            "alert_type": "Activity Surge",
            "title": "YoY Incident Activity Surge",
            "severity": sev,
            "badge_class": sev_badge,
            "border_color": border_col,
            "current": f"+{act_increase_pct:.1f}%",
            "threshold": f"+{activity_threshold}%",
            "detail": f"Year-over-year incident count increased from {prev_cnt} ({prev_yr}) to {latest_cnt} ({latest_yr}), representing a +{act_increase_pct:.1f}% surge."
        }
    return None
