import pytest
import json
import requests
from unittest.mock import patch, MagicMock
from utils.doc_extraction import extract_intelligence_ollama

def test_extract_intelligence_ollama_valid_json():
    """Test that valid JSON from Ollama parses correctly on the first try."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": json.dumps({
            "countries": [
                {
                    "country_name": "Test Country",
                    "troop_count": "5000",
                    "equipment_types": "Tanks",
                    "known_bases": "Base Alpha",
                    "general_capabilities": "High",
                    "incident_count": "10",
                    "threat_score_tsi": "85",
                    "dominant_attack_types": "Bombings",
                    "protected_sites_to_avoid": "Hospital 1"
                }
            ]
        })
    }
    mock_response.raise_for_status.return_value = None

    with patch('requests.post', return_value=mock_response) as mock_post:
        results = extract_intelligence_ollama("Some text here", "report.txt")
        
        # Post was called exactly once
        assert mock_post.call_count == 1
        
        # Results parsed correctly
        assert len(results) == 1
        assert results[0]["country_name"] == "Test Country"
        assert results[0]["source_document"] == "report.txt"

def test_extract_intelligence_ollama_retry_success():
    """Test that malformed JSON triggers a retry, and succeeds if the second attempt is valid."""
    # First response: Invalid JSON structure (missing a required field, e.g., troop_count)
    bad_response = MagicMock()
    bad_response.json.return_value = {
        "response": json.dumps({
            "countries": [
                {
                    "country_name": "Test Country"
                    # missing all other fields!
                }
            ]
        })
    }
    
    # Second response: Valid JSON
    good_response = MagicMock()
    good_response.json.return_value = {
        "response": json.dumps({
            "countries": [
                {
                    "country_name": "Test Country",
                    "troop_count": "Not found in document",
                    "equipment_types": "Not found in document",
                    "known_bases": "Not found in document",
                    "general_capabilities": "Not found in document",
                    "incident_count": "Not found in document",
                    "threat_score_tsi": "Not found in document",
                    "dominant_attack_types": "Not found in document",
                    "protected_sites_to_avoid": "Not found in document"
                }
            ]
        })
    }

    with patch('requests.post', side_effect=[bad_response, good_response]) as mock_post:
        results = extract_intelligence_ollama("Some text here", "report.txt")
        
        # Post was called twice (initial + 1 retry)
        assert mock_post.call_count == 2
        
        # The second call's payload should contain the validation error from the first attempt
        second_call_kwargs = mock_post.call_args_list[1][1]
        payload = second_call_kwargs['json']
        assert "failed validation with the following error" in payload['prompt']
        assert "troop_count" in payload['prompt']
        
        assert len(results) == 1
        assert results[0]["troop_count"] == "Not found in document"

def test_extract_intelligence_ollama_retry_failure():
    """Test that consecutive failures exhaust the retries and raise an error."""
    # Response is completely broken JSON
    bad_response = MagicMock()
    bad_response.json.return_value = {
        "response": "This is not JSON at all!"
    }

    with patch('requests.post', return_value=bad_response) as mock_post:
        with pytest.raises(RuntimeError, match="Ollama extraction failed validation after 3 attempts."):
            extract_intelligence_ollama("Some text here", "report.txt")
            
        # Post should have been called 3 times
        assert mock_post.call_count == 3
