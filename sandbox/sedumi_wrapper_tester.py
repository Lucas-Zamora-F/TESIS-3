import os
import sys

# Ajustar path del proyecto para importar el wrapper
current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_script_path, ".."))
sys.path.insert(0, project_root)

from tools.wrappers.sedumi_wrapper import run_benchmark


def main():
    # Instancias de prueba
    selected_instances = [
        "arch0.dat-s",
        "arch2.dat-s",
        "arch4.dat-s",
        "arch8.dat-s",
    ]

    print(f"Targeting: {len(selected_instances)} instances")

    instance_folder = os.path.join(project_root, "data", "instances", "sdplib")
    config_path = os.path.join(project_root, "metadata", "solver_config.json")

    try:
        results = run_benchmark(
            instance_folder=instance_folder,
            config_path=config_path,
            filter_list=selected_instances,
        )

        if not results:
            print("No se obtuvieron resultados.")
            return

        print("\n" + "=" * 150)
        print("RESULTADOS SEDUMI")
        print("=" * 150)
        print(
            f"{'Instance':<15} {'Status':<8} {'Obj.Val':<14} {'Gap':<12} "
            f"{'PInf':<12} {'DInf':<12} {'Phi':<12} {'Optimal':<8} "
            f"{'Iter':<8} {'Time(s)':<10} {'NumErr':<8} {'pinf':<8} "
            f"{'dinf':<8} {'feasratio':<12}"
        )
        print("-" * 150)

        for res in results:
            instance = str(res.get("instance", "N/A"))
            status = format_int(res.get("status"))
            obj_val = format_float(res.get("obj_val"))
            gap = format_float(res.get("gap"))
            pinfeas = format_float(res.get("pinfeas"))
            dinfeas = format_float(res.get("dinfeas"))
            phi = format_float(res.get("phi"))
            is_optimal = format_bool(res.get("is_optimal"))
            iterations = format_int(res.get("iterations"))
            runtime = format_float(res.get("runtime"))
            numerr = format_int(res.get("numerr"))
            pinf_flag = format_int(res.get("pinf_flag"))
            dinf_flag = format_int(res.get("dinf_flag"))
            feasratio = format_float(res.get("feasratio"))

            print(
                f"{instance:<15} {status:<8} {obj_val:<14} {gap:<12} "
                f"{pinfeas:<12} {dinfeas:<12} {phi:<12} {is_optimal:<8} "
                f"{iterations:<8} {runtime:<10} {numerr:<8} {pinf_flag:<8} "
                f"{dinf_flag:<8} {feasratio:<12}"
            )

        print("-" * 150)

        optimal_count = sum(1 for r in results if safe_float(r.get("is_optimal")) == 1.0)
        total_count = len(results)

        print(f"\nInstancias resueltas: {total_count}")
        print(f"Óptimas según benchmark homogéneo: {optimal_count}/{total_count}")

    except Exception as e:
        print(f"Critical error during execution: {e}")


def format_float(value, precision=3):
    try:
        v = float(value)
        return f"{v:.{precision}e}"
    except (TypeError, ValueError):
        return "N/A"


def format_int(value):
    try:
        if value is None:
            return "N/A"
        return str(int(float(value)))
    except (TypeError, ValueError):
        return "N/A"


def format_bool(value):
    try:
        return "yes" if float(value) == 1.0 else "no"
    except (TypeError, ValueError):
        return "N/A"


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


if __name__ == "__main__":
    main()