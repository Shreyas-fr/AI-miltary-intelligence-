import unittest.mock as mock
from streamlit.testing.v1 import AppTest

def test_ai_fallback():
    print("Testing AI Intelligence page fallback behavior...")
    
    # We will mock the fetch_gdelt_events function inside utils.intelligence
    with mock.patch("utils.intelligence.fetch_gdelt_events") as mock_fetch:
        # Simulate a network failure / timeout
        mock_fetch.side_effect = Exception("Simulated GDELT network timeout or 500 Error")
        
        at = AppTest.from_file("pages/8_🧠_AI_Intelligence.py")
        at.session_state["authentication_status"] = True
        at.session_state["user_role"] = "Commander"
        try:
            at.run(timeout=30)
            
            if at.exception:
                err = at.exception[0]
                print(f"FAIL (Crashed) - {err.type}: {err.message}")
                return
                
            print("PASS (Did not crash). Checking UI for fallback warning...")
            
            # Check if the warning message appears in the UI
            warnings = [w.value for w in at.warning]
            found_warning = False
            for w in warnings:
                if "Live feed unavailable" in w:
                    print(f"SUCCESS: Found fallback warning -> '{w}'")
                    found_warning = True
                    break
            
            if not found_warning:
                print("FAIL: The page loaded, but the expected fallback warning was not found.")
                print("Warnings found:", warnings)
                
        except Exception as e:
            print(f"FAIL (Exception during test execution) - {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test_ai_fallback()
