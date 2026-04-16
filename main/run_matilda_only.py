from __future__ import annotations

import sys
from pathlib import Path


# ==========================================================
# REPOSITORY ROOT SETUP
# ==========================================================
REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ==========================================================
# IMPORTS
# ==========================================================
from tools.isa.run_matilda import run_matilda
from tools.logging.universal_logger import (
    setup_universal_logger,
    log_event,
    log_exception,
)


# ==========================================================
# MAIN EXECUTION
# ==========================================================
def main() -> None:
    setup_universal_logger()

    metadata_path = REPO_ROOT / "ISA metadata" / "metadata.csv"

    print("=" * 80)
    print("RUN MATILDA ONLY")
    print("=" * 80)
    print(f"[INFO] Expected metadata path: {metadata_path}")

    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {metadata_path}\n"
            "Generate it first before running this script."
        )

    try:
        log_event(
            "INFO",
            "run_matilda_only",
            "Starting MATILDA-only execution.",
            extra={
                "metadata_path": str(metadata_path),
            },
        )

        print("[INFO] Running MATILDA using existing metadata.csv ...")
        matilda_run_dir = run_matilda()

        print(f"[OK] MATILDA completed successfully.")
        print(f"[OK] Output directory: {matilda_run_dir}")

        log_event(
            "INFO",
            "run_matilda_only",
            "MATILDA-only execution completed successfully.",
            extra={
                "metadata_path": str(metadata_path),
                "matilda_run_dir": str(matilda_run_dir),
            },
        )

    except Exception as exc:
        log_exception(
            "run_matilda_only",
            "MATILDA-only execution failed.",
            exc,
        )
        raise


if __name__ == "__main__":
    main()