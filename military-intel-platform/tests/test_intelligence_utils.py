import unittest

import pandas as pd

from utils.intelligence import (
    build_situation_report,
    classify_event,
    classify_severity,
    compute_country_risk,
    enrich_live_events_with_country_centroids,
    risk_level,
)


class IntelligenceUtilsTests(unittest.TestCase):
    def test_event_and_severity_classification(self):
        self.assertEqual(classify_event("Border clash follows overnight shelling"), "Border Clash")
        self.assertEqual(classify_event("Missile launch reported near capital"), "Missile / Rocket")
        self.assertEqual(classify_severity("Explosion killed several people"), "High")
        self.assertEqual(classify_severity("Security alert reported by local source"), "Low")

    def test_country_centroid_enrichment_uses_title_match(self):
        live = pd.DataFrame(
            [
                {
                    "country": "Unknown",
                    "title": "Explosion reported in Exampleland",
                    "event": "Explosion / Bombing",
                    "severity": "High",
                }
            ]
        )
        historical = pd.DataFrame(
            {
                "country_txt": ["Exampleland", "Exampleland"],
                "latitude": [10.0, 12.0],
                "longitude": [20.0, 22.0],
            }
        )

        enriched = enrich_live_events_with_country_centroids(live, historical)

        self.assertEqual(enriched.loc[0, "country"], "Exampleland")
        self.assertEqual(enriched.loc[0, "latitude"], 11.0)
        self.assertEqual(enriched.loc[0, "longitude"], 21.0)

    def test_risk_score_has_expected_level_and_components(self):
        historical = pd.DataFrame(
            {
                "country_txt": ["A"] * 20 + ["B"] * 80,
                "nkill": [4] * 20 + [0] * 80,
                "latitude": [10.0] * 100,
                "longitude": [20.0] * 100,
            }
        )
        live = pd.DataFrame({"country": ["A", "A"], "severity": ["High", "Medium"]})

        risk = compute_country_risk("A", historical, live)

        self.assertGreater(risk.score, 0)
        self.assertIn(risk.level, {"Low", "Medium", "High", "Critical"})
        self.assertEqual(
            set(risk.components),
            {"Historical Activity", "Recent Events", "Fatalities", "Cluster Density", "Political Instability"},
        )

    def test_situation_report_contains_country_and_score(self):
        risk = compute_country_risk(
            "A",
            pd.DataFrame({"country_txt": ["A"], "nkill": [0], "latitude": [1.0], "longitude": [2.0]}),
            pd.DataFrame({"country": ["A"], "severity": ["Low"]}),
        )
        report = build_situation_report(
            "A",
            "Live window: 1d",
            {"historical_incidents": 1, "historical_fatalities": 0, "top_area": "North"},
            risk,
            pd.DataFrame({"event": ["Security Event"]}),
        )

        self.assertIn("Country: A", report)
        self.assertIn(f"({risk.score}/100)", report)

    def test_risk_level_thresholds(self):
        self.assertEqual(risk_level(10), "Low")
        self.assertEqual(risk_level(30), "Medium")
        self.assertEqual(risk_level(55), "High")
        self.assertEqual(risk_level(75), "Critical")


if __name__ == "__main__":
    unittest.main()
