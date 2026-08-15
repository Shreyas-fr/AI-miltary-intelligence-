import os
import json
from utils.doc_extraction import extract_intelligence_from_text

with open("scratch/incomplete_report.txt", "r") as f:
    text = f.read()

res = extract_intelligence_from_text(text, "incomplete_report.txt")
print(json.dumps(res, indent=2))
