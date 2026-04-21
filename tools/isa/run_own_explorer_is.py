# ======================================================================================
# RUN OWN EXPLORE IS
# ======================================================================================

from __future__ import annotations

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


def _find_latest_build_run(build_base: Path) -> Path:
    if not build_base.exists():
        raise FileNotFoundError(f"Build output folder not found: {build_base}")

    if not (build_base / "model.mat").exists():
        raise FileNotFoundError(f"model.mat not found in build output folder: {build_base}")

    return build_base


def _build_explore_run_dir(explore_base: Path, timestamp: str | None = None) -> Path:
    """
    Clean matilda_out/explore and use it as the output directory.
    """
    resolved_output = explore_base.resolve()
    resolved_expected_parent = (PROJECT_ROOT / "matilda_out").resolve()
    if resolved_output.parent != resolved_expected_parent or resolved_output.name != "explore":
        raise ValueError(f"Refusing to clean unexpected explore output directory: {resolved_output}")

    explore_base.mkdir(parents=True, exist_ok=True)
    for child in explore_base.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    return explore_base


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

    explore_run_dir = _build_explore_run_dir(explore_base)
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
