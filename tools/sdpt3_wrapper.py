from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SDPT3_PATH = PROJECT_ROOT / "extern" / "sdpt3"


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _matlab_scalar(eng, expr: str):
    """
    Intenta extraer un escalar simple desde MATLAB.
    """
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


def _status_from_termcode(termcode: Any) -> str:
    """
    Traducción conservadora. Si después quieres, la refinamos según SDPT3.
    """
    code = _safe_int(termcode)

    if code is None:
        return "unknown"

    if code == 0:
        return "solved"

    return f"termcode_{code}"


def _print_sdpt3_result(result: dict[str, Any]) -> None:
    instance = result.get("instance", "unknown")
    status = result.get("status", "unknown")
    solve_time = result.get("solve_time_sec")
    iterations = result.get("iter")
    termcode = result.get("termcode")
    gap = result.get("gap")

    if solve_time is None:
        time_text = "time=NA"
    else:
        time_text = f"time={solve_time:.2f}s"

    if iterations is None:
        iter_text = "iter=NA"
    else:
        iter_text = f"iter={iterations}"

    if termcode is None:
        termcode_text = "termcode=NA"
    else:
        termcode_text = f"termcode={termcode}"

    if gap is None:
        gap_text = "gap=NA"
    else:
        gap_text = f"gap={gap:.2e}"

    print(f"[SDPT3] {instance} -> {status} | {time_text} | {iter_text} | {termcode_text} | {gap_text}")


def start_sdpt3_engine():
    """
    Abre MATLAB una sola vez y deja SDPT3 listo.
    """
    if not SDPT3_PATH.exists():
        raise FileNotFoundError(f"No se encontró SDPT3 en: {SDPT3_PATH}")

    eng = matlab.engine.start_matlab()

    sdpt3_path = _normalize_path(SDPT3_PATH)

    eng.addpath(eng.genpath(sdpt3_path), nargout=0)

    # Captura la salida de instalación por si imprime mensajes
    eng.eval("evalc('install_sdpt3');", nargout=0)

    return eng


def close_sdpt3_engine(eng) -> None:
    """
    Cierra la sesión MATLAB.
    """
    if eng is not None:
        eng.quit()


def solve_one_sdpt3(eng, instance_path: str | Path) -> dict[str, Any]:
    """
    Resuelve una instancia con SDPT3 usando una sesión MATLAB ya abierta.
    Silencia la salida del solver usando evalc(...).
    """
    instance = Path(instance_path)
    instance_abs = _normalize_path(instance)

    try:
        t0 = time.perf_counter()
        eng.eval(f"[blk,At,C,b] = read_sdpa('{instance_abs}');", nargout=0)
        read_time_sec = time.perf_counter() - t0

        t1 = time.perf_counter()

        # Captura toda la salida que normalmente imprimiría SDPT3
        eng.eval(
            "solver_log = evalc('[obj,X,y,Z,info] = sqlp(blk,At,C,b);');",
            nargout=0
        )

        solve_time_sec = time.perf_counter() - t1

        c_tx = _matlab_scalar(eng, "obj(1)")
        b_ty = _matlab_scalar(eng, "obj(2)")
        termcode = _matlab_scalar(eng, "info.termcode")
        iterations = _matlab_scalar(eng, "info.iter")

        c_tx_f = _safe_float(c_tx)
        b_ty_f = _safe_float(b_ty)
        gap = None

        if c_tx_f is not None and b_ty_f is not None:
            gap = abs(c_tx_f - b_ty_f)

        status = _status_from_termcode(termcode)
        success = status == "solved"

        result = {
            "instance": instance.stem,
            "solver": "sdpt3",
            "success": success,
            "status": status,
            "read_time_sec": read_time_sec,
            "solve_time_sec": solve_time_sec,
            "iter": _safe_int(iterations),
            "termcode": _safe_int(termcode),
            "gap": gap,
        }
        _print_sdpt3_result(result)
        return result

    except Exception as e:
        result = {
            "instance": instance.stem,
            "solver": "sdpt3",
            "success": False,
            "status": f"exception: {e}",
            "read_time_sec": None,
            "solve_time_sec": None,
            "iter": None,
            "termcode": None,
            "gap": None,
        }
        _print_sdpt3_result(result)
        return result


def solve_sdpt3_batch(instance_paths: list[str | Path]) -> list[dict[str, Any]]:
    """
    Resuelve varias instancias con una sola sesión MATLAB.
    """
    if not instance_paths:
        return []

    eng = start_sdpt3_engine()

    try:
        results: list[dict[str, Any]] = []

        total = len(instance_paths)
        print(f"[SDPT3] starting batch with {total} instances")

        for i, instance_path in enumerate(instance_paths, start=1):
            instance_name = Path(instance_path).stem
            print(f"[SDPT3] ({i}/{total}) solving {instance_name} ...")

            result = solve_one_sdpt3(eng, instance_path)
            results.append(result)

        print("[SDPT3] batch finished")
        return results

    finally:
        close_sdpt3_engine(eng)