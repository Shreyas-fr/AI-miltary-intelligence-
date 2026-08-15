from collections import namedtuple
from utils.pdf_export import generate_mission_brief_pdf

Rec = namedtuple('Rec', ['priority', 'category', 'action', 'rationale'])
recs = [
    Rec("HIGH", "MedEvac", "Prepare air support.", "Past incidents caused high casualties."),
    Rec("MEDIUM", "Convoy Route", "Avoid central highways.", "High density of IEDs on main roads.")
]

pdf_bytes = generate_mission_brief_pdf(
    country="Iraq",
    lat=33.3152,
    lon=44.3661,
    radius=100,
    threat_score=85,
    threat_level="CRITICAL",
    incident_count=142,
    dominant_attack="Bombing/Explosion",
    recommendations=recs
)

with open("sample_mission_brief.pdf", "wb") as f:
    f.write(pdf_bytes)
print("Saved sample_mission_brief.pdf")
