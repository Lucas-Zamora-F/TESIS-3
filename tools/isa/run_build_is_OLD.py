# ======================================================================================
# RUN BUILDIS / INSTANCE SPACE
# ======================================================================================

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import matlab.engine


# ======================================================================================
# DEFAULT PATHS
# ======================================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_METADATA_PATH = PROJECT_ROOT / "ISA metadata" / "metadata.csv"
DEFAULT_INSTANCE_SPACE_PATH = PROJECT_ROOT / "extern" / "InstanceSpace"
DEFAULT_OUTPUT_BASE = PROJECT_ROOT / "matilda_out" / "build"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "instance_space_config.json"


# ======================================================================================
# HELPER FUNCTIONS
# ======================================================================================

def _to_matlab_path(path: Path) -> str:
    """
    Convert a pathlib Path into a MATLAB-compatible path string.
    """
    return str(path.resolve()).replace("\\", "/")


def _timestamp() -> str:
    """
    Return a timestamp string for naming run directories.
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _create_run_dir(output_base: Path) -> Path:
    """
    Create a new run directory under the output base folder.

    Example:
        matilda_out/build/run_build_20260420_154500
    """
    run_dir = output_base / f"run_build_{_timestamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _normalize_instances_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the metadata contains an 'instances' column exactly with this name.

    The input CSV may contain a differently capitalized version such as:
    - Instances
    - INSTANCES
    - instances

    This function renames it to 'instances' if needed.
    """
    lower_to_original = {col.lower(): col for col in df.columns}

    if "instances" not in lower_to_original:
        raise ValueError("metadata.csv must contain an 'instances' column.")

    original_name = lower_to_original["instances"]
    if original_name != "instances":
        df = df.rename(columns={original_name: "instances"})

    return df


def _validate_metadata_columns(df: pd.DataFrame) -> None:
    """
    Validate that the metadata contains at least:
    - one feature_* column
    - one algo_* column
    """
    feature_cols = [col for col in df.columns if col.startswith("feature_")]
    algo_cols = [col for col in df.columns if col.startswith("algo_")]

    if not feature_cols:
        raise ValueError("metadata.csv does not contain any 'feature_*' columns.")

    if not algo_cols:
        raise ValueError("metadata.csv does not contain any 'algo_*' columns.")


def _prepare_metadata(src_metadata_path: Path, run_dir: Path) -> Path:
    """
    Load, validate, normalize, and copy the metadata.csv into the run directory.

    Returns
    -------
    Path
        The destination metadata.csv path inside the run directory.
    """
    if not src_metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {src_metadata_path}")

    print("[INFO] Loading metadata...")
    df = pd.read_csv(src_metadata_path)

    df = _normalize_instances_column(df)
    _validate_metadata_columns(df)

    dst_metadata_path = run_dir / "metadata.csv"
    df.to_csv(dst_metadata_path, index=False)

    print(f"[OK] Metadata prepared: {dst_metadata_path}")
    return dst_metadata_path


def _load_build_is_options(config_path: Path) -> dict:
    """
    Load buildIS options from the JSON configuration file.

    Supported formats:
    1) The JSON file itself is already the full InstanceSpace options object.
    2) The JSON file contains a top-level 'build_is_options' key.

    Returns
    -------
    dict
        A dictionary that will be written as options.json for buildIS.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    print(f"[INFO] Loading configuration from: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if not isinstance(config, dict):
        raise ValueError("instance_space_config.json must contain a JSON object.")

    if "build_is_options" in config:
        options = config["build_is_options"]
    else:
        options = config

    if not isinstance(options, dict):
        raise ValueError("The buildIS configuration must be a valid JSON object.")

    # Basic validation of the expected top-level keys
    required_keys = [
        "parallel",
        "perf",
        "auto",
        "bound",
        "norm",
        "selvars",
        "sifted",
        "outputs",
    ]

    missing_keys = [key for key in required_keys if key not in options]
    if missing_keys:
        raise ValueError(
            "Missing required keys in instance_space_config.json: "
            + ", ".join(missing_keys)
        )

    return options


def _write_options_json(run_dir: Path, options: dict) -> Path:
    """
    Write the buildIS options into options.json inside the run directory.

    Returns
    -------
    Path
        The written options.json path.
    """
    options_path = run_dir / "options.json"

    with open(options_path, "w", encoding="utf-8") as f:
        json.dump(options, f, indent=4)

    print(f"[OK] Options written: {options_path}")
    return options_path


# ======================================================================================
# MAIN EXECUTION FUNCTION
# ======================================================================================

def run_build_is(
    metadata_path: Optional[Path] = None,
    instance_space_path: Optional[Path] = None,
    output_base: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> Path:
    """
    Run InstanceSpace buildIS on an existing metadata.csv file.

    The execution output is stored in:
        matilda_out/build/run_build_YYYYMMDD_HHMMSS

    Parameters
    ----------
    metadata_path : Path | None
        Source path to the input metadata.csv file.
        If None, the default project path is used.
    instance_space_path : Path | None
        Path to the extern/InstanceSpace submodule.
        If None, the default project path is used.
    output_base : Path | None
        Base directory where the run_build_<timestamp> folder will be created.
        If None, the default project path is used.
    config_path : Path | None
        Path to config/instance_space_config.json.
        If None, the default project path is used.

    Returns
    -------
    Path
        The generated run directory path.
    """
    metadata_path = Path(metadata_path) if metadata_path else DEFAULT_METADATA_PATH
    instance_space_path = (
        Path(instance_space_path) if instance_space_path else DEFAULT_INSTANCE_SPACE_PATH
    )
    output_base = Path(output_base) if output_base else DEFAULT_OUTPUT_BASE
    config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH

    print("=" * 80)
    print("RUN BUILDIS / INSTANCE SPACE")
    print("=" * 80)
    print(f"[INFO] Project root         : {PROJECT_ROOT}")
    print(f"[INFO] Input metadata       : {metadata_path}")
    print(f"[INFO] Config path          : {config_path}")
    print(f"[INFO] InstanceSpace path   : {instance_space_path}")
    print(f"[INFO] Output base          : {output_base}")

    if not instance_space_path.exists():
        raise FileNotFoundError(
            f"InstanceSpace submodule not found at: {instance_space_path}"
        )

    print("\n[INFO] Creating run directory...")
    run_dir = _create_run_dir(output_base)
    print(f"[OK] Run directory created: {run_dir}")

    print("\n[INFO] Preparing metadata...")
    _prepare_metadata(metadata_path, run_dir)

    print("\n[INFO] Loading buildIS options from configuration...")
    options = _load_build_is_options(config_path)

    print("\n[INFO] Writing options.json...")
    _write_options_json(run_dir, options)

    eng = None
    try:
        print("\n[INFO] Starting MATLAB engine...")
        eng = matlab.engine.start_matlab()

        matlab_instance_space_path = _to_matlab_path(instance_space_path)
        matlab_run_dir = _to_matlab_path(run_dir)

        print("[INFO] Adding InstanceSpace root to MATLAB path...")
        eng.addpath(matlab_instance_space_path, nargout=0)

        print("[INFO] Adding InstanceSpace subfolders recursively with genpath...")
        eng.eval(f"addpath(genpath('{matlab_instance_space_path}'));", nargout=0)

        print("[INFO] Running buildIS(rootdir)...")
        eng.eval(f"buildIS('{matlab_run_dir}/');", nargout=0)

        print("[OK] buildIS finished successfully")
        print(f"[OK] Outputs saved in: {run_dir}")

    except Exception:
        print(f"[ERROR] buildIS failed. Partial outputs may exist in: {run_dir}")
        raise

    finally:
        if eng is not None:
            print("[INFO] Closing MATLAB engine...")
            eng.quit()
            print("[OK] MATLAB engine closed.")

    return run_dir


# ======================================================================================
# STANDALONE ENTRY POINT
# ======================================================================================

def main() -> None:
    """
    Standalone entry point.
    """
    run_dir = run_build_is()

    print("\n" + "=" * 80)
    print("BUILDIS FINISHED")
    print("=" * 80)
    print(f"[INFO] Run output directory: {run_dir}")


if __name__ == "__main__":
    main()