from __future__ import annotations

import json
import shutil
from pathlib import Path

import matlab.engine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent

MATILDA_PATH = PROJECT_ROOT / "extern" / "matilda"
INPUT_METADATA = SCRIPT_DIR / "matilda_metadata.csv"
RUN_DIR = SCRIPT_DIR / "matilda_run"


def create_options() -> dict:
    """
    Crea un options.json con la misma estructura del ejemplo de MATILDA.
    """
    return {
        "parallel": {
            "flag": False,
            "ncores": 18
        },
        "perf": {
            "MaxPerf": False,
            "AbsPerf": False,
            "epsilon": 0.2,
            "betaThreshold": 0.55
        },
        "auto": {
            "preproc": False
        },
        "bound": {
            "flag": True
        },
        "norm": {
            "flag": True
        },
        "selvars": {
            "smallscaleflag": False,
            "smallscale": 0.5,
            "fileidxflag": False,
            "fileidx": "",
            "densityflag": False,
            "mindistance": 0.1,
            "type": "Ftr&Good"
        },
        "sifted": {
            "flag": True,
            "rho": 0.1,
            "K": 10,
            "NTREES": 50,
            "MaxIter": 1000,
            "Replicates": 100
        },
        "pilot": {
            "analytic": False,
            "ntries": 5
        },
        "cloister": {
            "pval": 0.05,
            "cthres": 0.7
        },
        "pythia": {
            "flag": True,
            "useknn": True,
            "cvfolds": 5,
            "ispolykrnl": False,
            "useweights": False,
            "uselibsvm": False
        },
        "trace": {
            "usesim": True,
            "PI": 0.55
        },
        "outputs": {
            "csv": True,
            "web": False,
            "png": True
        }
    }


def prepare_run_directory() -> Path:
    """
    Crea una carpeta limpia de ejecución para MATILDA y deja dentro:
    - metadata.csv
    - options.json
    """
    if RUN_DIR.exists():
        shutil.rmtree(RUN_DIR)

    RUN_DIR.mkdir(parents=True, exist_ok=True)

    metadata_dst = RUN_DIR / "metadata.csv"
    options_dst = RUN_DIR / "options.json"

    shutil.copyfile(INPUT_METADATA, metadata_dst)

    with open(options_dst, "w", encoding="utf-8") as f:
        json.dump(create_options(), f, indent=4)

    return RUN_DIR


def main() -> None:
    if not MATILDA_PATH.exists():
        raise FileNotFoundError(f"No se encontró MATILDA en: {MATILDA_PATH}")

    if not INPUT_METADATA.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {INPUT_METADATA}")

    run_dir = prepare_run_directory()

    matlab_matilda_path = str(MATILDA_PATH.resolve()).replace("\\", "/")
    matlab_run_dir = str(run_dir.resolve()).replace("\\", "/")

    if not matlab_run_dir.endswith("/"):
        matlab_run_dir += "/"

    print("========================================")
    print(" INICIANDO EJECUCIÓN DE MATILDA")
    print("========================================")
    print(f"MATILDA_PATH : {matlab_matilda_path}")
    print(f"RUN_DIR      : {matlab_run_dir}")
    print()

    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        print("Cambiando directorio a MATILDA...")
        eng.cd(matlab_matilda_path, nargout=0)

        print("Ejecutando buildIS...")
        eng.eval(f"model = buildIS('{matlab_run_dir}');", nargout=0)

        print()
        print("========================================")
        print(" MATILDA TERMINÓ CORRECTAMENTE")
        print("========================================")
        print(f"Resultados en: {run_dir}")

    except Exception as e:
        print()
        print("========================================")
        print(" ERROR AL EJECUTAR MATILDA")
        print("========================================")
        print(e)
        raise

    finally:
        eng.quit()
        print("Motor de MATLAB cerrado.")


if __name__ == "__main__":
    main()