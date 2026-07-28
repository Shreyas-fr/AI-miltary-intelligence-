import sys
from streamlit.testing.v1 import AppTest

def test_map():
    at = AppTest.from_file("pages/2_🌍_Global_Threat_Map.py")
    
    print("Running with default settings (Mobile Fallback OFF)...")
    at.run(timeout=30)
    assert not at.exception, f"App crashed with exceptions: {at.exception}"
    print("Desktop view loaded successfully.")
    
    print("Toggling Mobile Fallback ON...")
    # The toggle is the first toggle on the page (or sidebar)
    at.sidebar.toggle[0].set_value(True)
    at.run(timeout=30)
    assert not at.exception, f"App crashed with exceptions: {at.exception}"
    print("Mobile 2D fallback view loaded successfully.")
    
if __name__ == "__main__":
    test_map()
