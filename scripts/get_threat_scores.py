import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import load_data
from utils.intelligence import compute_country_risk

def main():
    historical = load_data()
    countries = ["Iraq", "Afghanistan", "Pakistan"]
    
    for c in countries:
        risk = compute_country_risk(c, historical)
        print(f"\n--- {c} ---")
        print(f"Total Score: {risk.score}/100")
        for k, v in risk.components.items():
            print(f"  {k}: {v:.1f}")

if __name__ == "__main__":
    main()
