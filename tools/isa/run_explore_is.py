# ======================================================================================
# RUN EXPLOREIS / INSTANCE SPACE
# ======================================================================================

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

import matlab.engine


# ======================================================================================
# DEFAULT PATHS
# ======================================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_INSTANCE_SPACE_PATH = PROJECT_ROOT / "extern" / "InstanceSpace"
DEFAULT_BUILD_BASE = PROJECT_ROOT / "matilda_out" / "build"
DEFAULT_EXPLORE_BASE = PROJECT_ROOT / "matilda_out" / "explore"


# ======================================================================================
# HELPER FUNCTIONS
# ======================================================================================

def _to_matlab_path(path: Path) -> str:
    """
    Convert a pathlib Path into a MATLAB-compatible path string.
    """
    return str(path.resolve()).replace("\\", "/")


def _extract_build_timestamp(build_dir_name: str) -> str:
    """
    Extract the timestamp portion from a build run directory name.

    Expected input:
        run_build_YYYYMMDD_HHMMSS

    Returns
    -------
    str
        The extracted timestamp string: YYYYMMDD_HHMMSS
    """
    match = re.fullmatch(r"run_build_(\d{8}_\d{6})", build_dir_name)
    if match is None:
        raise ValueError(
            f"Invalid build run directory name format: {build_dir_name}"
        )
    return match.group(1)


def _find_latest_build_run(build_base: Path) -> Path:
    """
    Find the most recent build run directory inside matilda_out/build.

    The selection is based on modification time.
    """
    if not build_base.exists():
        raise FileNotFoundError(f"Build output folder not found: {build_base}")

    run_dirs = [p for p in build_base.iterdir() if p.is_dir() and p.name.startswith("run_build_")]

    if not run_dirs:
        raise FileNotFoundError(
            f"No build run directories were found in: {build_base}"
        )

    latest_run = max(run_dirs, key=lambda p: p.stat().st_mtime)
    return latest_run


def _build_explore_run_dir(explore_base: Path, timestamp: str) -> Path:
    """
    Create a new explore run directory using the same timestamp as the source build run.

    Naming rule:
        run_explore_YYYYMMDD_HHMMSS
        run_explore_YYYYMMDD_HHMMSS_v2
        run_explore_YYYYMMDD_HHMMSS_v3
        ...

    Returns
    -------
    Path
        The created explore run directory path.
    """
    explore_base.mkdir(parents=True, exist_ok=True)

    base_name = f"run_explore_{timestamp}"
    candidate = explore_base / base_name

    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=False)
        return candidate

    version = 2
    while True:
        candidate = explore_base / f"{base_name}_v{version}"
        if not candidate.exists():
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        version += 1


def _prepare_explore_inputs(build_run_dir: Path, explore_run_dir: Path) -> None:
    """
    Prepare the input files required by exploreIS.

    Required by exploreIS:
    - model.mat
    - metadata_test.csv

    Source files taken from the selected build run:
    - model.mat
    - metadata.csv  -> renamed to metadata_test.csv
    """
    src_model = build_run_dir / "model.mat"
    src_metadata = build_run_dir / "metadata.csv"

    if not src_model.exists():
        raise FileNotFoundError(f"model.mat not found in build run: {src_model}")

    if not src_metadata.exists():
        raise FileNotFoundError(f"metadata.csv not found in build run: {src_metadata}")

    dst_model = explore_run_dir / "model.mat"
    dst_metadata_test = explore_run_dir / "metadata_test.csv"

    shutil.copy2(src_model, dst_model)
    shutil.copy2(src_metadata, dst_metadata_test)

    print(f"[OK] Copied model.mat       -> {dst_model}")
    print(f"[OK] Copied metadata.csv   -> {dst_metadata_test} (as metadata_test.csv)")


# ======================================================================================
# MAIN EXECUTION FUNCTION
# ======================================================================================

def run_explore_is(
    build_run_dir: Optional[Path] = None,
    instance_space_path: Optional[Path] = None,
    build_base: Optional[Path] = None,
    explore_base: Optional[Path] = None,
) -> Path:
    """
    Run InstanceSpace exploreIS using the latest build run by default.

    The script:
    1. Locates the latest build run in matilda_out/build (unless one is provided).
    2. Creates a new explore run directory in matilda_out/explore using the same timestamp.
    3. Copies:
        - model.mat
        - metadata.csv -> metadata_test.csv
    4. Runs exploreIS(rootdir).

    Parameters
    ----------
    build_run_dir : Path | None
        Specific build run directory to use.
        If None, the latest run in matilda_out/build is used.
    instance_space_path : Path | None
        Path to the extern/InstanceSpace submodule.
        If None, the default project path is used.
    build_base : Path | None
        Base directory containing build runs.
        If None, the default project path is used.
    explore_base : Path | None
        Base directory where explore runs will be created.
        If None, the default project path is used.

    Returns
    -------
    Path
        The generated explore run directory path.
    """
    instance_space_path = (
        Path(instance_space_path) if instance_space_path else DEFAULT_INSTANCE_SPACE_PATH
    )
    build_base = Path(build_base) if build_base else DEFAULT_BUILD_BASE
    explore_base = Path(explore_base) if explore_base else DEFAULT_EXPLORE_BASE

    if build_run_dir is not None:
        build_run_dir = Path(build_run_dir)
    else:
        build_run_dir = _find_latest_build_run(build_base)

    if not build_run_dir.exists():
        raise FileNotFoundError(f"Build run directory not found: {build_run_dir}")

    if not instance_space_path.exists():
        raise FileNotFoundError(
            f"InstanceSpace submodule not found at: {instance_space_path}"
        )

    timestamp = _extract_build_timestamp(build_run_dir.name)
    explore_run_dir = _build_explore_run_dir(explore_base, timestamp)

    print("=" * 80)
    print("RUN EXPLOREIS / INSTANCE SPACE")
    print("=" * 80)
    print(f"[INFO] Project root         : {PROJECT_ROOT}")
    print(f"[INFO] InstanceSpace path   : {instance_space_path}")
    print(f"[INFO] Build base           : {build_base}")
    print(f"[INFO] Selected build run   : {build_run_dir}")
    print(f"[INFO] Explore base         : {explore_base}")
    print(f"[INFO] Explore run dir      : {explore_run_dir}")

    print("\n[INFO] Preparing exploreIS input files...")
    _prepare_explore_inputs(build_run_dir, explore_run_dir)

    eng = None
    try:
        print("\n[INFO] Starting MATLAB engine...")
        eng = matlab.engine.start_matlab()

        matlab_instance_space_path = _to_matlab_path(instance_space_path)
        matlab_explore_run_dir = _to_matlab_path(explore_run_dir)

        print("[INFO] Adding InstanceSpace root to MATLAB path...")
        eng.addpath(matlab_instance_space_path, nargout=0)

        print("[INFO] Adding InstanceSpace subfolders recursively with genpath...")
        eng.eval(f"addpath(genpath('{matlab_instance_space_path}'));", nargout=0)

        print("[INFO] Running exploreIS(rootdir)...")
        eng.eval(f"exploreIS('{matlab_explore_run_dir}/');", nargout=0)

        print("[OK] exploreIS finished successfully")
        print(f"[OK] Outputs saved in: {explore_run_dir}")

    except Exception:
        print(f"[ERROR] exploreIS failed. Partial outputs may exist in: {explore_run_dir}")
        raise

    finally:
        if eng is not None:
            print("[INFO] Closing MATLAB engine...")
            eng.quit()
            print("[OK] MATLAB engine closed.")

    return explore_run_dir


# ======================================================================================
# STANDALONE ENTRY POINT
# ======================================================================================

def main() -> None:
    """
    Standalone entry point.
    """
    run_dir = run_explore_is()

    print("\n" + "=" * 80)
    print("EXPLOREIS FINISHED")
    print("=" * 80)
    print(f"[INFO] Run output directory: {run_dir}")


if __name__ == "__main__":
    main()