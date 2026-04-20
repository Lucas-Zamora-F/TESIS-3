from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSTANCES_DIR = PROJECT_ROOT / "data" / "instances" / "sdplib"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "ISA metadata" / "intermediates" / "source_table.csv"
)


def _extract_source(instance_name: str) -> str:
    """
    Extract the source name from the instance file name.

    Examples
    --------
    arch0.dat-s -> arch
    beas2.dat-s -> beas

    Rule
    ----
    Take everything before the first digit.
    """
    match = re.match(r"^([^\d]+)", instance_name)

    if not match:
        raise ValueError(f"Could not extract source from instance name: {instance_name}")

    return match.group(1)


def _normalize_instances(
    instances: str | Path | Iterable[str | Path],
) -> list[Path]:
    """
    Accept:
    - a directory containing .dat-s files
    - a single instance file path
    - an iterable of instance file paths
    """
    if isinstance(instances, (str, Path)):
        instances_path = Path(instances)

        if instances_path.is_dir():
            instance_paths = sorted(instances_path.glob("*.dat-s"))
            if not instance_paths:
                raise FileNotFoundError(
                    f"No .dat-s files were found in: {instances_path}"
                )
            return instance_paths

        if instances_path.is_file():
            return [instances_path]

        raise FileNotFoundError(f"Instances path does not exist: {instances_path}")

    instance_paths = [Path(p) for p in instances]

    if not instance_paths:
        raise ValueError("The instance list is empty.")

    for path in instance_paths:
        if not path.exists():
            raise FileNotFoundError(f"Instance does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

    return sorted(instance_paths)


def build_source_table(
    instances: str | Path | Iterable[str | Path],
) -> pd.DataFrame:
    """
    Build a source table with the following structure:

    | Instance    | Source |
    |-------------|--------|
    | arch0.dat-s | arch   |
    | arch2.dat-s | arch   |

    The resulting dataframe is also saved to:
        ISA metadata/intermediates/source_table.csv

    The CSV file is overwritten on every run.
    """
    instance_paths = _normalize_instances(instances)

    rows: list[dict[str, str]] = []

    for instance_path in instance_paths:
        instance_name = instance_path.name
        source = _extract_source(instance_name)

        rows.append(
            {
                "Instance": instance_name,
                "Source": source,
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df[["Instance", "Source"]]

    save_source_table(df, DEFAULT_OUTPUT_PATH)

    return df


def save_source_table(df: pd.DataFrame, output_path: str | Path) -> Path:
    """
    Save the source table to CSV.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def _run_standalone() -> None:
    """
    Run the module as a standalone script.
    """
    print("========================================")
    print("BUILD SOURCE TABLE")
    print("========================================")
    print(f"[INFO] Instances directory : {DEFAULT_INSTANCES_DIR}")
    print(f"[INFO] Output path         : {DEFAULT_OUTPUT_PATH}")

    df = build_source_table(DEFAULT_INSTANCES_DIR)

    print(f"[OK] Source table saved to: {DEFAULT_OUTPUT_PATH}")
    print(f"[INFO] Rows: {len(df)}")
    print(f"[INFO] Columns: {len(df.columns)}")

    print("\n[INFO] Preview:")
    print(df.head())


if __name__ == "__main__":
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    _run_standalone()