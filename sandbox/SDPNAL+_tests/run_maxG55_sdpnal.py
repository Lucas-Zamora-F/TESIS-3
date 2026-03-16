from __future__ import annotations

from pathlib import Path
import io
import re
import time
import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDPNAL_PATH = PROJECT_ROOT / "extern" / "SDPNAL+v1.0"
INSTANCE_PATH = PROJECT_ROOT / "data" / "instances" / "sdplib" / "maxG55.dat-s"


def normalize_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def extract_float(text: str, pattern: str):
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def extract_int(text: str, pattern: str):
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def parse_summary(matlab_log: str) -> dict:
    return {
        "termcode": extract_int(matlab_log, r"termcode\s*=\s*([+-]?\d+)"),
        "time_total": extract_float(
            matlab_log, r"Computing time \(total\)\s*=\s*([0-9eE+.\-]+)"
        ),
        "time_admm": extract_float(
            matlab_log, r"Computing time \(ADMM\+\)\s*=\s*([0-9eE+.\-]+)"
        ),
        "time_ssn": extract_float(
            matlab_log, r"Computing time \(SSN\)\s*=\s*([0-9eE+.\-]+)"
        ),
        "admm_iter": extract_int(
            matlab_log, r"number of ADMM\+ iter\s*=\s*([+-]?\d+)"
        ),
        "ssn_iter": extract_int(
            matlab_log, r"number of SSN\s+iter\s*=\s*([+-]?\d+)"
        ),
        "pobj": extract_float(
            matlab_log, r"primal objval\s*=\s*([0-9eE+.\-]+)"
        ),
        "dobj": extract_float(
            matlab_log, r"dual\s+objval\s*=\s*([0-9eE+.\-]+)"
        ),
        "relgap": extract_float(
            matlab_log, r"relative gap\s*=\s*([0-9eE+.\-]+)"
        ),
        "primfeasorg": extract_float(
            matlab_log, r"primfeasorg\s*=\s*([0-9eE+.\-]+)"
        ),
        "dualfeasorg": extract_float(
            matlab_log, r"dualfeasorg\s*=\s*([0-9eE+.\-]+)"
        ),
    }


def main() -> None:
    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    matlab_output = io.StringIO()
    matlab_error = io.StringIO()

    try:
        sdpnal_path = normalize_path(SDPNAL_PATH)
        instance_path = normalize_path(INSTANCE_PATH)

        print(f"Archivo objetivo: {instance_path}")
        print(f"Existe en Python: {INSTANCE_PATH.exists()}")

        if not INSTANCE_PATH.exists():
            raise FileNotFoundError(f"No existe la instancia: {INSTANCE_PATH}")

        eng.eval("restoredefaultpath; rehash;", nargout=0)
        eng.addpath(eng.genpath(sdpnal_path), nargout=0)

        print(f"which sdpnalplus -> {eng.which('sdpnalplus')}")
        print(f"which read_sdpa  -> {eng.which('read_sdpa')}")
        print(f"which scaling    -> {eng.which('scaling')}")

        print("\nLeyendo instancia SDPA...")
        eng.eval(
            f"[blk, At, C, b] = read_sdpa('{instance_path}');",
            nargout=0,
            stdout=matlab_output,
            stderr=matlab_error
        )

        print("Configurando opciones balanceadas...")
        eng.eval(
            r"""
            clear OPTIONS
            OPTIONS = SDPNALplus_parameters;

            if isfield(OPTIONS,'maxiter');     OPTIONS.maxiter = 4000; end
            if isfield(OPTIONS,'maxtime');     OPTIONS.maxtime = 300; end
            if isfield(OPTIONS,'ADMmaxiter');  OPTIONS.ADMmaxiter = 4000; end
            if isfield(OPTIONS,'printlevel');  OPTIONS.printlevel = 1; end

            disp('=== class(OPTIONS) ===');
            disp(class(OPTIONS));
            disp('=== fieldnames(OPTIONS) ===');
            disp(fieldnames(OPTIONS));
            """,
            nargout=0,
            stdout=matlab_output,
            stderr=matlab_error
        )

        print("\nCorriendo SDPNAL+...")
        start = time.time()

        eng.eval(
            r"""
            [obj, X, y, Z, info, runhist] = sdpnalplus( ...
                blk, At, C, b, [], [], [], [], [], OPTIONS);
            """,
            nargout=0,
            stdout=matlab_output,
            stderr=matlab_error
        )

        elapsed = time.time() - start
        full_log = matlab_output.getvalue()
        parsed = parse_summary(full_log)

        print("\n" + "=" * 90)
        print("RESULTADOS: maxG55 con SDPNAL+ BALANCED")
        print("=" * 90)
        print("instance       : maxG55")
        print(f"time_py_sec    : {elapsed:.6f}")
        print(f"termcode       : {parsed['termcode']}")
        print(f"time_total     : {parsed['time_total']}")
        print(f"time_admm      : {parsed['time_admm']}")
        print(f"time_ssn       : {parsed['time_ssn']}")
        print(f"admm_iter      : {parsed['admm_iter']}")
        print(f"ssn_iter       : {parsed['ssn_iter']}")
        print(f"pobj           : {parsed['pobj']}")
        print(f"dobj           : {parsed['dobj']}")
        print(f"relgap         : {parsed['relgap']}")
        print(f"primfeasorg    : {parsed['primfeasorg']}")
        print(f"dualfeasorg    : {parsed['dualfeasorg']}")

        if matlab_error.getvalue().strip():
            print("\n===== ERRORES MATLAB =====")
            print(matlab_error.getvalue())

        print("\n===== ÚLTIMAS 80 LÍNEAS DEL LOG MATLAB =====")
        lines = full_log.splitlines()
        print("\n".join(lines[-80:]))

    except Exception as exc:
        print("\nOcurrió un error:")
        print(exc)

        if matlab_output.getvalue().strip():
            print("\n===== SALIDA MATLAB =====")
            print(matlab_output.getvalue())

        if matlab_error.getvalue().strip():
            print("\n===== ERRORES MATLAB =====")
            print(matlab_error.getvalue())

    finally:
        print("\nCerrando motor de MATLAB...")
        eng.quit()
        print("Motor de MATLAB cerrado.")


if __name__ == "__main__":
    main()