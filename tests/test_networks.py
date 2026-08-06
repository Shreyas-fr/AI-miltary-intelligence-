import sys
from streamlit.testing.v1 import AppTest

def test_networks():
    at = AppTest.from_file("pages/25_🕸️_Group_Networks.py")
    
    print("Running Group Networks page...")
    at.run(timeout=30)
    assert not at.exception, f"App crashed with exceptions: {at.exception}"
    print("Group Networks page loaded successfully.")
    
if __name__ == "__main__":
    test_networks()
