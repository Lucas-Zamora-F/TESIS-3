import math
import os
import sys


current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_script_path, "..", ".."))
sys.path.append(project_root)

from tools.wrappers_v2.lorads_wrapper import LoRADSWrapper


def fmt_float(x, fmt="{:.6e}", nan_text="NaN"):
    if x is None:
        return nan_text
    try:
        xf = float(x)
        if math.isnan(xf):
            return nan_text
        return fmt.format(xf)
    except Exception:
        return nan_text


def main():
    instances_to_test = [
        "arch0.dat-s",
        "arch2.dat-s",
        "arch4.dat-s",
        "arch8.dat-s",
    ]

    instance_dir = os.path.join(project_root, "data", "instances", "sdplib")
    config_file = os.path.join(project_root, "config", "solver_config.json")

    print("========================================")
    print("LORADS WRAPPER V2 TESTER")
    print("========================================")
    print(f"Targeting: {len(instances_to_test)} instances")

    solver = None

    try:
        solver = LoRADSWrapper(
            config_path=config_file,
            project_root=project_root,
        )

        results = []

        for idx, instance_name in enumerate(instances_to_test, start=1):
            instance_path = os.path.join(instance_dir, instance_name)
            print(f"\nRunning instance {idx}/{len(instances_to_test)}: {instance_name}")

            try:
                result = solver.solve(instance_path)
                results.append(result)
            except Exception as e:
                results.append(
                    {
                        "instance": instance_name,
                        "status": "FAILED",
                        "obj_val": float("nan"),
                        "gap": float("nan"),
                        "pinfeas": float("nan"),
                        "dinfeas": float("nan"),
                        "phi": float("nan"),
                        "optimal": False,
                        "iterations": 0,
                        "runtime": float("nan"),
                        "numerr": 0,
                        "pinf": float("nan"),
                        "dinf": float("nan"),
                        "feasratio": float("nan"),
                        "error": str(e),
                        "log_file": "",
                    }
                )

        print("\n========================================")
        print("FINAL RESULTS")
        print("========================================\n")

        header = (
            f"{'Instance':<12} "
            f"{'Status':<10} "
            f"{'Obj.Val':>14} "
            f"{'Gap':>12} "
            f"{'PInf':>12} "
            f"{'DInf':>12} "
            f"{'Phi':>12} "
            f"{'Optimal':>8} "
            f"{'Iter':>6} "
            f"{'Time(s)':>10} "
            f"{'NumErr':>7} "
            f"{'pinf':>12} "
            f"{'dinf':>12} "
            f"{'feasratio':>12}"
        )
        print(header)

        for res in results:
            print(
                f"{res['instance']:<12} "
                f"{res.get('status', 'UNK'):<10} "
                f"{fmt_float(res.get('obj_val')):>14} "
                f"{fmt_float(res.get('gap')):>12} "
                f"{fmt_float(res.get('pinfeas')):>12} "
                f"{fmt_float(res.get('dinfeas')):>12} "
                f"{fmt_float(res.get('phi')):>12} "
                f"{str(bool(res.get('optimal', False))):>8} "
                f"{int(res.get('iterations', 0)):>6} "
                f"{fmt_float(res.get('runtime'), fmt='{:.3f}', nan_text='NaN'):>10} "
                f"{int(res.get('numerr', 0)):>7} "
                f"{fmt_float(res.get('pinf')):>12} "
                f"{fmt_float(res.get('dinf')):>12} "
                f"{fmt_float(res.get('feasratio')):>12}"
            )

        print("\nLogs:")
        for res in results:
            print(f" - {res['instance']}: {res.get('log_file', '')}")
            if "error" in res and res["error"]:
                print(f"   ERROR: {res['error']}")

    except Exception as e:
        print(f"Critical error during execution: {e}")

    finally:
        if solver is not None:
            try:
                solver.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()