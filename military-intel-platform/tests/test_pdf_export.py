import unittest
from utils.pdf_export import generate_mission_brief_pdf
from collections import namedtuple

class TestPDFExport(unittest.TestCase):
    def test_generate_mission_brief_pdf(self):
        Rec = namedtuple('Rec', ['priority', 'category', 'action', 'rationale'])
        recs = [
            Rec("HIGH", "MedEvac", "Prepare air support.", "Past incidents caused high casualties.")
        ]
        
        pdf_bytes = generate_mission_brief_pdf(
            country="Iraq",
            lat=33.0,
            lon=44.0,
            radius=100,
            threat_score=85,
            threat_level="CRITICAL",
            incident_count=50,
            dominant_attack="Bombing/Explosion",
            recommendations=recs
        )
        
        # Verify it returns bytes
        self.assertIsInstance(pdf_bytes, bytes)
        # Verify it's actually a PDF by checking header
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))

if __name__ == '__main__':
    unittest.main()
