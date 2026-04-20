from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.isa.build_metadata.build_features_table import build_features_table
from tools.isa.build_metadata.build_solver_runtime_table import build_solver_runtime_table
from tools.isa.build_metadata.build_source_table import build_source_table
from tools.isa.build_metadata.build_isa_metadata_table import build_isa_metadata_table
from tools.logging.universal_logger import (
    setup_universal_logger,
    log_event,
    log_exception,
)


INTERMEDIATE_DIR = REPO_ROOT / "ISA metadata" / "intermediates"
SOURCE_TABLE_PATH = INTERMEDIATE_DIR / "source_table.csv"
FEATURES_TABLE_PATH = INTERMEDIATE_DIR / "features_table.csv"
SOLVER_RUNTIME_TABLE_PATH = INTERMEDIATE_DIR / "solver_runtime_table.csv"
METADATA_OUTPUT_PATH = REPO_ROOT / "ISA metadata" / "metadata.csv"


def orchestrate_isa_metadata(
    use_all_instances: bool = False,
    use_source_csv: bool = False,
    use_features_csv: bool = False,
    use_solver_runtime_csv: bool = False,
) -> pd.DataFrame:
    """
    Main orchestrator for ISA metadata generation.

    Parameters
    ----------
    use_all_instances : bool
        - False -> use enabled_instances from config
        - True  -> use all instances in sdplib

    use_source_csv : bool
        If True, load source_table from ISA metadata/intermediates/source_table.csv.
        If False, rebuild source_table.

    use_features_csv : bool
        If True, load features_table from ISA metadata/intermediates/features_table.csv.
        If False, rebuild features_table.

    use_solver_runtime_csv : bool
        If True, load solver_runtime_table from
        ISA metadata/intermediates/solver_runtime_table.csv.
        If False, rebuild solver_runtime_table.

    Returns
    -------
    pd.DataFrame
        Final merged metadata dataframe.
    """
    setup_universal_logger()

    instances_config_path = REPO_ROOT / "config" / "instances_config.json"
    features_config_path = REPO_ROOT / "config" / "features_config.json"
    solver_registry_path = REPO_ROOT / "config" / "solver_registry.json"
    instances_dir = REPO_ROOT / "data" / "instances" / "sdplib"

    try:
        log_event(
            "INFO",
            "orchestrator",
            "Starting ISA metadata orchestration.",
            extra={
                "use_all_instances": use_all_instances,
                "use_source_csv": use_source_csv,
                "use_features_csv": use_features_csv,
                "use_solver_runtime_csv": use_solver_runtime_csv,
            },
        )

        if use_all_instances:
            enabled_instance_paths = _get_all_instances(instances_dir)
            print("[INFO] Mode: ALL instances")
        else:
            enabled_instance_names = _load_enabled_instances(instances_config_path)
            enabled_instance_paths = _resolve_instance_paths(
                instance_names=enabled_instance_names,
                instances_dir=instances_dir,
            )
            print("[INFO] Mode: enabled_instances from config")

        print("========================================")
        print("ISA METADATA ORCHESTRATOR")
        print("========================================")
        print(f"[INFO] Instances: {len(enabled_instance_paths)}")
        print(f"[INFO] Source table mode         : {'CSV' if use_source_csv else 'BUILD'}")
        print(f"[INFO] Features table mode       : {'CSV' if use_features_csv else 'BUILD'}")
        print(
            f"[INFO] Solver runtime table mode : "
            f"{'CSV' if use_solver_runtime_csv else 'BUILD'}"
        )

        log_event(
            "INFO",
            "orchestrator",
            "Instances selected.",
            extra={
                "count": len(enabled_instance_paths),
                "use_all_instances": use_all_instances,
            },
        )

        source_table = _get_source_table(
            enabled_instance_paths=enabled_instance_paths,
            use_csv=use_source_csv,
        )
        _validate_dataframe(source_table, "source_table")
        _validate_required_columns(source_table, "source_table", ["Instance", "Source"])

        features_table = _get_features_table(
            enabled_instance_paths=enabled_instance_paths,
            features_config_path=features_config_path,
            use_csv=use_features_csv,
        )
        _validate_dataframe(features_table, "features_table")
        _validate_required_columns(features_table, "features_table", ["Instance"])

        solver_runtime_table = _get_solver_runtime_table(
            enabled_instance_paths=enabled_instance_paths,
            solver_registry_path=solver_registry_path,
            use_csv=use_solver_runtime_csv,
        )
        _validate_dataframe(solver_runtime_table, "solver_runtime_table")
        _validate_required_columns(solver_runtime_table, "solver_runtime_table", ["Instance"])

        print("[INFO] Building metadata_df...")
        metadata_df = build_isa_metadata_table(
            features_table,
            solver_runtime_table,
            source_table,
        )
        _validate_dataframe(metadata_df, "metadata_df")

        METADATA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        metadata_df.to_csv(METADATA_OUTPUT_PATH, index=False)

        log_event(
            "INFO",
            "orchestrator",
            "Metadata saved successfully.",
            extra={
                "output_path": str(METADATA_OUTPUT_PATH),
                "row_count": len(metadata_df),
                "column_count": len(metadata_df.columns),
            },
        )

        print(f"[OK] Metadata saved to: {METADATA_OUTPUT_PATH}")
        print("\n[INFO] Metadata preview:")
        print(metadata_df.head())

        return metadata_df

    except Exception as exc:
        log_exception(
            "orchestrator",
            "ISA metadata orchestration failed.",
            exc,
        )
        raise


def _get_source_table(
    enabled_instance_paths: list[str],
    use_csv: bool,
) -> pd.DataFrame:
    """
    Load source_table from CSV or rebuild it.
    """
    if use_csv:
        print(f"\n[INFO] Loading source_table from CSV: {SOURCE_TABLE_PATH}")
        return _load_dataframe_from_csv(SOURCE_TABLE_PATH, "source_table")

    print("\n[INFO] Building source_table...")
    return build_source_table(enabled_instance_paths)


def _get_features_table(
    enabled_instance_paths: list[str],
    features_config_path: Path,
    use_csv: bool,
) -> pd.DataFrame:
    """
    Load features_table from CSV or rebuild it.
    """
    if use_csv:
        print(f"\n[INFO] Loading features_table from CSV: {FEATURES_TABLE_PATH}")
        return _load_dataframe_from_csv(FEATURES_TABLE_PATH, "features_table")

    print("\n[INFO] Building features_table...")
    return build_features_table(
        enabled_instance_paths,
        str(features_config_path),
    )


def _get_solver_runtime_table(
    enabled_instance_paths: list[str],
    solver_registry_path: Path,
    use_csv: bool,
) -> pd.DataFrame:
    """
    Load solver_runtime_table from CSV or rebuild it.
    """
    if use_csv:
        print(
            f"\n[INFO] Loading solver_runtime_table from CSV: "
            f"{SOLVER_RUNTIME_TABLE_PATH}"
        )
        return _load_dataframe_from_csv(
            SOLVER_RUNTIME_TABLE_PATH,
            "solver_runtime_table",
        )

    print("\n[INFO] Building solver_runtime_table...")
    return build_solver_runtime_table(
        enabled_instance_paths,
        str(solver_registry_path),
    )


def _load_dataframe_from_csv(csv_path: Path, dataframe_name: str) -> pd.DataFrame:
    """
    Load a dataframe from CSV and validate that the file exists.
    """
    if not csv_path.exists():
        raise FileNotFoundError(
            f"{dataframe_name} CSV file does not exist: {csv_path}"
        )

    df = pd.read_csv(csv_path)

    if df.empty:
        raise ValueError(f"{dataframe_name} loaded from CSV is empty: {csv_path}")

    return df


def _get_all_instances(instances_dir: Path) -> list[str]:
    """
    Return all .dat-s instances inside the sdplib directory.
    """
    if not instances_dir.exists():
        raise FileNotFoundError(f"Directory does not exist: {instances_dir}")

    instances = sorted(instances_dir.glob("*.dat-s"))

    if not instances:
        raise ValueError("No .dat-s files were found in sdplib.")

    return [str(path) for path in instances]


def _load_enabled_instances(config_path: Path) -> list[str]:
    """
    Load enabled instance names from instances_config.json.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if "enabled_instances" not in config:
        raise KeyError("The config file is missing the 'enabled_instances' key.")

    enabled_instances = config["enabled_instances"]

    if not isinstance(enabled_instances, list):
        raise TypeError("'enabled_instances' must be a list.")

    if not enabled_instances:
        raise ValueError("'enabled_instances' is empty.")

    return enabled_instances


def _resolve_instance_paths(
    instance_names: list[str],
    instances_dir: Path,
) -> list[str]:
    """
    Resolve instance file names into full paths.
    """
    resolved_paths: list[str] = []

    for name in instance_names:
        path = instances_dir / name

        if not path.exists():
            raise FileNotFoundError(f"Instance file not found: {path}")

        if not path.is_file():
            raise ValueError(f"Resolved path is not a file: {path}")

        resolved_paths.append(str(path))

    return resolved_paths


def _validate_dataframe(df: pd.DataFrame, name: str) -> None:
    """
    Validate that the object is a non-empty DataFrame.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} is not a pandas.DataFrame.")

    if df.empty:
        raise ValueError(f"{name} is empty.")


def _validate_required_columns(
    df: pd.DataFrame,
    name: str,
    required_columns: list[str],
) -> None:
    """
    Validate that the dataframe contains the required columns.
    """
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"{name} is missing required columns: {missing_columns}"
        )


def _prompt_yes_no(message: str, default: bool) -> bool:
    """
    Prompt the user for a yes/no answer in standalone mode.
    """
    default_text = "Y/n" if default else "y/N"

    while True:
        answer = input(f"{message} [{default_text}]: ").strip().lower()

        if answer == "":
            return default

        if answer in {"y", "yes"}:
            return True

        if answer in {"n", "no"}:
            return False

        print("Please answer with 'y' or 'n'.")


def _run_standalone() -> None:
    """
    Run the orchestrator in standalone mode with interactive prompts.
    """
    print("========================================")
    print("ISA METADATA ORCHESTRATOR")
    print("========================================")

    use_all_instances = _prompt_yes_no(
        "Use all instances in sdplib?",
        default=False,
    )

    use_source_csv = _prompt_yes_no(
        "Load source_table from CSV instead of rebuilding it?",
        default=False,
    )

    use_features_csv = _prompt_yes_no(
        "Load features_table from CSV instead of rebuilding it?",
        default=False,
    )

    use_solver_runtime_csv = _prompt_yes_no(
        "Load solver_runtime_table from CSV instead of rebuilding it?",
        default=False,
    )

    orchestrate_isa_metadata(
        use_all_instances=use_all_instances,
        use_source_csv=use_source_csv,
        use_features_csv=use_features_csv,
        use_solver_runtime_csv=use_solver_runtime_csv,
    )


if __name__ == "__main__":
    _run_standalone()