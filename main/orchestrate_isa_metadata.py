from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
# Bootstrap de imports para permitir ejecución directa con "Run Python File"
# en VS Code, sin depender de "python -m ...".
# -----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main.build_features_table import build_features_table
from main.build_solver_runtime_table import build_solver_runtime_table
from main.build_isa_metadata_table import build_isa_metadata_table
from tools.logging.universal_logger import (
    setup_universal_logger,
    log_event,
    log_exception,
)


def orchestrate_isa_metadata() -> pd.DataFrame:
    """
    Orquesta la construcción de la tabla final de metadata ISA.

    Flujo:
        1. Lee las instancias habilitadas desde config/instances_config.json
        2. Resuelve sus rutas reales en data/instances/sdplib
        3. Construye features_table usando config/features_config.json
        4. Construye solver_runtime_table usando config/solver_registry.json
        5. Combina ambas tablas en metadata_df
        6. Guarda metadata_df en ISA metadata/metadata.csv

    Retorna
    -------
    pd.DataFrame
        DataFrame final de metadata.
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
                "instances_config_path": str(instances_config_path),
                "features_config_path": str(features_config_path),
                "solver_registry_path": str(solver_registry_path),
                "instances_dir": str(instances_dir),
                "output_path": str(output_path),
            },
        )

        enabled_instance_names = _load_enabled_instances(instances_config_path)

        log_event(
            "INFO",
            "orchestrator",
            "Loaded enabled instances from config.",
            extra={
                "enabled_instances": enabled_instance_names,
                "count": len(enabled_instance_names),
            },
        )

        enabled_instance_paths = _resolve_instance_paths(
            instance_names=enabled_instance_names,
            instances_dir=instances_dir,
        )

        log_event(
            "INFO",
            "orchestrator",
            "Resolved enabled instance paths.",
            extra={
                "instance_paths": enabled_instance_paths,
                "count": len(enabled_instance_paths),
            },
        )

        print("========================================")
        print("ISA METADATA ORCHESTRATOR")
        print("========================================")
        print(f"[INFO] Instancias habilitadas: {len(enabled_instance_names)}")
        for instance_name in enabled_instance_names:
            print(f"  - {instance_name}")

        print("\n[INFO] Construyendo features_table...")
        log_event(
            "INFO",
            "orchestrator",
            "Calling build_features_table.",
            extra={
                "instances": enabled_instance_paths,
                "config_path": str(features_config_path),
            },
        )

        features_table = build_features_table(
            enabled_instance_paths,
            str(features_config_path),
        )
        _validate_dataframe(features_table, "features_table")

        log_event(
            "INFO",
            "orchestrator",
            "features_table built successfully.",
            extra={
                "shape": list(features_table.shape),
                "columns": features_table.columns.tolist(),
            },
        )

        print("[INFO] Construyendo solver_runtime_table...")
        log_event(
            "INFO",
            "orchestrator",
            "Calling build_solver_runtime_table.",
            extra={
                "instances": enabled_instance_paths,
                "config_path": str(solver_registry_path),
            },
        )

        solver_runtime_table = build_solver_runtime_table(
            enabled_instance_paths,
            str(solver_registry_path),
        )
        _validate_dataframe(solver_runtime_table, "solver_runtime_table")

        log_event(
            "INFO",
            "orchestrator",
            "solver_runtime_table built successfully.",
            extra={
                "shape": list(solver_runtime_table.shape),
                "columns": solver_runtime_table.columns.tolist(),
            },
        )

        print("[INFO] Construyendo metadata_df...")
        log_event(
            "INFO",
            "orchestrator",
            "Calling build_isa_metadata_table.",
            extra={
                "features_shape": list(features_table.shape),
                "solver_runtime_shape": list(solver_runtime_table.shape),
            },
        )

        metadata_df = build_isa_metadata_table(
            features_table,
            solver_runtime_table,
        )
        _validate_dataframe(metadata_df, "metadata_df")

        log_event(
            "INFO",
            "orchestrator",
            "metadata_df built successfully.",
            extra={
                "shape": list(metadata_df.shape),
                "columns": metadata_df.columns.tolist(),
            },
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        log_event(
            "INFO",
            "orchestrator",
            "Saving metadata dataframe to CSV.",
            extra={
                "output_path": str(output_path),
                "rows": len(metadata_df),
            },
        )

        metadata_df.to_csv(output_path, index=False)

        log_event(
            "INFO",
            "orchestrator",
            "ISA metadata orchestration finished successfully.",
            extra={
                "output_path": str(output_path),
            },
        )

        print(f"[OK] Metadata guardada en: {output_path}")
        return metadata_df

    except Exception as exc:
        log_exception(
            "orchestrator",
            "ISA metadata orchestration failed.",
            exc,
        )
        raise


def _load_enabled_instances(config_path: Path) -> list[str]:
    """
    Carga las instancias habilitadas desde config/instances_config.json.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de configuración de instancias: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    if "enabled_instances" not in config:
        raise ValueError(
            "El archivo instances_config.json no contiene la clave 'enabled_instances'."
        )

    enabled_instances = config["enabled_instances"]

    if not isinstance(enabled_instances, list):
        raise TypeError("'enabled_instances' debe ser una lista.")

    if not enabled_instances:
        raise ValueError("La lista 'enabled_instances' está vacía.")

    non_string_instances = [
        instance_name
        for instance_name in enabled_instances
        if not isinstance(instance_name, str)
    ]
    if non_string_instances:
        raise TypeError(
            "Todas las entradas de 'enabled_instances' deben ser strings."
        )

    return enabled_instances


def _resolve_instance_paths(
    instance_names: list[str],
    instances_dir: Path,
) -> list[str]:
    """
    Convierte nombres de instancia a rutas absolutas y valida que existan.
    """
    if not instances_dir.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de instancias: {instances_dir}"
        )

    resolved_paths: list[str] = []
    missing_instances: list[str] = []

    for instance_name in instance_names:
        instance_path = instances_dir / instance_name

        if not instance_path.exists():
            missing_instances.append(instance_name)
            continue

        resolved_paths.append(str(instance_path))

    if missing_instances:
        raise FileNotFoundError(
            "No se encontraron las siguientes instancias en "
            f"{instances_dir}: {missing_instances}"
        )

    return resolved_paths


def _validate_dataframe(df: pd.DataFrame, df_name: str) -> None:
    """
    Valida que el objeto retornado sea un DataFrame no vacío.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{df_name} debe ser un pandas.DataFrame.")

    if df.empty:
        raise ValueError(f"{df_name} está vacío.")


if __name__ == "__main__":
    orchestrate_isa_metadata()