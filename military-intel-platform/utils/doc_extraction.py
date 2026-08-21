import os
import json
import pandas as pd
import requests
from pydantic import BaseModel, Field
from typing import List



class CountryExtraction(BaseModel):
    country_name: str = Field(description="The name of the country being reported on")
    troop_count: str = Field(description="Number of troops or personnel. Must be 'Not found in document' if missing.")
    equipment_types: str = Field(description="Types of equipment mentioned. Must be 'Not found in document' if missing.")
    known_bases: str = Field(description="Known bases or outposts. Must be 'Not found in document' if missing.")
    general_capabilities: str = Field(description="General military capabilities. Must be 'Not found in document' if missing.")
    incident_count: str = Field(description="Number of threat incidents. Must be 'Not found in document' if missing.")
    threat_score_tsi: str = Field(description="TSI or threat score. Must be 'Not found in document' if missing.")
    dominant_attack_types: str = Field(description="Dominant attack types (e.g. bombings, firearms). Must be 'Not found in document' if missing.")
    protected_sites_to_avoid: str = Field(description="Count or list of protected civilian sites (hospitals, schools, NGOs) explicitly flagged for avoidance. Must be 'Not found in document' if missing.")

class DocumentExtraction(BaseModel):
    countries: List[CountryExtraction] = Field(description="A list of extractions for each country mentioned in the document.")

PROMPT_CONSTRAINT = """
CRITICAL DIRECTIVE: You are a strict military intelligence parser. You may ONLY extract explicit facts stated in the provided text. You are strictly forbidden from inferring, estimating, or relying on external knowledge. If the text does not explicitly state a value for a requested field, you MUST populate that field with the exact string: "Not found in document". Do not guess numbers (e.g., troop counts) or invent dominant attack types.
DEFENSIVE FRAMING RULE: When extracting 'protected_sites_to_avoid', you must only list sites (hospitals, schools, NGOs) that are explicitly protected civilian infrastructure to be avoided. Never frame these as targets.
"""

def extract_intelligence_ollama(text: str, source_name: str, model: str = "phi4") -> list[dict]:
    """Extracts intelligence using a local Ollama instance with JSON mode and Pydantic validation."""
    schema = DocumentExtraction.model_json_schema()
    
    system_prompt = (
        f"{PROMPT_CONSTRAINT}\n\n"
        f"You must strictly reply with valid JSON matching this schema:\n{json.dumps(schema)}\n\n"
        "Do not include any explanations, markdown blocks, or text outside the JSON."
    )
    
    current_prompt = f"DOCUMENT TEXT:\n{text}"
    max_retries = 3
    
    for attempt in range(max_retries):
        payload = {
            "model": model,
            "prompt": f"{system_prompt}\n\n{current_prompt}",
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0}
        }
        
        try:
            response = requests.post("http://localhost:11434/api/generate", json=payload, timeout=300)
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Ollama service is not running or unreachable on port 11434.")
        
        response_data = response.json()
        output_text = response_data.get("response", "")
        
        try:
            # 1. Parse JSON syntactically
            parsed = json.loads(output_text)
            
            # 2. Validate semantically via Pydantic
            validated = DocumentExtraction(**parsed)
            
            results = []
            for c in validated.countries:
                c_dict = c.model_dump()
                c_dict["source_document"] = source_name
                results.append(c_dict)
            return results
            
        except (json.JSONDecodeError, ValueError) as e:
            # Re-prompt with the error to fix the output
            current_prompt = (
                f"DOCUMENT TEXT:\n{text}\n\n"
                f"Your previous output failed validation with the following error:\n{str(e)}\n"
                "Please fix the JSON and ensure it matches the schema strictly."
            )
            
    raise RuntimeError("Ollama extraction failed validation after 3 attempts.")

def extract_intelligence_from_text(text: str, source_name: str) -> tuple[list[dict], str]:
    """Extracts intelligence using the local Ollama backend (Phi-4). Returns (results, backend_name)."""
    return extract_intelligence_ollama(text, source_name), "Ollama / Phi-4 (Local)"

def merge_extractions(all_results: list[dict]) -> pd.DataFrame:
    """Merges multiple extractions into a single DataFrame with conflict resolution."""
    if not all_results:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_results)
    
    # We want to group by country_name and merge fields
    merged_data = []
    
    for country, group in df.groupby("country_name"):
        row = {"Country": country}
        
        fields = [
            "troop_count", "equipment_types", "known_bases", "general_capabilities",
            "incident_count", "threat_score_tsi", "dominant_attack_types", "protected_sites_to_avoid"
        ]
        
        for field in fields:
            values = []
            for _, g_row in group.iterrows():
                val = g_row.get(field, "Not found in document")
                source = g_row.get("source_document", "Unknown")
                
                # We only want to append if it's NOT the placeholder
                if val and val != "Not found in document":
                    values.append(f"{val} [{source}]")
                    
            if not values:
                row[field] = "Not found in document"
            else:
                row[field] = " | ".join(values)
                
        merged_data.append(row)
        
    return pd.DataFrame(merged_data)
