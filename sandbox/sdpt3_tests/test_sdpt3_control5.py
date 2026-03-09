from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDPT3_PATH = PROJECT_ROOT / "extern" / "sdpt3"
INSTANCE_PATH = PROJECT_ROOT / "data" / "instances" / "sdplib" / "control5.dat-s"

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


def _solve_one_sdpt3_worker(instance_path: str | Path) -> dict[str, Any]:
    instance = Path(instance_path)
    eng = None

    try:
        if not instance.exists():
            raise FileNotFoundError(f"No existe el archivo: {instance}")

        if not SDPT3_PATH.exists():
            raise FileNotFoundError(f"No se encontró SDPT3 en: {SDPT3_PATH}")

        instance_abs = _normalize_path(instance)
        sdpt3_path = _normalize_path(SDPT3_PATH)

        eng = matlab.engine.start_matlab()
        eng.addpath(eng.genpath(sdpt3_path), nargout=0)

        eng.workspace["instance_file"] = instance_abs

        matlab_exists = _safe_int(_matlab_scalar(eng, "exist(instance_file, 'file')"))
        which_read_sdpa = _matlab_scalar(eng, "which('read_sdpa')")
        which_sdpt3 = _matlab_scalar(eng, "which('sdpt3')")

        t0 = time.perf_counter()
        eng.eval(
            """
            clear blk At C b info runhist solver_log
            [blk, At, C, b] = read_sdpa(instance_file);
            """,
            nargout=0,
        )
        read_time_sec = time.perf_counter() - t0

        has_blk = _safe_int(_matlab_scalar(eng, "exist('blk','var')"))
        has_At = _safe_int(_matlab_scalar(eng, "exist('At','var')"))
        has_C = _safe_int(_matlab_scalar(eng, "exist('C','var')"))
        has_b = _safe_int(_matlab_scalar(eng, "exist('b','var')"))

        blk_len = _safe_int(_matlab_scalar(eng, "length(blk)"))
        b_len = _safe_int(_matlab_scalar(eng, "length(b)"))

        if not all(x == 1 for x in [has_blk, has_At, has_C, has_b]):
            raise RuntimeError("read_sdpa no dejó blk/At/C/b correctamente definidos.")

        if blk_len is None or blk_len == 0:
            raise RuntimeError("blk quedó vacío después de read_sdpa.")

        try:
            eng.eval(
                """
                At_fro = 0;
                C_fro = 0;

                for ii = 1:size(blk,1)
                    try
                        At_fro = At_fro + norm(full(At{ii}), 'fro');
                    catch
                    end
                    try
                        C_fro = C_fro + norm(full(C{ii}), 'fro');
                    catch
                    end
                end

                b_norm_2 = norm(full(b));
                """,
                nargout=0,
            )
            At_fro = _safe_float(_matlab_scalar(eng, "At_fro"))
            C_fro = _safe_float(_matlab_scalar(eng, "C_fro"))
            b_norm_2 = _safe_float(_matlab_scalar(eng, "b_norm_2"))
        except Exception:
            At_fro = None
            C_fro = None
            b_norm_2 = None

        t1 = time.perf_counter()
        eng.eval(
            """
            OPTIONS = struct();
            OPTIONS.gaptol = 1e-8;
            OPTIONS.inftol = 1e-8;
            OPTIONS.steptol = 1e-6;
            OPTIONS.maxit = 100;
            OPTIONS.printlevel = 3;

            solver_log = evalc('[obj,X,y,Z,info,runhist] = sdpt3(blk,At,C,b,OPTIONS);');
            """,
            nargout=0,
        )
        solve_time_sec = time.perf_counter() - t1

        result = {
            "instance": instance.stem,
            "path": instance_abs,
            "matlab_exists": matlab_exists,
            "which_read_sdpa": which_read_sdpa,
            "which_sdpt3": which_sdpt3,
            "read_time_sec": read_time_sec,
            "solve_time_sec": solve_time_sec,
            "blk_len": blk_len,
            "b_len": b_len,
            "At_fro": At_fro,
            "C_fro": C_fro,
            "b_norm_2": b_norm_2,
        }

        info_fields = {
            "termcode": "info.termcode",
            "iter": "info.iter",
            "gap": "info.gap",
            "relgap": "info.relgap",
            "pinfeas": "info.pinfeas",
            "dinfeas": "info.dinfeas",
            "primobj": "info.primobj",
            "dualobj": "info.dualobj",
            "cputime": "info.cputime",
        }

        for key, expr in info_fields.items():
            try:
                value = _matlab_scalar(eng, expr)
            except Exception:
                value = None

            if key in {"termcode", "iter"}:
                result[key] = _safe_int(value)
            else:
                result[key] = _safe_float(value)

        try:
            result["runhist_gap"] = _safe_float(_matlab_scalar(eng, "runhist.gap(end)"))
        except Exception:
            result["runhist_gap"] = None

        try:
            result["runhist_pinfeas"] = _safe_float(_matlab_scalar(eng, "runhist.pinfeas(end)"))
        except Exception:
            result["runhist_pinfeas"] = None

        try:
            result["runhist_dinfeas"] = _safe_float(_matlab_scalar(eng, "runhist.dinfeas(end)"))
        except Exception:
            result["runhist_dinfeas"] = None

        try:
            solver_log = eng.workspace["solver_log"]
        except Exception:
            solver_log = None

        if isinstance(solver_log, str) and solver_log.strip():
            lines = [line for line in solver_log.splitlines() if line.strip()]
            result["log_tail"] = "\n".join(lines[-40:])
        else:
            result["log_tail"] = None

        result["status"] = "ok"
        return result

    except Exception as e:
        return {
            "instance": instance.stem,
            "path": _normalize_path(instance),
            "status": f"exception: {e}",
        }

    finally:
        if eng is not None:
            try:
                eng.quit()
            except Exception:
                pass


def solve_one_sdpt3(instance_path: str | Path, timeout_sec: int = TIMEOUT_SEC) -> dict[str, Any]:
    instance = Path(instance_path)

    with ProcessPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_solve_one_sdpt3_worker, instance_path)

        try:
            return future.result(timeout=timeout_sec)

        except TimeoutError:
            future.cancel()
            return {
                "instance": instance.stem,
                "path": _normalize_path(instance),
                "status": "timeout",
            }

        except Exception as e:
            return {
                "instance": instance.stem,
                "path": _normalize_path(instance),
                "status": f"exception: {e}",
            }


def print_result(result: dict[str, Any]) -> None:
    print("\n" + "=" * 100)
    print(f"INSTANCIA: {result.get('instance')}")
    print("=" * 100)

    for key, value in result.items():
        if key != "log_tail":
            print(f"{key:20}: {value}")

    print("\n" + "-" * 100)
    print("LOG FINAL SDPT3")
    print("-" * 100)
    print(result.get("log_tail") or "No disponible")


def main() -> None:
    print("=" * 100)
    print("TEST SDPT3 SOLO PARA control5")
    print("=" * 100)
    print(f"Archivo objetivo: {INSTANCE_PATH}")
    print(f"Existe en Python: {INSTANCE_PATH.exists()}")

    result = solve_one_sdpt3(INSTANCE_PATH, timeout_sec=TIMEOUT_SEC)
    print_result(result)


if __name__ == "__main__":
    main()