from __future__ import annotations

import json
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
# HELPERS
# ======================================================================================

def _to_matlab_path(path: Path) -> str:
    """
    Convert a Windows path to a MATLAB-friendly path using forward slashes.
    """
    return str(path.resolve()).replace("\\", "/")


def _extract_build_timestamp(build_run_name: str) -> str:
    """
    Extract the timestamp from a build run folder name.

    Expected formats:
        run_build_YYYYMMDD_HHMMSS
        run_build_YYYYMMDD_HHMMSS_v2
        run_build_YYYYMMDD_HHMMSS_v3
        ...

    Returns
    -------
    str
        The extracted timestamp: YYYYMMDD_HHMMSS
    """
    match = re.match(r"^run_build_(\d{8}_\d{6})(?:_v\d+)?$", build_run_name)
    if not match:
        raise ValueError(
            f"Could not extract timestamp from build run folder name: {build_run_name}"
        )
    return match.group(1)


def _find_latest_build_run(build_base: Path) -> Path:
    """
    Find the most recent build run directory.
    """
    if not build_base.exists():
        raise FileNotFoundError(f"Build base directory not found: {build_base}")

    candidates = [
        p
        for p in build_base.iterdir()
        if p.is_dir() and re.match(r"^run_build_\d{8}_\d{6}(?:_v\d+)?$", p.name)
    ]

    if not candidates:
        raise FileNotFoundError(f"No build run directories found in: {build_base}")

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _build_explore_run_dir(explore_base: Path, timestamp: str) -> Path:
    """
    Create a new explore run directory using the build timestamp.
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
    - metadata.csv -> renamed to metadata_test.csv
    """
    src_model = build_run_dir / "model.mat"
    src_metadata = build_run_dir / "metadata.csv"
    src_options = build_run_dir / "options.json"

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

    # Not required by exploreIS itself, but useful for reproducibility/debugging
    if src_options.exists():
        dst_options = explore_run_dir / "options.json"
        shutil.copy2(src_options, dst_options)
        print(f"[OK] Copied options.json   -> {dst_options}")


def _write_explore_manifest(build_run_dir: Path, explore_run_dir: Path) -> None:
    """
    Write a minimal manifest JSON for debugging/reproducibility.
    """
    manifest = {
        "project_root": str(PROJECT_ROOT.resolve()),
        "build_run_dir": str(build_run_dir.resolve()),
        "explore_run_dir": str(explore_run_dir.resolve()),
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
    instance_space_path: Optional[Path] = None,
    build_base: Optional[Path] = None,
    explore_base: Optional[Path] = None,
) -> Path:
    """
    Run InstanceSpace exploreIS using the latest build run by default.

    Steps
    -----
    1. Locate the latest build run in matilda_out/build (unless one is provided).
    2. Create a new explore run directory in matilda_out/explore with the same timestamp.
    3. Copy:
        - model.mat
        - metadata.csv -> metadata_test.csv
    4. Patch the copied model.mat for current exploreIS compatibility.
    5. Run exploreIS(rootdir).

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

    exploreis_path = instance_space_path / "exploreIS.m"
    if not exploreis_path.exists():
        raise FileNotFoundError(f"exploreIS.m not found at: {exploreis_path}")

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
    _write_explore_manifest(build_run_dir, explore_run_dir)

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