from utils.doc_extraction import extract_intelligence_from_text
import json

with open("test_intel_report_docA.txt", "r") as f:
    text = f.read()

try:
    results, backend = extract_intelligence_from_text(text, "test_intel_report_docA.txt", backend="Ollama")
    print(f"Backend Used: {backend}")
    print(json.dumps(results, indent=2))
except Exception as e:
    print(f"Error during extraction: {e}")
