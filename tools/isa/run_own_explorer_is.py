# ======================================================================================
# RUN OWN EXPLORE IS
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
DEFAULT_BUILD_BASE = PROJECT_ROOT / "matilda_out" / "build"
DEFAULT_EXPLORE_BASE = PROJECT_ROOT / "matilda_out" / "explore"
DEFAULT_CUSTOM_EXPLORE_PATH = PROJECT_ROOT / "tools" / "exploreIS"


# ======================================================================================
# HELPERS
# ======================================================================================

def _to_matlab_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def _extract_build_timestamp(build_dir_name: str) -> str:
    """
    Accept:
        run_build_YYYYMMDD_HHMMSS
        run_build_YYYYMMDD_HHMMSS_v2
        run_build_YYYYMMDD_HHMMSS_v3
        ...
    Return:
        YYYYMMDD_HHMMSS
    """
    match = re.fullmatch(r"run_build_(\d{8}_\d{6})(?:_v\d+)?", build_dir_name)
    if match is None:
        raise ValueError(f"Invalid build run directory name format: {build_dir_name}")
    return match.group(1)


def _find_latest_build_run(build_base: Path) -> Path:
    if not build_base.exists():
        raise FileNotFoundError(f"Build output folder not found: {build_base}")

    run_dirs = [
        p for p in build_base.iterdir()
        if p.is_dir() and p.name.startswith("run_build_")
    ]

    if not run_dirs:
        raise FileNotFoundError(f"No build run directories were found in: {build_base}")

    return max(run_dirs, key=lambda p: p.stat().st_mtime)


def _build_explore_run_dir(explore_base: Path, timestamp: str) -> Path:
    """
    Naming rule:
        run_explore_YYYYMMDD_HHMMSS
        run_explore_YYYYMMDD_HHMMSS_v2
        run_explore_YYYYMMDD_HHMMSS_v3
        ...
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


def _copy_if_exists(src: Path, dst: Path) -> bool:
    if src.exists():
        shutil.copy2(src, dst)
        return True
    return False


def _prepare_explore_inputs(build_run_dir: Path, explore_run_dir: Path) -> None:
    """
    Copy the minimum required files into the custom explore run directory.
    """
    print("[INFO] Preparing custom explore inputs...")

    model_src = build_run_dir / "model.mat"
    if not model_src.exists():
        raise FileNotFoundError(f"model.mat not found in build run: {model_src}")

    shutil.copy2(model_src, explore_run_dir / "model.mat")
    print(f"[OK] Copied: {model_src.name}")

    metadata_test_found = _copy_if_exists(
        build_run_dir / "metadata_test.csv",
        explore_run_dir / "metadata_test.csv",
    )
    metadata_found = _copy_if_exists(
        build_run_dir / "metadata.csv",
        explore_run_dir / "metadata.csv",
    )

    if metadata_test_found:
        print("[OK] Copied: metadata_test.csv")
    if metadata_found:
        print("[OK] Copied: metadata.csv")

    if not metadata_test_found and not metadata_found:
        raise FileNotFoundError(
            "No metadata_test.csv or metadata.csv found in the build run directory."
        )


# ======================================================================================
# MAIN LOGIC
# ======================================================================================

def run_own_explore_is(
    build_run_dir: Optional[Path] = None,
    build_base: Path = DEFAULT_BUILD_BASE,
    explore_base: Path = DEFAULT_EXPLORE_BASE,
    custom_explore_path: Path = DEFAULT_CUSTOM_EXPLORE_PATH,
) -> Path:
    """
    Run the custom MATLAB own_exploreIS.m over a build run directory.

    Parameters
    ----------
    build_run_dir : Optional[Path]
        Specific build run directory. If None, the latest one is used.
    build_base : Path
        Base directory containing build runs.
    explore_base : Path
        Base directory where explore runs will be created.
    custom_explore_path : Path
        Folder containing own_exploreIS.m.

    Returns
    -------
    Path
        Created explore run directory.
    """
    print("=" * 92)
    print("RUN OWN EXPLORE IS")
    print("=" * 92)

    if build_run_dir is None:
        build_run_dir = _find_latest_build_run(build_base)
        print(f"[INFO] No build run provided. Using latest: {build_run_dir}")
    else:
        build_run_dir = build_run_dir.resolve()
        print(f"[INFO] Using build run: {build_run_dir}")

    if not build_run_dir.exists():
        raise FileNotFoundError(f"Build run directory does not exist: {build_run_dir}")

    if not custom_explore_path.exists():
        raise FileNotFoundError(
            f"Custom explore path does not exist: {custom_explore_path}"
        )

    timestamp = _extract_build_timestamp(build_run_dir.name)
    explore_run_dir = _build_explore_run_dir(explore_base, timestamp)
    print(f"[INFO] Explore run directory: {explore_run_dir}")

    _prepare_explore_inputs(build_run_dir, explore_run_dir)

    print("[INFO] Starting MATLAB engine...")
    eng = matlab.engine.start_matlab()

    try:
        project_root_matlab = _to_matlab_path(PROJECT_ROOT)
        custom_explore_path_matlab = _to_matlab_path(custom_explore_path)
        explore_run_dir_matlab = _to_matlab_path(explore_run_dir)

        print("[INFO] Adding MATLAB paths...")
        eng.addpath(project_root_matlab, nargout=0)
        eng.addpath(custom_explore_path_matlab, nargout=0)

        print("[INFO] Running own_exploreIS...")
        eng.eval(f"own_exploreIS('{explore_run_dir_matlab}/');", nargout=0)

        print(f"[OK] own_exploreIS completed successfully.")
        print(f"[OK] Output folder: {explore_run_dir}")
        return explore_run_dir

    except Exception:
        print(f"[ERROR] own_exploreIS failed. Partial outputs may exist in: {explore_run_dir}")
        raise

    finally:
        print("[INFO] Closing MATLAB engine...")
        eng.quit()
        print("[OK] MATLAB engine closed.")


# ======================================================================================
# CLI
# ======================================================================================

def main() -> None:
    run_own_explore_is()


if __name__ == "__main__":
    main()