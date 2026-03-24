import os
import sys
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tools.wrappers.lorads_wrapper import LoRaDSWrapper


def fmt(x, f="{:.6e}"):
    try:
        x = float(x)
        if math.isnan(x):
            return "NaN"
        return f.format(x)
    except Exception:
        return "NaN"


def run_wrapper_test():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(project_root, "metadata", "solver_config.json")

    instances = [
        "arch0.dat-s",
        "arch2.dat-s",
        "arch4.dat-s",
        "arch8.dat-s",
    ]

    instance_dir = os.path.join(project_root, "data", "instances", "sdplib")

    solver = LoRaDSWrapper(config_path=config_path)

    print("========================================")
    print("LoRADS WRAPPER TESTER")
    print("========================================")
    print(f"Targeting: {len(instances)} instances")

    results = []
    for k, inst in enumerate(instances, start=1):
        path = os.path.join(instance_dir, inst)
        print(f"\nRunning instance {k}/{len(instances)}: {inst}")
        try:
            res = solver.solve(path, force_rebuild=(k == 1))
            results.append(res)
        except Exception as e:
            results.append(
                {
                    "instance": inst,
                    "status": "FAILED",
                    "objective": float("nan"),
                    "dual_objective": float("nan"),
                    "gap": float("nan"),
                    "pinf": float("nan"),
                    "dinf": float("nan"),
                    "phi": float("nan"),
                    "optimal": False,
                    "iterations": 0,
                    "runtime": float("nan"),
                    "returncode": -999,
                    "log_file": "",
                    "error": str(e),
                }
            )

    print("\n========================================")
    print("FINAL RESULTS")
    print("========================================\n")

    header = (
        f"{'Instance':<12} "
        f"{'Status':<12} "
        f"{'Obj.Val':>14} "
        f"{'Dual.Obj':>14} "
        f"{'Gap':>12} "
        f"{'PInf':>12} "
        f"{'DInf':>12} "
        f"{'Phi':>12} "
        f"{'Optimal':>8} "
        f"{'Iter':>6} "
        f"{'Time(s)':>10}"
    )
    print(header)

    for r in results:
        print(
            f"{r['instance']:<12} "
            f"{r.get('status', 'UNK'):<12} "
            f"{fmt(r.get('objective')):>14} "
            f"{fmt(r.get('dual_objective')):>14} "
            f"{fmt(r.get('gap')):>12} "
            f"{fmt(r.get('pinf')):>12} "
            f"{fmt(r.get('dinf')):>12} "
            f"{fmt(r.get('phi')):>12} "
            f"{str(bool(r.get('optimal', False))):>8} "
            f"{int(r.get('iterations', 0)):>6} "
            f"{fmt(r.get('runtime'), '{:.3f}'):>10}"
        )

    print("\nLogs:")
    for r in results:
        print(f" - {r['instance']}: {r.get('log_file', '')}")
        if "error" in r:
            print(f"   ERROR: {r['error']}")


if __name__ == "__main__":
    run_wrapper_test()