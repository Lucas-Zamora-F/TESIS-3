from __future__ import annotations

from pathlib import Path
import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parent
SDPNAL_PATH = PROJECT_ROOT / "extern" / "SDPNAL+v1.0"


def normalize_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def main() -> None:
    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        sdpnal_path = normalize_path(SDPNAL_PATH)

        print(f"Agregando SDPNAL+ al path:\n{sdpnal_path}")
        eng.addpath(eng.genpath(sdpnal_path), nargout=0)

        print("\nVerificando instalación...")
        which_sdpnal = eng.which("sdpnalplus")
        print(f"which sdpnalplus -> {which_sdpnal}")

        if not which_sdpnal:
            raise RuntimeError("MATLAB no encontró sdpnalplus en el path.")

        print("\nCambiando carpeta al ejemplo de SDPNAL+...")
        eng.cd(sdpnal_path, nargout=0)

        print("\nEjecutando script de demostración: SDPNALplus_Demo")
        eng.eval("SDPNALplus_Demo", nargout=0)

        print("\nDemo ejecutada correctamente.")

    except Exception as exc:
        print("\nOcurrió un error al ejecutar SDPNAL+:")
        print(exc)

    finally:
        print("\nCerrando motor de MATLAB...")
        eng.quit()
        print("Motor de MATLAB cerrado.")


if __name__ == "__main__":
    main()