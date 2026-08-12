import os
import sys
from streamlit.testing.v1 import AppTest

def test_pages():
    page_files = [
        "pages/17_📋_Resource_Recommendation.py"
    ]
    
    results = {}
    
    for page_file in page_files:
        try:
            at = AppTest.from_file(page_file)
            at.session_state["authentication_status"] = True
            at.session_state["user_role"] = "Commander"
            
            # Inject authentication state to bypass auth gate and render the full page
            at.session_state["authentication_status"] = True
            at.session_state["user_role"] = "Commander" 
            
            # Increase timeout to 10s for heavy pages like the map
            at.run(timeout=30)
            
            if at.exception:
                err = at.exception[0]
                results[page_file] = f"FAIL - {err.type}: {err.message}"
            else:
                results[page_file] = "PASS"
        except Exception as e:
            results[page_file] = f"FAIL (Crash) - {type(e).__name__}: {str(e)}"
            
    print("--- 30s Test Results ---")
    for page, result in results.items():
        print(f"{page}: {result}")

if __name__ == "__main__":
    test_pages()
