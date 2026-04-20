from __future__ import annotations

import importlib
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


# ============================================================
# CONFIG
# ============================================================

REQUIRED_PACKAGES = [
    "pandas",
    "numpy",
    "PySide6",
]

ENABLE_COOLDOWN = 0
COOLDOWN_SECONDS = 1.0


# ============================================================
# LOGGER
# ============================================================

def create_logger(log_callback: Optional[Callable[[str], None]] = None):
    log_dir = Path(__file__).parent
    log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"environment_setup_{timestamp}.txt"

    def log(msg: str) -> None:
        # consola
        print(msg)

        # UI
        if log_callback:
            log_callback(msg)

        # archivo
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

    return log


# ============================================================
# HELPERS
# ============================================================

def _cooldown() -> None:
    if ENABLE_COOLDOWN == 1:
        time.sleep(COOLDOWN_SECONDS)


def is_installed(package: str) -> bool:
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False


def is_matlab_engine_installed() -> bool:
    try:
        import matlab.engine
        return True
    except ImportError:
        return False


def install_pip_package(package: str, log) -> None:
    log(f"[INSTALLING] {package}...")
    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        package,
    ])
    log(f"[DONE] {package}")


# ============================================================
# MATLAB ENGINE INSTALL
# ============================================================

def try_install_matlab_engine(log) -> bool:
    candidate_paths = [
        Path(r"C:\Program Files\MATLAB\R2025b\extern\engines\python"),
        Path(r"C:\Program Files\MATLAB\R2024b\extern\engines\python"),
        Path(r"C:\Program Files\MATLAB\R2024a\extern\engines\python"),
        Path(r"C:\Program Files\MATLAB\R2023b\extern\engines\python"),
        Path(r"C:\Program Files\MATLAB\R2023a\extern\engines\python"),
        Path(r"C:\Program Files\MATLAB\R2022b\extern\engines\python"),
        Path(r"C:\Program Files\MATLAB\R2022a\extern\engines\python"),
    ]

    for engine_path in candidate_paths:
        log(f"[CHECK] MATLAB engine path: {engine_path}")
        _cooldown()

        if engine_path.exists():
            log(f"[FOUND] MATLAB engine path exists")
            log(f"[INSTALLING] matlab.engine from {engine_path}")
            _cooldown()

            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "."],
                    cwd=str(engine_path),
                )

                log("[DONE] matlab.engine installed")
                return True

            except subprocess.CalledProcessError as exc:
                log(f"[ERROR] Failed installing matlab.engine: {exc}")

        else:
            log("[SKIP] Path not found")

        _cooldown()

    return False


# ============================================================
# MAIN ENTRY
# ============================================================

def ensure_environment(log_callback: Optional[Callable[[str], None]] = None) -> None:
    log = create_logger(log_callback)

    log("=" * 60)
    log("ENVIRONMENT SETUP")
    log("=" * 60)

    log(f"[INFO] Python executable: {sys.executable}")
    _cooldown()

    # ------------------------------------------------------------
    # PYTHON PACKAGES
    # ------------------------------------------------------------
    log("[INFO] Checking Python packages...")
    _cooldown()

    for pkg in REQUIRED_PACKAGES:
        log(f"[CHECK] {pkg}")
        _cooldown()

        if is_installed(pkg):
            log(f"[OK] {pkg}")
        else:
            install_pip_package(pkg, log)

        _cooldown()

    # ------------------------------------------------------------
    # MATLAB ENGINE
    # ------------------------------------------------------------
    log("[INFO] Checking MATLAB Engine...")
    _cooldown()

    if is_matlab_engine_installed():
        log("[OK] matlab.engine")
    else:
        log("[MISSING] matlab.engine")
        log("[INFO] Attempting automatic installation...")
        _cooldown()

        installed = try_install_matlab_engine(log)

        if installed:
            log("[DONE] matlab.engine")
        else:
            log("[WARNING] matlab.engine could not be installed automatically.")
            log("[WARNING] Install manually from MATLAB/extern/engines/python")

    log("=" * 60)
    log("ENVIRONMENT CHECK COMPLETE")
    log("=" * 60)