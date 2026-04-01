from pathlib import Path
import sys

# =========================================
# Ajuste de path para importar desde main/
# =========================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from main.build_solver_runtime_table import build_solver_runtime_table


def main():
    # =========================================
    # Instancias de prueba (SDPLIB)
    # =========================================
    instances = [
        PROJECT_ROOT / "data/instances/sdplib/arch0.dat-s",
        PROJECT_ROOT / "data/instances/sdplib/arch2.dat-s",
        PROJECT_ROOT / "data/instances/sdplib/arch4.dat-s",
        PROJECT_ROOT / "data/instances/sdplib/arch8.dat-s",
    ]

    # =========================================
    # Ejecutar función principal
    # =========================================
    df = build_solver_runtime_table(instances)

    # =========================================
    # Mostrar resultado
    # =========================================
    print("\n========================================")
    print(" SOLVER RUNTIME TABLE")
    print("========================================\n")

    print(df.to_string(index=False))

    print("\n========================================\n")


if __name__ == "__main__":
    main()