"""Quick profile of the enriched Arkhangelsk infrastructure export.

Run with:  pixi run profile
Writes nothing; prints a compact summary to stdout (UTF-8).
"""
from pathlib import Path
import sys
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data" / "raw" / \
    "objects_arkhangelsk_2026-06-28_enriched.csv"


def main() -> None:
    # Console on Windows may be cp1251; force UTF-8 so Cyrillic prints cleanly.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    df = pd.read_csv(DATA, sep=";", encoding="utf-8-sig", low_memory=False)
    print(f"Rows: {len(df):,}   Columns: {df.shape[1]}")
    print(f"Categories: {df['category_orig'].nunique()}   "
          f"Types: {df['type_orig'].nunique()}   "
          f"Districts: {df['district_orig'].nunique()}")
    print(f"Coordinate coverage: {df['latitude'].notna().mean()*100:.1f}%   "
          f"Address coverage: {df['adress_orig'].notna().mean()*100:.1f}%")

    print("\nVerification status:")
    print(df["verification_status"].value_counts(dropna=False).to_string())

    print("\nTop categories:")
    print(df["category_orig"].value_counts().head(10).to_string())

    print("\nObjects per district:")
    print(df["district_orig"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
