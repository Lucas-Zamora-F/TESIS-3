from __future__ import annotations

import time
from pathlib import Path
import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDPT3_PATH = PROJECT_ROOT / "extern" / "sdpt3"


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


def solve_with_sdpt3(sdpa_file: str | Path) -> dict:

    sdpa_file = str(Path(sdpa_file).resolve()).replace("\\", "/")

    eng = matlab.engine.start_matlab()

    try:

        eng.addpath(eng.genpath(str(SDPT3_PATH).replace("\\", "/")), nargout=0)
        eng.install_sdpt3(nargout=0)

        t0 = time.perf_counter()
        eng.eval(f"[blk,At,C,b] = read_sdpa('{sdpa_file}');", nargout=0)
        read_time = time.perf_counter() - t0

        t1 = time.perf_counter()
        eng.eval("[obj,X,y,Z,info] = sqlp(blk,At,C,b);", nargout=0)
        solve_time = time.perf_counter() - t1

        pobj = _matlab_scalar(eng, "obj(1)")
        dobj = _matlab_scalar(eng, "obj(2)")

        try:
            gap = abs(float(pobj) - float(dobj))
        except Exception:
            gap = None

        return {
            "solver": "sdpt3",
            "instance": sdpa_file,
            "read_time_sec": read_time,
            "solve_time_sec": solve_time,
            "iter": _matlab_scalar(eng, "info.iter"),
            "cpusec": _matlab_scalar(eng, "info.cputime"),
            "termcode": _matlab_scalar(eng, "info.termcode"),
            "cTx": pobj,
            "bTy": dobj,
            "gap": gap,
        }

    finally:
        eng.quit()