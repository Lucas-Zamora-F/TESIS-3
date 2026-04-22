#!/usr/bin/env python3
"""
tools/installation/setup_env.py

Prepares the general environment for the repository.

Responsibilities:
- Verify the base repo layout.
- Sync and download all submodules declared in .gitmodules.
- Verify and install required Python dependencies.
- Start the MATLAB Engine.
- Verify required MATLAB products.
- Add relevant project folders to the MATLAB path.
- Run MATLAB solver installers supported by the repo.
- Verify that the MATLAB/solver stack is fully operational.

This script does NOT:
- read solver_config.json
- decide which solver is active
- configure run parameters
- execute experiments

Its sole purpose is to leave the environment ready to run the repository.
"""

from __future__ import annotations

import configparser
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


# =============================================================================
# Base configuration
# =============================================================================

PYTHON_DEPENDENCIES: Dict[str, str] = {
    "pandas": "pandas",
    "matlabengine": "matlab.engine",
}

# MATLAB products declared as required by the repo.
REQUIRED_MATLAB_PRODUCTS: List[str] = [
    "MATLAB",
    "Statistics and Machine Learning Toolbox",
    "Optimization Toolbox",
    "Signal Processing Toolbox",
    "Communications Toolbox",
]

# MATLAB paths relevant to the current repo code.
MATLAB_REPO_PATHS: List[Path] = [
    Path("tools"),
    Path("tools/matlab"),
    Path("tools/matlab/sdpt3"),
    Path("tools/matlab/sedumi"),
    Path("tools/runners"),
    Path("tools/wrappers_v2"),
    Path("extern/sdpt3"),
    Path("extern/sedumi"),
]

# Critical function checks for the MATLAB/solver stack supported by the repo.
MATLAB_FUNCTION_CHECKS: List[Tuple[str, str]] = [
    ("SDPT3 entrypoint", "sqlp"),
    ("SDPT3 parameters", "sqlparameters"),
    ("SDPT3 reader", "read_sdpa"),
    ("SDPT3 mex", "mexsvec"),
    ("SeDuMi entrypoint", "sedumi"),
    ("SeDuMi reader", "fromsdpa"),
    ("SeDuMi cone helper", "eigK"),
    ("Repo helper", "run_sdpt3_instance"),
    ("Repo helper", "run_sedumi_instance"),
]


# =============================================================================
# Console utilities
# =============================================================================

def print_header(title: str) -> None:
    line = "=" * 88
    print(f"\n{line}\n{title}\n{line}")


def print_info(message: str) -> None:
    print(f"[INFO] {message}")


def print_ok(message: str) -> None:
    print(f"[ OK ] {message}")


def print_warn(message: str) -> None:
    print(f"[WARN] {message}")


def print_fail(message: str) -> None:
    print(f"[FAIL] {message}")


def run_command(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    print_info("Running: " + " ".join(cmd))
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        check=check,
    )


# =============================================================================
# Repo / structure
# =============================================================================

def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_repo_layout(repo_root: Path) -> None:
    required_paths = [
        repo_root / ".gitmodules",
        repo_root / "tools",
        repo_root / "config",
        repo_root / "tools" / "installation",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(
            "Repository layout does not look valid. Missing paths:\n- "
            + "\n- ".join(missing)
        )


def read_gitmodules_paths(repo_root: Path) -> List[Path]:
    gitmodules_path = repo_root / ".gitmodules"
    if not gitmodules_path.exists():
        return []

    parser = configparser.ConfigParser()
    parser.read(gitmodules_path, encoding="utf-8")

    submodule_paths: List[Path] = []
    for section in parser.sections():
        if parser.has_option(section, "path"):
            raw_path = parser.get(section, "path").strip()
            if raw_path:
                submodule_paths.append(Path(raw_path))

    return submodule_paths


# =============================================================================
# Git / submodules
# =============================================================================

def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("'git' not found in PATH. Install it before continuing.")


def sync_and_update_submodules(repo_root: Path) -> List[Path]:
    print_header("1. Git submodules")
    ensure_git_available()

    submodule_paths = read_gitmodules_paths(repo_root)
    if not submodule_paths:
        print_warn("No submodules found in .gitmodules.")
        return []

    run_command(["git", "submodule", "sync", "--recursive"], cwd=repo_root)
    run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=repo_root)

    missing = [str(repo_root / rel_path) for rel_path in submodule_paths if not (repo_root / rel_path).exists()]
    if missing:
        raise RuntimeError(
            "After updating submodules, these paths are still missing:\n- "
            + "\n- ".join(missing)
        )

    for rel_path in submodule_paths:
        print_ok(f"Submodule present: {rel_path}")

    return submodule_paths


# =============================================================================
# Python
# =============================================================================

def module_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def install_python_package(package_name: str) -> None:
    run_command([sys.executable, "-m", "pip", "install", package_name])


def ensure_python_dependencies() -> None:
    print_header("2. Python dependencies")

    missing_packages = [
        package_name
        for package_name, module_name in PYTHON_DEPENDENCIES.items()
        if not module_exists(module_name)
    ]

    if not missing_packages:
        for package_name in PYTHON_DEPENDENCIES:
            print_ok(f"Available: {package_name}")
        return

    for package_name in missing_packages:
        print_warn(f"Missing {package_name}. Attempting install...")
        install_python_package(package_name)

    still_missing = [
        package_name
        for package_name, module_name in PYTHON_DEPENDENCIES.items()
        if not module_exists(module_name)
    ]
    if still_missing:
        raise RuntimeError(
            "Could not install these Python dependencies:\n- "
            + "\n- ".join(still_missing)
        )

    for package_name in PYTHON_DEPENDENCIES:
        print_ok(f"Available: {package_name}")


# =============================================================================
# MATLAB helpers
# =============================================================================

def import_matlab_engine():
    try:
        import matlab.engine  # type: ignore
        return matlab.engine
    except Exception as exc:
        raise RuntimeError(
            "Could not import matlab.engine. "
            "Verify that MATLAB is installed and that the 'matlabengine' package "
            "is compatible with your Python version."
        ) from exc


def matlab_exist(eng, name: str, kind: str = "file") -> int:
    return int(eng.exist(name, kind))


def matlab_which(eng, name: str) -> str:
    try:
        result = eng.which(name, nargout=1)
        return str(result)
    except Exception:
        return ""


def get_installed_matlab_products(eng) -> List[str]:
    values = eng.eval("{ver().Name}", nargout=1)
    return [str(value) for value in values]


def ensure_required_matlab_products(eng) -> None:
    print_header("3. MATLAB products")

    installed_products = get_installed_matlab_products(eng)
    for product in installed_products:
        print(f" - {product}")

    missing = [product for product in REQUIRED_MATLAB_PRODUCTS if product not in installed_products]
    if missing:
        raise RuntimeError(
            "Missing required MATLAB products:\n- "
            + "\n- ".join(missing)
            + "\n\nInstall them from MATLAB/MathWorks and re-run this script."
        )

    print_ok("MATLAB products verified.")


def reset_and_add_repo_paths(eng, repo_root: Path) -> None:
    print_header("4. Repo paths in MATLAB")

    eng.restoredefaultpath(nargout=0)
    eng.rehash(nargout=0)

    for rel_path in MATLAB_REPO_PATHS:
        abs_path = repo_root / rel_path
        if abs_path.exists():
            matlab_path = abs_path.as_posix().replace("'", "''")
            eng.eval(f"addpath(genpath('{matlab_path}'));", nargout=0)
            print_ok(f"Path added: {rel_path}")
        else:
            print_warn(f"Path does not exist, skipping: {rel_path}")

    eng.rehash(nargout=0)
    print_ok("Repo paths added to MATLAB.")


def configure_mex_compilers(eng) -> None:
    print_header("5. MEX configuration")

    try:
        eng.eval("mex -setup C", nargout=0)
        print_ok("MEX C compiler configured.")
    except Exception as exc:
        print_warn(f"Could not configure MEX C automatically: {exc}")

    try:
        eng.eval("mex -setup C++", nargout=0)
        print_ok("MEX C++ compiler configured.")
    except Exception as exc:
        print_warn(f"Could not configure MEX C++ automatically: {exc}")


# =============================================================================
# MATLAB solver preparation
# =============================================================================

def run_matlab_installer_if_available(
    eng,
    working_dir: Path,
    script_name: str,
    *,
    allow_rebuild: bool = False,
) -> None:
    if not working_dir.exists():
        print_warn(f"Directory {working_dir} does not exist. Skipping {script_name}.")
        return

    old_dir = eng.pwd(nargout=1)
    try:
        eng.cd(working_dir.as_posix(), nargout=0)

        if matlab_exist(eng, script_name, "file") == 0:
            raise RuntimeError(f"MATLAB cannot find '{script_name}' in {working_dir}")

        try:
            eng.eval(script_name, nargout=0)
            print_ok(f"{script_name} executed successfully.")
        except Exception as exc:
            if allow_rebuild:
                print_warn(f"{script_name} failed. Attempting rebuild...")
                eng.eval(f"{script_name} -rebuild", nargout=0)
                print_ok(f"{script_name} -rebuild executed successfully.")
            else:
                raise RuntimeError(f"{script_name} failed: {exc}") from exc
    finally:
        eng.cd(old_dir, nargout=0)


def prepare_supported_solvers(eng, repo_root: Path) -> None:
    print_header("6. Solver preparation")

    sdpt3_dir = repo_root / "extern" / "sdpt3"
    sedumi_dir = repo_root / "extern" / "sedumi"

    run_matlab_installer_if_available(
        eng,
        sdpt3_dir,
        "install_sdpt3",
        allow_rebuild=True,
    )
    run_matlab_installer_if_available(
        eng,
        sedumi_dir,
        "install_sedumi",
        allow_rebuild=False,
    )

    # Some installers alter the MATLAB path; reset to ensure consistency.
    reset_and_add_repo_paths(eng, repo_root)


# =============================================================================
# Final verification
# =============================================================================

def verify_matlab_solver_stack(eng) -> None:
    print_header("7. Final MATLAB / solver verification")

    failures: List[str] = []

    for label, func_name in MATLAB_FUNCTION_CHECKS:
        exists = matlab_exist(eng, func_name, "file")
        if exists:
            location = matlab_which(eng, func_name)
            print_ok(f"{label}: {func_name} -> {location}")
        else:
            print_fail(f"{label}: MATLAB cannot find '{func_name}'")
            failures.append(f"{label}: {func_name}")

    if failures:
        raise RuntimeError(
            "Setup completed, but critical functions are still missing:\n- "
            + "\n- ".join(failures)
            + "\n\nThe environment is not ready to run the repository."
        )

    print_ok("MATLAB / solver verification passed.")


def smoke_test_repo_helpers(repo_root: Path, eng) -> None:
    print_header("8. Repo helper smoke test")

    required_helpers = [
        repo_root / "tools" / "matlab" / "sdpt3" / "run_sdpt3_instance.m",
        repo_root / "tools" / "matlab" / "sedumi" / "run_sedumi_instance.m",
    ]

    missing_files = [str(path) for path in required_helpers if not path.exists()]
    if missing_files:
        raise RuntimeError(
            "Expected repo MATLAB helpers are missing:\n- "
            + "\n- ".join(missing_files)
        )

    if matlab_exist(eng, "run_sdpt3_instance", "file") == 0:
        raise RuntimeError("MATLAB cannot find run_sdpt3_instance after setup.")
    if matlab_exist(eng, "run_sedumi_instance", "file") == 0:
        raise RuntimeError("MATLAB cannot find run_sedumi_instance after setup.")

    print_ok("Repo MATLAB helpers visible and ready.")


def summarize(repo_root: Path, submodule_paths: List[Path]) -> None:
    print_header("9. Summary")
    print_ok(f"Repo root: {repo_root}")

    if submodule_paths:
        print_ok("Submodules prepared:")
        for rel_path in submodule_paths:
            print(f"     - {rel_path}")
    else:
        print_warn("No submodules declared in .gitmodules.")

    print_ok("Python dependencies: OK")
    print_ok("MATLAB products: OK")
    print_ok("Repo MATLAB paths: OK")
    print_ok("SDPT3: OK")
    print_ok("SeDuMi: OK")
    print_ok("Repository environment ready.")


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    repo_root = repo_root_from_script()

    print_header("REPOSITORY ENVIRONMENT SETUP")
    print_info(f"Detected root: {repo_root}")

    ensure_repo_layout(repo_root)
    submodule_paths = sync_and_update_submodules(repo_root)
    ensure_python_dependencies()

    matlab_engine = import_matlab_engine()

    print_header("Starting MATLAB Engine")
    eng = matlab_engine.start_matlab()
    try:
        ensure_required_matlab_products(eng)
        reset_and_add_repo_paths(eng, repo_root)
        configure_mex_compilers(eng)
        prepare_supported_solvers(eng, repo_root)
        verify_matlab_solver_stack(eng)
        smoke_test_repo_helpers(repo_root, eng)
    finally:
        try:
            eng.quit()
        except Exception:
            pass

    summarize(repo_root, submodule_paths)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print_header("SETUP FAILED")
        print(str(exc))
        raise
