from __future__ import annotations

import time
from pathlib import Path
import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEDUMI_PATH = PROJECT_ROOT / "extern" / "sedumi"


def _matlab_scalar(eng, expr: str):
    value = eng.eval(expr, nargout=1)

    if isinstance(value, (int, float)):
        return value

    try:
        if hasattr(value, "__len__") and len(value) == 1:
            first = value[0]
            if hasattr(first, "__len__") and len(first) == 1:
                return first[0]
    except Exception:
        pass

    return value


def solve_with_sedumi(sdpa_file: str | Path) -> dict:

    sdpa_file = str(Path(sdpa_file).resolve()).replace("\\", "/")

    eng = matlab.engine.start_matlab()

    try:
        eng.addpath(eng.genpath(str(SEDUMI_PATH).replace("\\", "/")), nargout=0)
        eng.install_sedumi(nargout=0)

        t0 = time.perf_counter()
        eng.eval(f"[At,b,c,K] = fromsdpa('{sdpa_file}');", nargout=0)
        read_time = time.perf_counter() - t0

        t1 = time.perf_counter()
        eng.eval("[x,y,info] = sedumi(At,b,c,K);", nargout=0)
        solve_time = time.perf_counter() - t1

        c_tx = _matlab_scalar(eng, "full(c' * x)")
        b_ty = _matlab_scalar(eng, "full(b' * y)")

        try:
            gap = abs(float(c_tx) - float(b_ty))
        except Exception:
            gap = None

        return {
            "solver": "sedumi",
            "instance": sdpa_file,
            "read_time_sec": read_time,
            "solve_time_sec": solve_time,
            "iter": _matlab_scalar(eng, "info.iter"),
            "numerr": _matlab_scalar(eng, "info.numerr"),
            "pinf": _matlab_scalar(eng, "info.pinf"),
            "dinf": _matlab_scalar(eng, "info.dinf"),
            "feasratio": _matlab_scalar(eng, "info.feasratio"),
            "r0": _matlab_scalar(eng, "info.r0"),
            "cpusec": _matlab_scalar(eng, "info.cpusec"),
            "cTx": c_tx,
            "bTy": b_ty,
            "gap": gap,
        }

    finally:
        eng.quit()