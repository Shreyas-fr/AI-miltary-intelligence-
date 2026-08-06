import unittest
import pandas as pd
from utils.similarity import SimilarityEngine


class SimilarityEngineTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame([
            {
                "iyear": 2020,
                "country_txt": "Iraq",
                "region_txt": "Middle East & North Africa",
                "attacktype1_txt": "Bombing/Explosion",
                "weaptype1_txt": "Explosives",
                "targtype1_txt": "Private Citizens & Property",
                "gname": "Unknown Group",
                "nkill": 5,
                "nwound": 10,
                "success": 1,
                "city": "Baghdad",
            },
            {
                "iyear": 2021,
                "country_txt": "Afghanistan",
                "region_txt": "South Asia",
                "attacktype1_txt": "Armed Assault",
                "weaptype1_txt": "Firearms",
                "targtype1_txt": "Military",
                "gname": "Taliban",
                "nkill": 12,
                "nwound": 25,
                "success": 1,
                "city": "Kabul",
            },
            {
                "iyear": 2019,
                "country_txt": "Iraq",
                "region_txt": "Middle East & North Africa",
                "attacktype1_txt": "Bombing/Explosion",
                "weaptype1_txt": "Explosives",
                "targtype1_txt": "Police",
                "gname": "Islamic State",
                "nkill": 3,
                "nwound": 7,
                "success": 1,
                "city": "Mosul",
            },
        ])
        
        self.data = pd.concat([self.data, self.data], ignore_index=True)
        self.engine = SimilarityEngine(self.data)

    def test_find_similar(self):
        query = {
            "country_txt": "Iraq",
            "region_txt": "Middle East & North Africa",
            "attacktype1_txt": "Bombing/Explosion",
            "weaptype1_txt": "Explosives",
            "targtype1_txt": "Private Citizens & Property",
            "gname": "Unknown Group",
            "nkill": 5,
            "nwound": 10,
            "success": 1,
        }
        results = self.engine.find_similar(query, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertIn("similarity_score", results.columns)
        self.assertIn("similarity_pct", results.columns)
        # Top result should be the exact matching row from Iraq
        self.assertEqual(results.iloc[0]["country_txt"], "Iraq")
        self.assertGreater(results.iloc[0]["similarity_pct"], 90.0)


if __name__ == "__main__":
    unittest.main()
