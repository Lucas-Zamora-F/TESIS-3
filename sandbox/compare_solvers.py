from pathlib import Path

from sedumi_tests.benchmarck_sedumi_only_sdpa import solve_with_sedumi
from sdpt3_tests.benchmarck_sdpt3_only_sdpa import solve_with_sdpt3


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTANCE = PROJECT_ROOT / "data" / "instances" / "sdplib" / "arch0.dat-s"


def print_result(result: dict) -> None:
    print(f"\nSolver: {result['solver']}")
    print("-" * 40)

    for key, value in result.items():
        if key not in {"solver", "instance"}:
            print(f"{key:15}: {value}")


def main() -> None:
    sedumi_result = solve_with_sedumi(INSTANCE)
    sdpt3_result = solve_with_sdpt3(INSTANCE)

    print("\nRESULTADOS")
    print("=" * 50)

    print_result(sedumi_result)
    print_result(sdpt3_result)

    print("\nCOMPARACIÓN")
    print("=" * 50)
    print(f"{'metric':15} {'sedumi':15} {'sdpt3':15}")
    print("-" * 50)

    for key in ["solve_time_sec", "gap", "iter"]:
        a = sedumi_result.get(key)
        b = sdpt3_result.get(key)
        print(f"{key:15} {str(a):15} {str(b):15}")


if __name__ == "__main__":
    main()