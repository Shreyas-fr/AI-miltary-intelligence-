import pytest
from utils.alerts import generate_threat_score_alert, generate_activity_surge_alert

def test_threat_score_alert_triggering():
    # Should not trigger (score < threshold)
    alert = generate_threat_score_alert("Syria", 70, "High", 75)
    assert alert is None

    # Should trigger exactly at boundary (score == threshold)
    alert = generate_threat_score_alert("Syria", 75, "High", 75)
    assert alert is not None
    assert alert["alert_type"] == "Threat Score"
    assert alert["country"] == "Syria"
    assert alert["severity"] == "High"
    assert alert["badge_class"] == "badge-high"

    # Should trigger above boundary
    alert = generate_threat_score_alert("Iraq", 90, "Critical", 75)
    assert alert is not None
    assert alert["severity"] == "Critical"
    assert alert["badge_class"] == "badge-critical"

def test_threat_score_alert_severity():
    # Test Medium severity (< 70, but >= threshold)
    alert = generate_threat_score_alert("France", 60, "Medium", 50)
    assert alert is not None
    assert alert["severity"] == "Medium"
    assert alert["badge_class"] == "badge-medium"
    assert alert["border_color"] == "#FFD60A"

    # Test High severity (>= 70)
    alert = generate_threat_score_alert("India", 72, "High", 50)
    assert alert is not None
    assert alert["severity"] == "High"
    assert alert["badge_class"] == "badge-high"
    assert alert["border_color"] == "#FF6B35"

    # Test Critical severity (>= 85)
    alert = generate_threat_score_alert("Yemen", 88, "Critical", 50)
    assert alert is not None
    assert alert["severity"] == "Critical"
    assert alert["badge_class"] == "badge-critical"
    assert alert["border_color"] == "#FF2D55"
    
    # Test fallback to risk_level if score doesn't match threshold rules but level does
    # This shouldn't normally happen with consistent data but we test the OR condition
    alert = generate_threat_score_alert("Yemen", 80, "Critical", 50)
    assert alert["severity"] == "Critical"

def test_activity_surge_alert_triggering():
    # Should not trigger
    alert = generate_activity_surge_alert("Syria", 40.0, 50.0, 140, 100, 2023, 2022)
    assert alert is None

    # Should trigger exactly at boundary
    alert = generate_activity_surge_alert("Syria", 50.0, 50.0, 150, 100, 2023, 2022)
    assert alert is not None
    assert alert["alert_type"] == "Activity Surge"
    assert alert["severity"] == "Medium"

def test_activity_surge_alert_severity():
    # Test Medium severity (< 60)
    alert = generate_activity_surge_alert("France", 55.0, 50.0, 155, 100, 2023, 2022)
    assert alert is not None
    assert alert["severity"] == "Medium"
    assert alert["badge_class"] == "badge-medium"

    # Test High severity (>= 60 and < 100)
    alert = generate_activity_surge_alert("India", 75.0, 50.0, 175, 100, 2023, 2022)
    assert alert is not None
    assert alert["severity"] == "High"
    assert alert["badge_class"] == "badge-high"

    # Test Critical severity (>= 100)
    alert = generate_activity_surge_alert("Yemen", 120.0, 50.0, 220, 100, 2023, 2022)
    assert alert is not None
    assert alert["severity"] == "Critical"
    assert alert["badge_class"] == "badge-critical"
