from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.isa.build_metadata.build_features_table import build_features_table
from tools.isa.build_metadata.build_solver_runtime_table import build_solver_runtime_table
from tools.isa.build_metadata.build_source_table import build_source_table
from tools.isa.build_metadata.build_isa_metadata_table import build_isa_metadata_table
from tools.features.instance_reader import collect_supported_instances
from tools.logging.universal_logger import (
    setup_universal_logger,
    log_event,
    log_exception,
)


CONFIG_PATH = REPO_ROOT / "config" / "metadata_orchestrator_config.json"
INTERMEDIATE_DIR = REPO_ROOT / "ISA metadata" / "intermediates"
SOURCE_TABLE_PATH = INTERMEDIATE_DIR / "source_table.csv"
FEATURES_TABLE_PATH = INTERMEDIATE_DIR / "features_table.csv"
SOLVER_RUNTIME_TABLE_PATH = INTERMEDIATE_DIR / "solver_runtime_table.csv"


def orchestrate_isa_metadata(
    config_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Main orchestrator for ISA metadata generation.

    Parameters
    ----------
    config_path : str | Path | None
        Path to metadata_orchestrator_config.json.
        If None, uses the default config path in /config.

    Returns
    -------
    pd.DataFrame
        Final merged metadata dataframe.
    """
    resolved_config_path = Path(config_path) if config_path else CONFIG_PATH
    config = _load_orchestrator_config(resolved_config_path)

    logging_enabled = config["logging"]["enabled"]
    if logging_enabled:
        setup_universal_logger()

    instances_config_path = REPO_ROOT / "config" / "instances_config.json"
    features_config_path = REPO_ROOT / "config" / "features_config.json"
    solver_registry_path = REPO_ROOT / "config" / "solver_registry.json"
    instances_roots = {
        "sdplib": REPO_ROOT / "data" / "instances" / "sdplib",
        "dimacs": REPO_ROOT / "data" / "instances" / "DIMACS" / "instances",
    }

    instances_mode = config["instances"]["mode"]
    source_mode = config["pipeline"]["source_table"]["mode"]
    features_mode = config["pipeline"]["features_table"]["mode"]
    solver_runtime_mode = config["pipeline"]["solver_runtime_table"]["mode"]

    save_metadata = config["output"]["save_metadata"]
    metadata_output_path = REPO_ROOT / config["output"]["metadata_path"]

    try:
        _log_info(
            logging_enabled,
            "orchestrator",
            "Starting ISA metadata orchestration.",
            extra={
                "config_path": str(resolved_config_path),
                "instances_mode": instances_mode,
                "source_table_mode": source_mode,
                "features_table_mode": features_mode,
                "solver_runtime_table_mode": solver_runtime_mode,
                "save_metadata": save_metadata,
                "metadata_output_path": str(metadata_output_path),
            },
        )

        print("========================================")
        print("ISA METADATA ORCHESTRATOR")
        print("========================================")
        print(f"[INFO] Config path               : {resolved_config_path}")
        print(f"[INFO] Instances mode           : {instances_mode}")
        print(f"[INFO] Source table mode        : {source_mode.upper()}")
        print(f"[INFO] Features table mode      : {features_mode.upper()}")
        print(f"[INFO] Solver runtime mode      : {solver_runtime_mode.upper()}")
        print(f"[INFO] Save metadata            : {save_metadata}")
        print(f"[INFO] Metadata output path     : {metadata_output_path}")

        enabled_instance_paths = _get_instance_paths(
            instances_mode=instances_mode,
            instances_config_path=instances_config_path,
            instances_roots=instances_roots,
        )

        print(f"[INFO] Instances selected       : {len(enabled_instance_paths)}")

        _log_info(
            logging_enabled,
            "orchestrator",
            "Instances selected.",
            extra={
                "count": len(enabled_instance_paths),
                "instances_mode": instances_mode,
            },
        )

        source_table = _get_source_table(
            enabled_instance_paths=enabled_instance_paths,
            mode=source_mode,
        )
        _validate_dataframe(source_table, "source_table")
        _validate_required_columns(source_table, "source_table", ["Instance", "Source"])

        features_table = _get_features_table(
            enabled_instance_paths=enabled_instance_paths,
            features_config_path=features_config_path,
            mode=features_mode,
        )
        _validate_dataframe(features_table, "features_table")
        _validate_required_columns(features_table, "features_table", ["Instance"])

        solver_runtime_table = _get_solver_runtime_table(
            enabled_instance_paths=enabled_instance_paths,
            solver_registry_path=solver_registry_path,
            mode=solver_runtime_mode,
        )
        _validate_dataframe(solver_runtime_table, "solver_runtime_table")
        _validate_required_columns(solver_runtime_table, "solver_runtime_table", ["Instance"])

        print("\n[INFO] Building metadata_df...")
        metadata_df = build_isa_metadata_table(
            features_table,
            solver_runtime_table,
            source_table,
        )
        _validate_dataframe(metadata_df, "metadata_df")

        if save_metadata:
            metadata_output_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_df.to_csv(metadata_output_path, index=False)

            print(f"[OK] Metadata saved to: {metadata_output_path}")

            _log_info(
                logging_enabled,
                "orchestrator",
                "Metadata saved successfully.",
                extra={
                    "output_path": str(metadata_output_path),
                    "row_count": len(metadata_df),
                    "column_count": len(metadata_df.columns),
                },
            )
        else:
            print("[INFO] Metadata saving disabled by config.")

            _log_info(
                logging_enabled,
                "orchestrator",
                "Metadata generated but not saved because save_metadata is false.",
                extra={
                    "row_count": len(metadata_df),
                    "column_count": len(metadata_df.columns),
                },
            )

        print("\n[INFO] Metadata preview:")
        print(metadata_df.head())

        return metadata_df

    except Exception as exc:
        if logging_enabled:
            log_exception(
                "orchestrator",
                "ISA metadata orchestration failed.",
                exc,
            )
        raise


def _load_orchestrator_config(config_path: Path) -> dict[str, Any]:
    """
    Load and validate metadata orchestrator config.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Orchestrator config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    _validate_orchestrator_config(config)

    return config


def _validate_orchestrator_config(config: dict[str, Any]) -> None:
    """
    Validate the structure and values of metadata_orchestrator_config.json.
    """
    required_top_keys = ["instances", "pipeline", "output", "logging"]
    for key in required_top_keys:
        if key not in config:
            raise KeyError(f"Missing top-level config key: '{key}'")

    if "mode" not in config["instances"]:
        raise KeyError("Missing key: 'instances.mode'")

    valid_instance_modes = {"enabled", "all"}
    instances_mode = config["instances"]["mode"]
    if instances_mode not in valid_instance_modes:
        raise ValueError(
            f"Invalid instances.mode: '{instances_mode}'. "
            f"Valid options are: {sorted(valid_instance_modes)}"
        )

    if "source_table" not in config["pipeline"]:
        raise KeyError("Missing key: 'pipeline.source_table'")
    if "features_table" not in config["pipeline"]:
        raise KeyError("Missing key: 'pipeline.features_table'")
    if "solver_runtime_table" not in config["pipeline"]:
        raise KeyError("Missing key: 'pipeline.solver_runtime_table'")

    valid_pipeline_modes = {"build", "csv"}

    source_mode = config["pipeline"]["source_table"].get("mode")
    features_mode = config["pipeline"]["features_table"].get("mode")
    solver_runtime_mode = config["pipeline"]["solver_runtime_table"].get("mode")

    if source_mode not in valid_pipeline_modes:
        raise ValueError(
            f"Invalid pipeline.source_table.mode: '{source_mode}'. "
            f"Valid options are: {sorted(valid_pipeline_modes)}"
        )

    if features_mode not in valid_pipeline_modes:
        raise ValueError(
            f"Invalid pipeline.features_table.mode: '{features_mode}'. "
            f"Valid options are: {sorted(valid_pipeline_modes)}"
        )

    if solver_runtime_mode not in valid_pipeline_modes:
        raise ValueError(
            f"Invalid pipeline.solver_runtime_table.mode: '{solver_runtime_mode}'. "
            f"Valid options are: {sorted(valid_pipeline_modes)}"
        )

    if "save_metadata" not in config["output"]:
        raise KeyError("Missing key: 'output.save_metadata'")
    if "metadata_path" not in config["output"]:
        raise KeyError("Missing key: 'output.metadata_path'")

    if not isinstance(config["output"]["save_metadata"], bool):
        raise TypeError("'output.save_metadata' must be a boolean.")

    if not isinstance(config["output"]["metadata_path"], str):
        raise TypeError("'output.metadata_path' must be a string.")

    if "enabled" not in config["logging"]:
        raise KeyError("Missing key: 'logging.enabled'")
    if "level" not in config["logging"]:
        raise KeyError("Missing key: 'logging.level'")

    if not isinstance(config["logging"]["enabled"], bool):
        raise TypeError("'logging.enabled' must be a boolean.")

    if not isinstance(config["logging"]["level"], str):
        raise TypeError("'logging.level' must be a string.")


def _get_instance_paths(
    instances_mode: str,
    instances_config_path: Path,
    instances_roots: dict[str, Path],
) -> list[str]:
    """
    Resolve which instances to use based on config mode.
    """
    if instances_mode == "all":
        print("[INFO] Loading all supported instances...")
        return _get_all_instances(instances_roots)

    if instances_mode == "enabled":
        print("[INFO] Loading enabled instances from instances_config.json...")
        enabled_instance_names = _load_enabled_instances(instances_config_path)
        return _resolve_instance_paths(
            instance_names=enabled_instance_names,
            instances_roots=instances_roots,
        )

    raise ValueError(f"Unsupported instances_mode: {instances_mode}")


def _get_source_table(
    enabled_instance_paths: list[str],
    mode: str,
) -> pd.DataFrame:
    """
    Load source_table from CSV or rebuild it.
    """
    if mode == "csv":
        print(f"\n[INFO] Loading source_table from CSV: {SOURCE_TABLE_PATH}")
        return _load_dataframe_from_csv(SOURCE_TABLE_PATH, "source_table")

    if mode == "build":
        print("\n[INFO] Building source_table...")
        return build_source_table(enabled_instance_paths)

    raise ValueError(f"Unsupported source_table mode: {mode}")


def _get_features_table(
    enabled_instance_paths: list[str],
    features_config_path: Path,
    mode: str,
) -> pd.DataFrame:
    """
    Load features_table from CSV or rebuild it.
    """
    if mode == "csv":
        print(f"\n[INFO] Loading features_table from CSV: {FEATURES_TABLE_PATH}")
        return _load_dataframe_from_csv(FEATURES_TABLE_PATH, "features_table")

    if mode == "build":
        print("\n[INFO] Building features_table...")
        return build_features_table(
            enabled_instance_paths,
            str(features_config_path),
        )

    raise ValueError(f"Unsupported features_table mode: {mode}")


def _get_solver_runtime_table(
    enabled_instance_paths: list[str],
    solver_registry_path: Path,
    mode: str,
) -> pd.DataFrame:
    """
    Load solver_runtime_table from CSV or rebuild it.
    """
    if mode == "csv":
        print(
            f"\n[INFO] Loading solver_runtime_table from CSV: "
            f"{SOLVER_RUNTIME_TABLE_PATH}"
        )
        return _load_dataframe_from_csv(
            SOLVER_RUNTIME_TABLE_PATH,
            "solver_runtime_table",
        )

    if mode == "build":
        print("\n[INFO] Building solver_runtime_table...")
        return build_solver_runtime_table(
            enabled_instance_paths,
            str(solver_registry_path),
        )

    raise ValueError(f"Unsupported solver_runtime_table mode: {mode}")


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


def _get_all_instances(instances_roots: dict[str, Path]) -> list[str]:
    """
    Return all supported instance files from every configured instance root.
    """
    instances: list[Path] = []

    for section_name, root in instances_roots.items():
        if not root.exists():
            raise FileNotFoundError(
                f"Directory for instance section '{section_name}' does not exist: {root}"
            )
        instances.extend(collect_supported_instances(root))

    if not instances:
        raise ValueError("No supported instance files were found.")

    return [str(path) for path in sorted(instances)]


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
    instances_roots: dict[str, Path],
) -> list[str]:
    """
    Resolve instance file names into full paths.
    """
    resolved_paths: list[str] = []

    for name in instance_names:
        raw_path = Path(name)
        candidates: list[Path] = []

        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            candidates.extend(root / name for root in instances_roots.values())

        path = next((candidate for candidate in candidates if candidate.exists()), None)

        if path is None:
            searched = ", ".join(str(candidate) for candidate in candidates)
            raise FileNotFoundError(
                f"Instance file not found for '{name}'. Searched: {searched}"
            )

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


def _log_info(
    logging_enabled: bool,
    source: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Log an INFO event only if logging is enabled.
    """
    if logging_enabled:
        log_event("INFO", source, message, extra=extra)


if __name__ == "__main__":
    orchestrate_isa_metadata()
