from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEDUMI_PATH = PROJECT_ROOT / "extern" / "sedumi"

TIMEOUT_SEC = 300  # 5 minutos


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _matlab_scalar(eng, expr: str):
    value = eng.eval(expr, nargout=1)

    if isinstance(value, (int, float, str, bool)):
        return value

    try:
        if hasattr(value, "__len__") and len(value) == 1:
            first = value[0]
            if hasattr(first, "__len__") and len(first) == 1:
                return first[0]
            return first
    except Exception:
        pass

    return value


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _status_from_numerr(numerr: Any, pinf: Any, dinf: Any) -> str:
    numerr_i = _safe_int(numerr)
    pinf_f = _safe_float(pinf)
    dinf_f = _safe_float(dinf)

    if pinf_f is not None and pinf_f > 0:
        return "primal_infeasible"

    if dinf_f is not None and dinf_f > 0:
        return "dual_infeasible"

    if numerr_i is None:
        return "unknown"

    if numerr_i == 0:
        return "solved"

    return f"numerr_{numerr_i}"


def _print_sedumi_result(result: dict[str, Any]) -> None:
    instance = result.get("instance", "unknown")
    status = result.get("status", "unknown")
    solve_time = result.get("solve_time_sec")
    iterations = result.get("iter")

    time_text = "time=NA" if solve_time is None else f"time={solve_time:.2f}s"
    iter_text = "iter=NA" if iterations is None else f"iter={iterations}"

    print(f"[SeDuMi] {instance} -> {status} | {time_text} | {iter_text}")


def _solve_one_sedumi_worker(instance_path: str | Path) -> dict[str, Any]:
    """
    Worker ejecutado en un proceso separado.
    Esto permite timeout real desde Python sin usar parfeval.
    """
    instance = Path(instance_path)
    instance_abs = _normalize_path(instance)

    eng = None

    try:
        if not SEDUMI_PATH.exists():
            raise FileNotFoundError(f"No se encontró SeDuMi en: {SEDUMI_PATH}")

        eng = matlab.engine.start_matlab()

        sedumi_path = _normalize_path(SEDUMI_PATH)
        eng.addpath(eng.genpath(sedumi_path), nargout=0)

        t0 = time.perf_counter()
        eng.eval(f"[A,b,c,K] = fromsdpa('{instance_abs}');", nargout=0)
        read_time_sec = time.perf_counter() - t0

        t1 = time.perf_counter()

        eng.eval(
            "pars.fid = 0; "
            "solver_log = evalc('[x,y,info] = sedumi(A,b,c,K,pars);');",
            nargout=0,
        )

        solve_time_sec = time.perf_counter() - t1

        iter_ = _matlab_scalar(eng, "info.iter")
        numerr = _matlab_scalar(eng, "info.numerr")
        pinf = _matlab_scalar(eng, "info.pinf")
        dinf = _matlab_scalar(eng, "info.dinf")
        feasratio = _matlab_scalar(eng, "info.feasratio")
        r0 = _matlab_scalar(eng, "info.r0")

        c_tx = None
        b_ty = None
        gap = None

        try:
            eng.eval("cTx_local = c' * x;", nargout=0)
            c_tx = _matlab_scalar(eng, "cTx_local")
        except Exception:
            c_tx = None

        try:
            eng.eval("bTy_local = b' * y;", nargout=0)
            b_ty = _matlab_scalar(eng, "bTy_local")
        except Exception:
            b_ty = None

        c_tx_f = _safe_float(c_tx)
        b_ty_f = _safe_float(b_ty)

        if c_tx_f is not None and b_ty_f is not None:
            gap = abs(c_tx_f - b_ty_f)

        status = _status_from_numerr(numerr, pinf, dinf)
        success = status == "solved"

        return {
            "instance": instance.stem,
            "solver": "sedumi",
            "success": success,
            "status": status,
            "read_time_sec": read_time_sec,
            "solve_time_sec": solve_time_sec,
            "iter": _safe_int(iter_),
            "numerr": _safe_int(numerr),
            "pinf": _safe_float(pinf),
            "dinf": _safe_float(dinf),
            "feasratio": _safe_float(feasratio),
            "r0": _safe_float(r0),
            "gap": gap,
        }

    except Exception as e:
        return {
            "instance": instance.stem,
            "solver": "sedumi",
            "success": False,
            "status": f"exception: {e}",
            "read_time_sec": None,
            "solve_time_sec": None,
            "iter": None,
            "numerr": None,
            "pinf": None,
            "dinf": None,
            "feasratio": None,
            "r0": None,
            "gap": None,
        }

    finally:
        if eng is not None:
            try:
                eng.quit()
            except Exception:
                pass


def solve_one_sedumi(instance_path: str | Path, timeout_sec: int = TIMEOUT_SEC) -> dict[str, Any]:
    """
    Ejecuta una instancia de SeDuMi con timeout real usando un proceso separado.
    """
    instance = Path(instance_path)

    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_solve_one_sedumi_worker, instance_path)

        try:
            result = future.result(timeout=timeout_sec)
            _print_sedumi_result(result)
            return result

        except TimeoutError:
            future.cancel()

            result = {
                "instance": instance.stem,
                "solver": "sedumi",
                "success": False,
                "status": "timeout",
                "read_time_sec": None,
                "solve_time_sec": float(timeout_sec),
                "iter": None,
                "numerr": None,
                "pinf": None,
                "dinf": None,
                "feasratio": None,
                "r0": None,
                "gap": None,
            }
            _print_sedumi_result(result)
            return result

        except Exception as e:
            result = {
                "instance": instance.stem,
                "solver": "sedumi",
                "success": False,
                "status": f"exception: {e}",
                "read_time_sec": None,
                "solve_time_sec": None,
                "iter": None,
                "numerr": None,
                "pinf": None,
                "dinf": None,
                "feasratio": None,
                "r0": None,
                "gap": None,
            }
            _print_sedumi_result(result)
            return result


def solve_sedumi_batch(instance_paths: list[str | Path], timeout_sec: int = TIMEOUT_SEC) -> list[dict[str, Any]]:
    if not instance_paths:
        return []

    results: list[dict[str, Any]] = []

    total = len(instance_paths)
    print(f"[SeDuMi] starting batch with {total} instances")

    for i, instance_path in enumerate(instance_paths, start=1):
        instance_name = Path(instance_path).stem
        print(f"[SeDuMi] ({i}/{total}) solving {instance_name} ...")

        result = solve_one_sedumi(instance_path, timeout_sec=timeout_sec)
        results.append(result)

    print("[SeDuMi] batch finished")
    return results