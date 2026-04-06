from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main.build_features_table import build_features_table
from main.build_solver_runtime_table import build_solver_runtime_table
from main.build_isa_metadata_table import build_isa_metadata_table
from tools.isa.run_matilda import run_matilda
from tools.logging.universal_logger import (
    setup_universal_logger,
    log_event,
    log_exception,
)


def orchestrate_isa_metadata(
    run_matilda_step: bool = True,
    use_all_instances: bool = False,
) -> pd.DataFrame:
    """
    Orquestador principal.

    Parámetros
    ----------
    run_matilda_step : bool
        Ejecutar MATILDA al final.

    use_all_instances : bool
        - False → usa enabled_instances del config
        - True → usa TODAS las instancias en sdplib
    """
    setup_universal_logger()

    instances_config_path = REPO_ROOT / "config" / "instances_config.json"
    features_config_path = REPO_ROOT / "config" / "features_config.json"
    solver_registry_path = REPO_ROOT / "config" / "solver_registry.json"
    instances_dir = REPO_ROOT / "data" / "instances" / "sdplib"
    output_dir = REPO_ROOT / "ISA metadata"
    output_path = output_dir / "metadata.csv"

    try:
        log_event(
            "INFO",
            "orchestrator",
            "Starting ISA metadata orchestration.",
            extra={
                "use_all_instances": use_all_instances,
                "run_matilda_step": run_matilda_step,
            },
        )

        if use_all_instances:
            enabled_instance_paths = _get_all_instances(instances_dir)
            enabled_instance_names = [Path(p).name for p in enabled_instance_paths]

            print("[INFO] Modo: TODAS las instancias")
        else:
            enabled_instance_names = _load_enabled_instances(instances_config_path)
            enabled_instance_paths = _resolve_instance_paths(
                instance_names=enabled_instance_names,
                instances_dir=instances_dir,
            )

            print("[INFO] Modo: enabled_instances desde config")

        log_event(
            "INFO",
            "orchestrator",
            "Instances selected.",
            extra={
                "count": len(enabled_instance_paths),
                "use_all_instances": use_all_instances,
            },
        )

        print("========================================")
        print("ISA METADATA ORCHESTRATOR")
        print("========================================")
        print(f"[INFO] Instancias: {len(enabled_instance_paths)}")

        print("\n[INFO] Construyendo features_table...")
        features_table = build_features_table(
            enabled_instance_paths,
            str(features_config_path),
        )
        _validate_dataframe(features_table, "features_table")

        print("[INFO] Construyendo solver_runtime_table...")
        solver_runtime_table = build_solver_runtime_table(
            enabled_instance_paths,
            str(solver_registry_path),
        )
        _validate_dataframe(solver_runtime_table, "solver_runtime_table")

        print("[INFO] Construyendo metadata_df...")
        metadata_df = build_isa_metadata_table(
            features_table,
            solver_runtime_table,
        )
        _validate_dataframe(metadata_df, "metadata_df")

        output_dir.mkdir(parents=True, exist_ok=True)
        metadata_df.to_csv(output_path, index=False)

        print(f"[OK] Metadata guardada en: {output_path}")

        # ------------------------------------------------------------------
        # MATILDA
        # ------------------------------------------------------------------
        if run_matilda_step:
            print("\n[INFO] Ejecutando MATILDA...")
            matilda_run_dir = run_matilda()
            print(f"[OK] MATILDA corrio en: {matilda_run_dir}")

        return metadata_df

    except Exception as exc:
        log_exception(
            "orchestrator",
            "ISA metadata orchestration failed.",
            exc,
        )
        raise



def _get_all_instances(instances_dir: Path) -> list[str]:
    """
    Retorna TODAS las instancias .dat-s dentro de sdplib.
    """
    if not instances_dir.exists():
        raise FileNotFoundError(f"No existe la carpeta: {instances_dir}")

    instances = sorted(instances_dir.glob("*.dat-s"))

    if not instances:
        raise ValueError("No se encontraron archivos .dat-s en sdplib.")

    return [str(p) for p in instances]


def _load_enabled_instances(config_path: Path) -> list[str]:
    if not config_path.exists():
        raise FileNotFoundError(f"No se encontró: {config_path}")

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    return config["enabled_instances"]


def _resolve_instance_paths(
    instance_names: list[str],
    instances_dir: Path,
) -> list[str]:

    resolved = []
    for name in instance_names:
        path = instances_dir / name
        if not path.exists():
            raise FileNotFoundError(f"No existe: {path}")
        resolved.append(str(path))

    return resolved


def _validate_dataframe(df: pd.DataFrame, name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{name} no es DataFrame")
    if df.empty:
        raise ValueError(f"{name} está vacío")


if __name__ == "__main__":
    orchestrate_isa_metadata(
        run_matilda_step=True,
        use_all_instances=True,
    )