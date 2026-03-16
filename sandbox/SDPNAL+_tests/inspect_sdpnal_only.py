from __future__ import annotations

from pathlib import Path
import io
import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SDPNAL_PATH = PROJECT_ROOT / "extern" / "SDPNAL+v1.0"


def normalize_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def main() -> None:
    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    out = io.StringIO()
    err = io.StringIO()

    try:
        sdpnal_path = normalize_path(SDPNAL_PATH)

        print(f"Ruta SDPNAL+: {sdpnal_path}")
        print(f"Existe en Python: {SDPNAL_PATH.exists()}")

        if not SDPNAL_PATH.exists():
            raise FileNotFoundError(f"No existe la carpeta: {SDPNAL_PATH}")

        eng.eval("restoredefaultpath; rehash;", nargout=0)
        eng.addpath(eng.genpath(sdpnal_path), nargout=0)

        print("\n=== WHICH ===")
        for fn in [
            "sdpnalplus",
            "SDPNALplus_Demo",
            "read_sdpa",
            "sqlpread",
            "readsdpa",
            "loadsdpafile",
            "scaling",
        ]:
            try:
                result = eng.which(fn)
            except Exception:
                result = ""
            print(f"{fn:16s} -> {result}")

        print("\n=== BUSCANDO ARCHIVOS .m / .p RELACIONADOS ===")
        eng.eval(
            r"""
            disp('--- archivos con "read" en el nombre ---');
            disp(evalc('which -all *read*'));

            disp('--- archivos con "sdpa" en el nombre ---');
            disp(evalc('which -all *sdpa*'));

            disp('--- archivos con "sqlp" en el nombre ---');
            disp(evalc('which -all *sqlp*'));
            """,
            nargout=0,
            stdout=out,
            stderr=err,
        )

        print(out.getvalue())

        if err.getvalue().strip():
            print("=== ERRORES MATLAB ===")
            print(err.getvalue())

    except Exception as exc:
        print("\nOcurrió un error:")
        print(exc)

        if out.getvalue().strip():
            print("\n=== SALIDA MATLAB ===")
            print(out.getvalue())

        if err.getvalue().strip():
            print("\n=== ERRORES MATLAB ===")
            print(err.getvalue())

    finally:
        print("\nCerrando motor de MATLAB...")
        eng.quit()
        print("Motor de MATLAB cerrado.")


if __name__ == "__main__":
    main()