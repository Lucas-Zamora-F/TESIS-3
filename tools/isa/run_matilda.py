from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matlab.engine
import pandas as pd


def find_repo_root(start: Path) -> Path:
    """
    Busca la raiz del repositorio subiendo directorios hasta encontrar
    una carpeta que contenga 'extern' y 'tools'.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "extern").exists() and (candidate / "tools").exists():
            return candidate
    raise FileNotFoundError(
        "No se pudo detectar la raiz del repositorio desde la ubicacion actual."
    )


SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = find_repo_root(SCRIPT_PATH)

INSTANCE_SPACE_PATH = PROJECT_ROOT / "extern" / "InstanceSpace87fe24e"
INPUT_METADATA = PROJECT_ROOT / "ISA metadata" / "metadata.csv"
OUTPUT_BASE_DIR = PROJECT_ROOT / "matilda_out"
INSTANCE_SPACE_CONFIG = PROJECT_ROOT / "config" / "instance_space_config.json"


def load_instance_space_options(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"No se encontro el archivo de configuracion: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        options = json.load(f)

    if not isinstance(options, dict):
        raise ValueError(
            "El archivo instance_space_config.json debe contener un objeto JSON."
        )

    return options


def validate_instance_space_options(options: dict[str, Any]) -> None:
    required_top_keys = [
        "parallel",
        "perf",
        "auto",
        "bound",
        "norm",
        "selvars",
        "sifted",
        "pilot",
        "cloister",
        "pythia",
        "trace",
        "outputs",
    ]

    for key in required_top_keys:
        if key not in options:
            raise ValueError(f"Falta la seccion obligatoria '{key}' en la configuracion.")

    perf = options["perf"]
    if not isinstance(perf, dict):
        raise ValueError("La seccion 'perf' debe ser un objeto JSON.")

    for key in ["MaxPerf", "AbsPerf", "epsilon", "betaThreshold"]:
        if key not in perf:
            raise ValueError(f"Falta 'perf.{key}' en la configuracion.")

    auto = options["auto"]
    if not isinstance(auto, dict) or "preproc" not in auto:
        raise ValueError("Falta 'auto.preproc' en la configuracion.")


def validate_metadata(metadata_path: Path) -> pd.DataFrame:
    if not metadata_path.exists():
        raise FileNotFoundError(f"No existe el archivo metadata: {metadata_path}")

    df = pd.read_csv(metadata_path)

    if df.empty:
        raise ValueError("El metadata.csv esta vacio.")

    if "Instances" not in df.columns:
        raise ValueError("El metadata.csv debe contener la columna 'Instances'.")

    feature_cols = [c for c in df.columns if c.startswith("feature_")]
    algo_cols = [c for c in df.columns if c.startswith("algo_")]

    if len(feature_cols) < 3:
        raise ValueError(
            "InstanceSpace requiere mas de dos columnas de features. "
            f"Se encontraron {len(feature_cols)} columnas 'feature_*'."
        )

    if len(algo_cols) < 1:
        raise ValueError(
            "El metadata.csv debe contener al menos una columna 'algo_*'."
        )

    if df["Instances"].isna().any():
        raise ValueError("La columna 'Instances' contiene valores vacios/NaN.")

    if (df["Instances"].astype(str).str.strip() == "").any():
        raise ValueError("La columna 'Instances' contiene strings vacios.")

    return df


def generate_run_dir(base_output_dir: Path) -> Path:
    run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir = base_output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def prepare_run_directory() -> Path:
    if not INSTANCE_SPACE_PATH.exists():
        raise FileNotFoundError(
            f"No se encontro InstanceSpace en: {INSTANCE_SPACE_PATH}"
        )

    if not INPUT_METADATA.exists():
        raise FileNotFoundError(
            f"No se encontro el archivo metadata: {INPUT_METADATA}"
        )

    df = validate_metadata(INPUT_METADATA)
    options = load_instance_space_options(INSTANCE_SPACE_CONFIG)
    validate_instance_space_options(options)

    OUTPUT_BASE_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = generate_run_dir(OUTPUT_BASE_DIR)

    metadata_dst = run_dir / "metadata.csv"
    options_dst = run_dir / "options.json"

    df.to_csv(metadata_dst, index=False)

    with open(options_dst, "w", encoding="utf-8") as f:
        json.dump(options, f, indent=4)

    return run_dir


def write_run_info(run_dir: Path) -> None:
    run_info = {
        "timestamp": datetime.now().isoformat(),
        "input_metadata": str(INPUT_METADATA.resolve()),
        "instance_space_path": str(INSTANCE_SPACE_PATH.resolve()),
        "instance_space_config": str(INSTANCE_SPACE_CONFIG.resolve()),
        "run_dir": str(run_dir.resolve()),
    }

    run_info_path = run_dir / "run_info.json"
    with open(run_info_path, "w", encoding="utf-8") as f:
        json.dump(run_info, f, indent=4)


def list_generated_files(run_dir: Path) -> list[Path]:
    return sorted([p for p in run_dir.rglob("*") if p.is_file()])


def run_matilda() -> Path:
    """
    Ejecuta MATILDA/InstanceSpace usando:
    - ISA metadata/metadata.csv
    - config/instance_space_config.json
    - extern/InstanceSpace87fe24e

    Retorna
    -------
    Path
        Ruta de la carpeta run_... generada en matilda_out.
    """
    run_dir = prepare_run_directory()
    write_run_info(run_dir)

    matlab_instance_space_path = str(INSTANCE_SPACE_PATH.resolve()).replace("\\", "/")
    matlab_run_dir = str(run_dir.resolve()).replace("\\", "/")

    if not matlab_run_dir.endswith("/"):
        matlab_run_dir += "/"

    print("================================================================================")
    print("RUN MATILDA / INSTANCE SPACE")
    print("================================================================================")
    print(f"[INFO] Project root         : {PROJECT_ROOT}")
    print(f"[INFO] Input metadata       : {INPUT_METADATA}")
    print(f"[INFO] InstanceSpace path   : {INSTANCE_SPACE_PATH}")
    print(f"[INFO] Config path          : {INSTANCE_SPACE_CONFIG}")
    print(f"[INFO] Base output dir      : {OUTPUT_BASE_DIR}")
    print(f"[INFO] Run directory        : {run_dir}")
    print()

    print("[INFO] Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        print(f"[INFO] Cambiando directorio a InstanceSpace: {matlab_instance_space_path}")
        eng.cd(matlab_instance_space_path, nargout=0)

        print(f"[INFO] Ejecutando buildIS sobre: {matlab_run_dir}")
        eng.eval(f"model = buildIS('{matlab_run_dir}');", nargout=0)

        print()
        print("================================================================================")
        print("MATILDA TERMINO CORRECTAMENTE")
        print("================================================================================")
        print(f"[INFO] Resultados en: {run_dir}")

        generated_files = list_generated_files(run_dir)
        if generated_files:
            print("[INFO] Archivos generados:")
            for path in generated_files:
                try:
                    rel = path.relative_to(PROJECT_ROOT)
                except ValueError:
                    rel = path
                print(f"  - {rel}")

        return run_dir

    except Exception as e:
        error_log_path = run_dir / "matlab_engine_error.txt"
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(str(e))

        print()
        print("================================================================================")
        print("ERROR AL EJECUTAR MATILDA")
        print("================================================================================")
        print(e)
        print(f"[INFO] Error guardado en: {error_log_path}")
        raise

    finally:
        eng.quit()
        print("[INFO] Motor de MATLAB cerrado.")


if __name__ == "__main__":
    run_matilda()