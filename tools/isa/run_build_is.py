#ISA SUBMODULE VERSION: c31aea51dcd7c26388ead78fb78a5be66d7efe5c extern/InstanceSpace (v0.3.3-12-gc31aea5)


# ======================================================================================
# RUN BUILDIS / INSTANCE SPACE
# ======================================================================================

from __future__ import annotations

import json
import shutil
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


def _prepare_clean_output_dir(output_base: Path) -> Path:
    """
    Clean matilda_out/build and use it as the build output directory.
    """
    resolved_output = output_base.resolve()
    resolved_expected_parent = (PROJECT_ROOT / "matilda_out").resolve()

    if resolved_output.parent != resolved_expected_parent or resolved_output.name != "build":
        raise ValueError(
            "Refusing to clean an unexpected build output directory: "
            f"{resolved_output}"
        )

    output_base.mkdir(parents=True, exist_ok=True)

    for child in output_base.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    return output_base


def _normalize_instances_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure the metadata contains an 'instances' column exactly with this name.
    """
    lower_to_original = {col.lower(): col for col in df.columns}

    if "instances" not in lower_to_original:
        raise ValueError("metadata.csv must contain an 'instances' column.")

    original_name = lower_to_original["instances"]
    if original_name != "instances":
        df = df.rename(columns={original_name: "instances"})

    return df


def _normalize_source_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize 'Source' / 'SOURCE' / 'source' into exactly 'source' if present.
    """
    lower_to_original = {col.lower(): col for col in df.columns}

    if "source" in lower_to_original:
        original_name = lower_to_original["source"]
        if original_name != "source":
            df = df.rename(columns={original_name: "source"})

    return df


def _validate_metadata_columns(df: pd.DataFrame) -> None:
    """
    Validate that metadata contains:
    - instances
    - at least one feature_* column
    - at least one algo_* column
    """
    if "instances" not in df.columns:
        raise ValueError("metadata.csv must contain an 'instances' column.")

    feature_cols = [col for col in df.columns if col.startswith("feature_")]
    algo_cols = [col for col in df.columns if col.startswith("algo_")]

    if not feature_cols:
        raise ValueError("metadata.csv does not contain any 'feature_*' columns.")

    if not algo_cols:
        raise ValueError("metadata.csv does not contain any 'algo_*' columns.")


def _print_metadata_summary(df: pd.DataFrame) -> None:
    """
    Print a concise metadata summary for debugging.
    """
    feature_cols = [col for col in df.columns if col.startswith("feature_")]
    algo_cols = [col for col in df.columns if col.startswith("algo_")]
    has_source = "source" in df.columns

    print("[INFO] Metadata summary:")
    print(f"       Rows                  : {len(df)}")
    print(f"       Total columns         : {len(df.columns)}")
    print(f"       Feature columns       : {len(feature_cols)}")
    print(f"       Algorithm columns     : {len(algo_cols)}")
    print(f"       Contains source       : {has_source}")


def _print_feature_diagnostics(df: pd.DataFrame) -> None:
    """
    Print diagnostics for feature columns:
    - missing values
    - unique values
    - constant features
    """
    feature_cols = [col for col in df.columns if col.startswith("feature_")]
    if not feature_cols:
        return

    feature_df = df[feature_cols]

    missing_count = feature_df.isna().sum()
    unique_count = feature_df.nunique(dropna=True)

    constant_features = unique_count[unique_count <= 1].index.tolist()
    all_nan_features = missing_count[missing_count == len(df)].index.tolist()

    print("\n" + "=" * 80)
    print("FEATURE DIAGNOSTICS")
    print("=" * 80)
    print(f"[INFO] Total feature columns        : {len(feature_cols)}")
    print(f"[INFO] Constant feature columns    : {len(constant_features)}")
    print(f"[INFO] All-NaN feature columns     : {len(all_nan_features)}")

    if constant_features:
        print("[WARN] Constant features:")
        for col in constant_features:
            print(f"       - {col}")

    if all_nan_features:
        print("[WARN] All-NaN features:")
        for col in all_nan_features:
            print(f"       - {col}")

    print("[INFO] Feature missing values:")
    for col, val in missing_count.items():
        print(f"       - {col}: {val}")

    print("[INFO] Feature unique values:")
    for col, val in unique_count.items():
        print(f"       - {col}: {val}")


def _print_algorithm_diagnostics(df: pd.DataFrame) -> None:
    """
    Print diagnostics for algorithm columns:
    - missing values
    - min / max
    - rows where all algorithms are NaN
    """
    algo_cols = [col for col in df.columns if col.startswith("algo_")]
    if not algo_cols:
        return

    algo_df = df[algo_cols]

    print("\n" + "=" * 80)
    print("ALGORITHM DIAGNOSTICS")
    print("=" * 80)

    missing_count = algo_df.isna().sum()
    non_missing_count = algo_df.notna().sum()
    min_vals = algo_df.min(numeric_only=True)
    max_vals = algo_df.max(numeric_only=True)

    print(f"[INFO] Total algorithm columns      : {len(algo_cols)}")

    print("[INFO] Algorithm missing values:")
    for col, val in missing_count.items():
        print(f"       - {col}: {val}")

    print("[INFO] Algorithm non-missing values:")
    for col, val in non_missing_count.items():
        print(f"       - {col}: {val}")

    print("[INFO] Algorithm minimum values:")
    for col, val in min_vals.items():
        print(f"       - {col}: {val}")

    print("[INFO] Algorithm maximum values:")
    for col, val in max_vals.items():
        print(f"       - {col}: {val}")

    rows_all_nan = int(algo_df.isna().all(axis=1).sum())
    print(f"[INFO] Rows with all algo_* as NaN : {rows_all_nan}")


def _prepare_metadata(src_metadata_path: Path, run_dir: Path) -> Path:
    """
    Load, validate, normalize, and copy metadata.csv into the run directory.

    Returns
    -------
    Path
        Destination metadata.csv path inside the run directory.
    """
    if not src_metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found: {src_metadata_path}")

    print("[INFO] Loading metadata CSV...")
    df = pd.read_csv(src_metadata_path)

    df = _normalize_instances_column(df)
    df = _normalize_source_column(df)

    _validate_metadata_columns(df)
    _print_metadata_summary(df)
    _print_feature_diagnostics(df)
    _print_algorithm_diagnostics(df)

    dst_metadata_path = run_dir / "metadata.csv"
    df.to_csv(dst_metadata_path, index=False)

    print(f"\n[OK] Metadata prepared: {dst_metadata_path}")
    return dst_metadata_path


def _inject_option_defaults(options: dict) -> dict:
    """
    Inject defensive defaults expected by the current InstanceSpace buildIS workflow.
    """
    options = dict(options)

    options.setdefault("perf", {})
    options["perf"].setdefault("MaxPerf", False)
    options["perf"].setdefault("AbsPerf", False)
    options["perf"].setdefault("epsilon", 0.30)
    options["perf"].setdefault("betaThreshold", 0.55)

    options.setdefault("auto", {})
    options["auto"].setdefault("preproc", True)

    options.setdefault("bound", {})
    options["bound"].setdefault("flag", True)

    options.setdefault("norm", {})
    options["norm"].setdefault("flag", True)

    options.setdefault("selvars", {})
    options["selvars"].setdefault("smallscaleflag", False)
    options["selvars"].setdefault("smallscale", 0.3)
    options["selvars"].setdefault("fileidxflag", False)
    options["selvars"].setdefault("fileidx", "")

    options.setdefault("sifted", {})
    options["sifted"].setdefault("flag", False)
    options["sifted"].setdefault("rho", 0.3)
    options["sifted"].setdefault("K", 6)
    options["sifted"].setdefault("N", 1000)

    options.setdefault("pilot", {})
    options["pilot"].setdefault("analytic", False)
    options["pilot"].setdefault("ntries", 10)
    options["pilot"].setdefault("ISA3D", False)

    options.setdefault("cloister", {})
    options["cloister"].setdefault("pval", 0.05)
    options["cloister"].setdefault("cthres", 0.7)

    options.setdefault("pythia", {})
    options["pythia"].setdefault("cvgrid", 10)
    options["pythia"].setdefault("maxcvgrid", 5)
    options["pythia"].setdefault("mincvgrid", -5)
    options["pythia"].setdefault("cvfolds", 5)

    options.setdefault("trace", {})
    options["trace"].setdefault("usesim", False)
    options["trace"].setdefault("RHO", 10)
    options["trace"].setdefault("PI", 0.75)
    options["trace"].setdefault("PCTILE", 0.3)
    options["trace"].setdefault("Trace2", False)

    options.setdefault("outputs", {})
    options["outputs"].setdefault("csv", True)
    options["outputs"].setdefault("web", False)
    options["outputs"].setdefault("png", True)

    return options


def _load_build_is_options(config_path: Path) -> dict:
    """
    Load buildIS options from the JSON configuration file.

    Supported formats:
    1) The JSON itself is already the full options object.
    2) The JSON contains a top-level 'build_is_options' key.
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

    if not options:
        raise ValueError("The buildIS configuration is empty.")

    options = _inject_option_defaults(options)

    print("[INFO] Top-level buildIS option keys:")
    for key in options.keys():
        print(f"       - {key}")

    return options


def _write_options_json(run_dir: Path, options: dict) -> Path:
    """
    Write buildIS options into options.json inside the run directory.
    """
    options_path = run_dir / "options.json"

    with open(options_path, "w", encoding="utf-8") as f:
        json.dump(options, f, indent=4)

    print(f"[OK] Options written: {options_path}")
    return options_path


def _validate_instance_space_path(instance_space_path: Path) -> None:
    """
    Validate that the InstanceSpace submodule exists and looks usable.
    """
    if not instance_space_path.exists():
        raise FileNotFoundError(
            f"InstanceSpace submodule not found at: {instance_space_path}"
        )

    buildis_path = instance_space_path / "buildIS.m"
    if not buildis_path.exists():
        raise FileNotFoundError(
            f"buildIS.m not found inside InstanceSpace path: {buildis_path}"
        )


def _write_run_manifest(
    run_dir: Path,
    metadata_path: Path,
    config_path: Path,
    instance_space_path: Path,
) -> Path:
    """
    Write a small manifest JSON for reproducibility/debugging.
    """
    manifest = {
        "created_at": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT.resolve()),
        "input_metadata_path": str(metadata_path.resolve()),
        "config_path": str(config_path.resolve()),
        "instance_space_path": str(instance_space_path.resolve()),
        "run_dir": str(run_dir.resolve()),
    }

    manifest_path = run_dir / "run_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

    print(f"[OK] Run manifest written: {manifest_path}")
    return manifest_path


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

    Parameters
    ----------
    metadata_path : Path | None
        Source path to input metadata.csv.
    instance_space_path : Path | None
        Path to extern/InstanceSpace.
    output_base : Path | None
        Directory where build outputs will be written directly.
    config_path : Path | None
        Path to config/instance_space_config.json.

    Returns
    -------
    Path
        Build output directory path.
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

    _validate_instance_space_path(instance_space_path)

    print("\n[INFO] Cleaning build output directory...")
    run_dir = _prepare_clean_output_dir(output_base)
    print(f"[OK] Build output directory ready: {run_dir}")

    print("\n[INFO] Preparing metadata...")
    _prepare_metadata(metadata_path, run_dir)

    print("\n[INFO] Loading buildIS options from configuration...")
    options = _load_build_is_options(config_path)

    print("\n[INFO] Writing options.json...")
    _write_options_json(run_dir, options)

    print("\n[INFO] Writing run manifest...")
    _write_run_manifest(
        run_dir=run_dir,
        metadata_path=metadata_path,
        config_path=config_path,
        instance_space_path=instance_space_path,
    )

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

        print("[INFO] Changing MATLAB working directory to run directory...")
        eng.cd(matlab_run_dir, nargout=0)

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
