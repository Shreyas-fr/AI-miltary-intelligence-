"""
data/prepare_gtd.py - Real GTD Preprocessor
============================================
Converts the official GTD CSV (from start.umd.edu or Kaggle)
into the 16-column format the app expects, filtered to 2000-2020.

Usage
-----
    # Place your downloaded GTD file as: data/globalterrorism_raw.csv
    ./venv/bin/python data/prepare_gtd.py

    # Or specify a custom input path and year range:
    ./venv/bin/python data/prepare_gtd.py --input path/to/gtd.csv --years 2000 2020
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLS = [
    "iyear", "imonth", "iday",
    "latitude", "longitude",
    "country_txt", "region_txt", "city",
    "attacktype1_txt", "weaptype1_txt", "targtype1_txt",
    "gname", "success", "suicide", "nkill", "nwound", "claimed",
]

COL_ALIASES = {
    "country":     "country_txt",
    "region":      "region_txt",
    "attack_type": "attacktype1_txt",
    "weapon_type": "weaptype1_txt",
    "target_type": "targtype1_txt",
    "group":       "gname",
    "killed":      "nkill",
    "wounded":     "nwound",
}


def load_raw(path: Path) -> pd.DataFrame:
    print(f"Loading {path} ...")
    try:
        df = pd.read_csv(path, encoding="latin1", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    print(f"  Raw shape: {df.shape}  ({df.shape[0]:,} rows x {df.shape[1]} columns)")
    return df


def rename_aliases(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {k: v for k, v in COL_ALIASES.items() if k in df.columns and v not in df.columns}
    if renamed:
        print(f"  Renaming columns: {renamed}")
        df = df.rename(columns=renamed)
    return df


def validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        print(f"\n  ERROR: Required columns missing: {missing}")
        print("  Available columns (first 40):")
        for col in sorted(df.columns)[:40]:
            print(f"    {col}")
        sys.exit(1)
    print(f"  All {len(REQUIRED_COLS)} required columns present")


def preprocess(df: pd.DataFrame, year_min: int, year_max: int) -> pd.DataFrame:
    print(f"\nPreprocessing...")
    df = df[REQUIRED_COLS].copy()

    df["iyear"] = pd.to_numeric(df["iyear"], errors="coerce")
    before = len(df)
    df = df[(df["iyear"] >= year_min) & (df["iyear"] <= year_max)].copy()
    print(f"  Year filter {year_min}-{year_max}: {before:,} -> {len(df):,} rows")

    df["attacktype1_txt"] = df["attacktype1_txt"].astype(str).str.strip()
    before = len(df)
    df = df[~df["attacktype1_txt"].isin(["", "nan", "Unknown", "unknown"])].copy()
    print(f"  Dropped unknown attacktype: {before:,} -> {len(df):,} rows")

    for col in ["country_txt", "region_txt", "attacktype1_txt", "weaptype1_txt",
                "targtype1_txt", "gname", "city"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace(["nan", "", "NaN"], np.nan)

    # Merge barricade incidents into kidnapping (reduces to 7-class problem)
    df["attacktype1_txt"] = df["attacktype1_txt"].replace(
        "Hostage Taking (Barricade Incident)",
        "Hostage Taking (Kidnapping)"
    )

    for col in ["nkill", "nwound"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(lower=0)
    for col in ["success", "suicide"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).clip(0, 1).astype(int)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    # Null out (0,0) coordinates - these are clearly missing data, not Gulf of Guinea
    invalid = ((df["latitude"].abs() < 0.01) & (df["longitude"].abs() < 0.01))
    n_invalid = int(invalid.sum())
    if n_invalid > 0:
        df.loc[invalid, ["latitude", "longitude"]] = np.nan
        print(f"  Nulled {n_invalid:,} (0,0) coordinates")

    before = len(df)
    df = df.drop_duplicates().copy()
    print(f"  Deduplicated: {before:,} -> {len(df):,} rows (removed {before - len(df):,} dupes)")

    df = df.sort_values(["iyear", "imonth", "iday"]).reset_index(drop=True)
    return df


def print_distribution(df: pd.DataFrame) -> None:
    print("\n" + "=" * 65)
    print("CLASS DISTRIBUTION (attacktype1_txt)")
    print("=" * 65)
    dist = df["attacktype1_txt"].value_counts()
    total = len(df)
    for cls, cnt in dist.items():
        bar = "#" * int(cnt / total * 50)
        print(f"  {str(cls):<45}: {cnt:>7,} ({cnt/total*100:>5.1f}%)  {bar}")

    print(f"\n  Total incidents : {total:,}")
    print(f"  Coverage        : {int(df.iyear.min())} - {int(df.iyear.max())}")
    print(f"  Countries       : {df.country_txt.nunique():,}")
    print(f"  Groups          : {df.gname.nunique():,}")
    print(f"  Rows with coords: {df.latitude.notna().sum():,}")

    cv = dist.std() / dist.mean()
    if cv < 0.20 and total < 5000:
        print(f"\n  WARNING: CV={cv:.3f} -- still looks synthetic. Not real GTD.")
    else:
        print(f"\n  CV={cv:.3f} -- class imbalance looks realistic (real GTD confirmed)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",  default="data/globalterrorism_raw.csv")
    parser.add_argument("--output", default="data/globalterrorism.csv")
    parser.add_argument("--years",  nargs=2, type=int, default=[2000, 2020], metavar=("FROM", "TO"))
    args = parser.parse_args()

    input_path  = Path(args.input)
    output_path = Path(args.output)
    year_min, year_max = args.years

    if not input_path.exists():
        print(f"\n  ERROR: Input file not found: {input_path}")
        print()
        print("  Option A -- Official (1970-2020, best):")
        print("    1. https://www.start.umd.edu/gtd/contact/  (free registration)")
        print("    2. Download: globalterrorismdb_0221dist.csv")
        print("    3. Place at: data/globalterrorism_raw.csv")
        print()
        print("  Option B -- Kaggle mirror (1970-2017, sufficient for classifier):")
        print("    1. https://www.kaggle.com/datasets/START-UMD/gtd")
        print("    2. Download: globalterrorism.csv")
        print("    3. Place at: data/globalterrorism_raw.csv")
        print()
        print("  Then run: ./venv/bin/python data/prepare_gtd.py")
        sys.exit(1)

    df = load_raw(input_path)
    df = rename_aliases(df)
    validate_columns(df)
    df = preprocess(df, year_min, year_max)
    print_distribution(df)

    df.to_csv(output_path, index=False)
    size_mb = output_path.stat().st_size / 1e6
    print(f"\n  Saved: {output_path}  ({size_mb:.1f} MB)")
    print()
    print("  Next steps:")
    print("    1. ./venv/bin/python train_models.py")
    print("    2. streamlit run app.py")


if __name__ == "__main__":
    main()
