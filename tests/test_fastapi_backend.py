import unittest

from fastapi.testclient import TestClient

from backend.main import app


class FastApiBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_overview(self):
        response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreater(payload["incidents"], 0)
        self.assertIn("countries", payload)

    def test_countries(self):
        response = self.client.get("/api/countries")
        self.assertEqual(response.status_code, 200)
        countries = response.json()
        self.assertTrue(countries)
        self.assertIn("country", countries[0])

    def test_country_analysis(self):
        country = self.client.get("/api/countries").json()[0]["country"]
        response = self.client.get(f"/api/country-analysis/{country}")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["country"], country)
        self.assertGreater(payload["summary"]["incidents"], 0)
        self.assertIn("attack_types", payload)
        self.assertIn("incident_details", payload)
        self.assertIn("incident_locations", payload)

    def test_country_analysis_csv(self):
        country = self.client.get("/api/countries?sort=name").json()[0]["country"]
        response = self.client.get(f"/api/country-analysis/{country}/csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
