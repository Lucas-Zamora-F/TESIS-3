from __future__ import annotations

import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main.build_features_table import build_features_table


def main() -> None:
    instances = [
        PROJECT_ROOT / "data/instances/sdplib/arch0.dat-s",
        PROJECT_ROOT / "data/instances/sdplib/arch2.dat-s",
        PROJECT_ROOT / "data/instances/sdplib/arch4.dat-s",
        PROJECT_ROOT / "data/instances/sdplib/arch8.dat-s",
    ]

    config_path = PROJECT_ROOT / "config/features_config.json"

    print("=" * 80)
    print("BUILD FEATURES TABLE TESTER")
    print("=" * 80)
    print(f"[INFO] PROJECT_ROOT: {PROJECT_ROOT}")
    print("[INFO] Instancias objetivo:")
    for instance in instances:
        print(f"  - {instance}")
    print(f"[INFO] Config de features: {config_path}")
    print()

    if not config_path.exists():
        raise FileNotFoundError(
            f"No existe el archivo de configuración de features: {config_path}"
        )

    df = build_features_table(
        instances=instances,
        config_path=config_path,
    )

    print("=" * 80)
    print("DATAFRAME RESULTANTE")
    print("=" * 80)

    if df.empty:
        print("[INFO] El dataframe resultante está vacío.")
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()