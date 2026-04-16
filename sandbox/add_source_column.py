import pandas as pd
import re
from pathlib import Path


# ==========================================================
# CONFIGURATION
# ==========================================================
CSV_PATH = Path("ISA metadata/metadata.csv")


# ==========================================================
# LOAD DATA
# ==========================================================
def load_metadata(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)
    
    if "Instances" not in df.columns:
        raise ValueError("Column 'Instances' not found in metadata.")
    
    return df


# ==========================================================
# SOURCE EXTRACTION LOGIC
# ==========================================================
def extract_source(instance_name: str) -> str:
    match = re.match(r"([a-zA-Z]+)", str(instance_name))
    return match.group(1) if match else "unknown"


# ==========================================================
# ADD SOURCE COLUMN (SECOND POSITION)
# ==========================================================
def add_source_column(df: pd.DataFrame) -> pd.DataFrame:
    source_series = df["Instances"].apply(extract_source)

    # If Source already exists, remove it first to avoid duplication
    if "Source" in df.columns:
        df = df.drop(columns=["Source"])

    # Insert as second column (index 1)
    df.insert(1, "Source", source_series)

    return df


# ==========================================================
# SAVE DATA
# ==========================================================
def save_metadata(df: pd.DataFrame, csv_path: Path) -> None:
    df.to_csv(csv_path, index=False)
    print(f"[OK] 'Source' column inserted as second column and file saved to: {csv_path}")


# ==========================================================
# MAIN
# ==========================================================
def main():
    print("=" * 60)
    print("ADD SOURCE COLUMN TO ISA METADATA")
    print("=" * 60)

    df = load_metadata(CSV_PATH)
    df = add_source_column(df)
    save_metadata(df, CSV_PATH)


if __name__ == "__main__":
    main()