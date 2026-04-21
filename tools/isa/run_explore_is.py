from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Optional

import matlab.engine

from analyze_explore_empty_space import find_empty_space_centers


# ======================================================================================
# DEFAULT PATHS
# ======================================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTANCE_SPACE_PATH = PROJECT_ROOT / "extern" / "InstanceSpace"
DEFAULT_BUILD_BASE = PROJECT_ROOT / "matilda_out" / "build"
DEFAULT_EXPLORE_BASE = PROJECT_ROOT / "matilda_out" / "explore"


# ======================================================================================
# HELPERS
# ======================================================================================

def _to_matlab_path(path: Path) -> str:
    """
    Convert a Windows path to a MATLAB-friendly path using forward slashes.
    """
    return str(path.resolve()).replace("\\", "/")


def _find_build_output_dir(build_base: Path) -> Path:
    """
    Return the current build output directory.
    """
    if not build_base.exists():
        raise FileNotFoundError(f"Build base directory not found: {build_base}")

    if not (build_base / "model.mat").exists():
        raise FileNotFoundError(f"model.mat not found in build output directory: {build_base}")

    return build_base


def _prepare_clean_explore_dir(explore_base: Path) -> Path:
    """
    Clean matilda_out/explore and use it as the explore output directory.
    """
    resolved_output = explore_base.resolve()
    resolved_expected_parent = (PROJECT_ROOT / "matilda_out").resolve()

    if resolved_output.parent != resolved_expected_parent or resolved_output.name != "explore":
        raise ValueError(
            "Refusing to clean an unexpected explore output directory: "
            f"{resolved_output}"
        )

    explore_base.mkdir(parents=True, exist_ok=True)

    for child in explore_base.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    return explore_base


def _prepare_explore_inputs(
    build_run_dir: Path,
    explore_run_dir: Path,
    metadata_test_path: Optional[Path] = None,
) -> None:
    """
    Prepare the input files required by exploreIS.

    Required by exploreIS:
    - model.mat
    - metadata_test.csv

    Source files taken from the selected build run by default:
    - model.mat
    - metadata.csv -> renamed to metadata_test.csv

    If metadata_test_path is provided, that file is copied as metadata_test.csv
    instead of the build metadata.csv.
    """
    src_model = build_run_dir / "model.mat"
    src_metadata = Path(metadata_test_path) if metadata_test_path else build_run_dir / "metadata.csv"
    src_options = build_run_dir / "options.json"

    if not src_model.exists():
        raise FileNotFoundError(f"model.mat not found in build run: {src_model}")

    if not src_metadata.exists():
        raise FileNotFoundError(f"metadata test CSV not found: {src_metadata}")

    dst_model = explore_run_dir / "model.mat"
    dst_metadata_test = explore_run_dir / "metadata_test.csv"

    shutil.copy2(src_model, dst_model)
    shutil.copy2(src_metadata, dst_metadata_test)

    print(f"[OK] Copied model.mat       -> {dst_model}")
    print(f"[OK] Copied metadata test   -> {dst_metadata_test}")

    # Not required by exploreIS itself, but useful for reproducibility/debugging
    if src_options.exists():
        dst_options = explore_run_dir / "options.json"
        shutil.copy2(src_options, dst_options)
        print(f"[OK] Copied options.json   -> {dst_options}")


def _write_explore_manifest(
    build_run_dir: Path,
    explore_run_dir: Path,
    metadata_test_path: Optional[Path] = None,
) -> None:
    """
    Write a minimal manifest JSON for debugging/reproducibility.
    """
    manifest = {
        "project_root": str(PROJECT_ROOT.resolve()),
        "build_run_dir": str(build_run_dir.resolve()),
        "explore_run_dir": str(explore_run_dir.resolve()),
        "metadata_test_source": (
            str(Path(metadata_test_path).resolve())
            if metadata_test_path
            else str((build_run_dir / "metadata.csv").resolve())
        ),
        "copied_model": str((explore_run_dir / "model.mat").resolve()),
        "copied_metadata_test": str((explore_run_dir / "metadata_test.csv").resolve()),
    }

    manifest_path = explore_run_dir / "explore_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)

    print(f"[OK] Wrote explore manifest -> {manifest_path}")


def _patch_model_mat_for_explore(
    eng: matlab.engine.MatlabEngine,
    model_mat_path: Path,
) -> None:
    """
    Patch the copied model.mat so it matches what the current exploreIS expects.

    Why this is still needed:
    - buildIS saves top-level structs, including:
        data, prelim, featsel, pilot, pythia, trace, opts, ...
    - exploreIS expects:
        opts, bound, norm, featsel, pilot, pythia, trace, ...

    Therefore:
    - bound <- prelim
    - norm  <- prelim

    Also:
    - If pythia.mu / pythia.sigma are missing, recover them from pilot.Z
    - If pythia.svm is missing but pythia.knn exists, alias svm <- knn
    """
    matlab_model_mat_path = _to_matlab_path(model_mat_path)

    print("[INFO] Patching copied model.mat for exploreIS compatibility...")

    eng.workspace["model_file"] = matlab_model_mat_path
    eng.eval(
        r"""
        S = load(model_file);

        fprintf('[MATLAB] Top-level fields before patch:\n');
        disp(fieldnames(S));

        if ~isfield(S, 'opts')
            error('Compatibility patch failed: model.mat does not contain top-level field ''opts''.');
        end

        if ~isfield(S, 'featsel') || ~isfield(S.featsel, 'idx')
            error('Compatibility patch failed: model.mat does not contain featsel.idx.');
        end

        if ~isfield(S, 'pilot')
            error('Compatibility patch failed: model.mat does not contain top-level field ''pilot''.');
        end

        if ~isfield(S, 'pythia')
            error('Compatibility patch failed: model.mat does not contain top-level field ''pythia''.');
        end

        if ~isfield(S, 'prelim')
            error('Compatibility patch failed: model.mat does not contain top-level field ''prelim''.');
        end

        % -----------------------------------------------------------------
        % Patch bound / norm from prelim if missing
        % -----------------------------------------------------------------
        if ~isfield(S, 'bound')
            required_bound_fields = {'hibound', 'lobound'};
            for k = 1:numel(required_bound_fields)
                if ~isfield(S.prelim, required_bound_fields{k})
                    error(['Compatibility patch failed: prelim is missing required bound field: ' required_bound_fields{k}]);
                end
            end
            bound = S.prelim;
            save(model_file, 'bound', '-append');
            fprintf('[MATLAB] Added top-level field: bound\n');
        end

        if ~isfield(S, 'norm')
            required_norm_fields = {'minX', 'lambdaX', 'muX', 'sigmaX', 'lambdaY', 'muY', 'sigmaY'};
            for k = 1:numel(required_norm_fields)
                if ~isfield(S.prelim, required_norm_fields{k})
                    error(['Compatibility patch failed: prelim is missing required norm field: ' required_norm_fields{k}]);
                end
            end
            norm = S.prelim;
            save(model_file, 'norm', '-append');
            fprintf('[MATLAB] Added top-level field: norm\n');
        end

        % Reload after append
        S = load(model_file);

        % -----------------------------------------------------------------
        % Patch pythia.mu / pythia.sigma if missing
        % -----------------------------------------------------------------
        if ~isfield(S.pythia, 'mu') || ~isfield(S.pythia, 'sigma')
            fprintf('[MATLAB] pythia.mu/sigma missing. Recomputing from pilot.Z.\n');

            if ~isfield(S.pilot, 'Z')
                error('Compatibility patch failed: pilot.Z not found in model.mat.');
            end

            [~, pythia_mu, pythia_sigma] = zscore(S.pilot.Z);
            pythia_sigma(pythia_sigma == 0) = 1;

            pythia = S.pythia;
            pythia.mu = pythia_mu;
            pythia.sigma = pythia_sigma;

            save(model_file, 'pythia', '-append');
            fprintf('[MATLAB] Patched pythia with mu and sigma.\n');
        end

        % -----------------------------------------------------------------
        % Patch pythia.svm if missing but pythia.knn exists
        % -----------------------------------------------------------------
        S = load(model_file);
        if ~isfield(S.pythia, 'svm') && isfield(S.pythia, 'knn')
            pythia = S.pythia;
            pythia.svm = pythia.knn;
            save(model_file, 'pythia', '-append');
            fprintf('[MATLAB] Patched pythia.svm from pythia.knn.\n');
        end

        fprintf('[MATLAB] Top-level fields after patch:\n');
        S_after = load(model_file);
        disp(fieldnames(S_after));
        """,
        nargout=0,
    )

    print("[OK] model.mat patched successfully")


# ======================================================================================
# MAIN EXECUTION FUNCTION
# ======================================================================================

def run_explore_is(
    build_run_dir: Optional[Path] = None,
    metadata_test_path: Optional[Path] = None,
    instance_space_path: Optional[Path] = None,
    build_base: Optional[Path] = None,
    explore_base: Optional[Path] = None,
    analyze_empty_space: bool = True,
    empty_space_top_k: int = 10,
    empty_space_grid_size: int = 80,
) -> Path:
    """
    Run InstanceSpace exploreIS using the current build output by default.

    Steps
    -----
    1. Use matilda_out/build as the build output directory unless one is provided.
    2. Clean matilda_out/explore and write outputs directly there.
    3. Copy:
        - model.mat
        - metadata_test_path -> metadata_test.csv, or metadata.csv -> metadata_test.csv
    4. Patch the copied model.mat for current exploreIS compatibility.
    5. Run exploreIS(rootdir).
    6. Optionally save empty-space target coordinates for future generation.

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
        build_run_dir = _find_build_output_dir(build_base)

    if not build_run_dir.exists():
        raise FileNotFoundError(f"Build run directory not found: {build_run_dir}")

    if not instance_space_path.exists():
        raise FileNotFoundError(
            f"InstanceSpace submodule not found at: {instance_space_path}"
        )

    exploreis_path = instance_space_path / "exploreIS.m"
    if not exploreis_path.exists():
        raise FileNotFoundError(f"exploreIS.m not found at: {exploreis_path}")

    explore_run_dir = _prepare_clean_explore_dir(explore_base)

    print("=" * 80)
    print("RUN EXPLOREIS / INSTANCE SPACE")
    print("=" * 80)
    print(f"[INFO] Project root         : {PROJECT_ROOT}")
    print(f"[INFO] InstanceSpace path   : {instance_space_path}")
    print(f"[INFO] Build base           : {build_base}")
    print(f"[INFO] Selected build run   : {build_run_dir}")
    print(f"[INFO] Metadata test source : {metadata_test_path or build_run_dir / 'metadata.csv'}")
    print(f"[INFO] Explore base         : {explore_base}")
    print(f"[INFO] Explore run dir      : {explore_run_dir}")

    print("\n[INFO] Preparing exploreIS input files...")
    _prepare_explore_inputs(build_run_dir, explore_run_dir, metadata_test_path)
    _write_explore_manifest(build_run_dir, explore_run_dir, metadata_test_path)

    eng = None
    try:
        print("\n[INFO] Starting MATLAB engine...")
        eng = matlab.engine.start_matlab()

        matlab_instance_space_path = _to_matlab_path(instance_space_path)
        matlab_explore_run_dir = _to_matlab_path(explore_run_dir)
        copied_model_mat = explore_run_dir / "model.mat"

        print("[INFO] Adding InstanceSpace root to MATLAB path...")
        eng.addpath(matlab_instance_space_path, nargout=0)

        print("[INFO] Adding InstanceSpace subfolders recursively with genpath...")
        eng.eval(f"addpath(genpath('{matlab_instance_space_path}'));", nargout=0)

        _patch_model_mat_for_explore(eng, copied_model_mat)

        print("[INFO] Running exploreIS(rootdir)...")
        eng.eval(f"exploreIS('{matlab_explore_run_dir}/');", nargout=0)

        print("[OK] exploreIS finished successfully")
        print(f"[OK] Outputs saved in: {explore_run_dir}")

        if analyze_empty_space:
            print("[INFO] Detecting empty-space target coordinates...")
            find_empty_space_centers(
                explore_run_dir=explore_run_dir,
                grid_size=empty_space_grid_size,
                top_k=empty_space_top_k,
            )

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

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run InstanceSpace exploreIS using a build model and metadata_test.csv."
    )
    parser.add_argument(
        "--build-run-dir",
        type=Path,
        help="Specific build output directory. Defaults to matilda_out/build.",
    )
    parser.add_argument(
        "--metadata-test-path",
        type=Path,
        help="CSV to copy as metadata_test.csv. Defaults to selected build metadata.csv.",
    )
    parser.add_argument(
        "--instance-space-path",
        type=Path,
        default=DEFAULT_INSTANCE_SPACE_PATH,
        help="Path to the InstanceSpace MATLAB folder.",
    )
    parser.add_argument(
        "--build-base",
        type=Path,
        default=DEFAULT_BUILD_BASE,
        help="Current build output folder.",
    )
    parser.add_argument(
        "--explore-base",
        type=Path,
        default=DEFAULT_EXPLORE_BASE,
        help="Current explore output folder.",
    )
    parser.add_argument(
        "--skip-empty-space-analysis",
        action="store_true",
        help="Do not generate empty_space_targets.csv/json after exploreIS.",
    )
    parser.add_argument(
        "--empty-space-top-k",
        type=int,
        default=10,
        help="Number of empty-space centers to save after exploreIS.",
    )
    parser.add_argument(
        "--empty-space-grid-size",
        type=int,
        default=80,
        help="Grid resolution per axis for empty-space detection.",
    )
    return parser.parse_args()


def main() -> None:
    """
    Standalone entry point.
    """
    args = _parse_args()
    run_dir = run_explore_is(
        build_run_dir=args.build_run_dir,
        metadata_test_path=args.metadata_test_path,
        instance_space_path=args.instance_space_path,
        build_base=args.build_base,
        explore_base=args.explore_base,
        analyze_empty_space=not args.skip_empty_space_analysis,
        empty_space_top_k=args.empty_space_top_k,
        empty_space_grid_size=args.empty_space_grid_size,
    )

    print("\n" + "=" * 80)
    print("EXPLOREIS FINISHED")
    print("=" * 80)
    print(f"[INFO] Run output directory: {run_dir}")


if __name__ == "__main__":
    main()
