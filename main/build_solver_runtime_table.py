from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config" / "solver_registry.json"
DEFAULT_SOLVER_CONFIG_PATH = PROJECT_ROOT / "config" / "solver_config.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"El archivo {path} no contiene un objeto JSON válido")

    return data


def _flatten_available_solvers(available_solvers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Aplana la estructura available_solvers para permitir grupos como:
    {
        "matlab_solvers": {
            "sdpt3": {...},
            "sedumi": {...}
        }
    }

    y también soporta una estructura plana:
    {
        "sdpt3": {...},
        "sedumi": {...}
    }
    """
    flat: dict[str, dict[str, Any]] = {}

    for key, value in available_solvers.items():
        if isinstance(value, dict):
            # Caso 1: estructura agrupada
            # e.g. "matlab_solvers": {"sdpt3": {...}, "sedumi": {...}}
            nested_solver_like = all(isinstance(v, dict) for v in value.values())
            if nested_solver_like and any(
                isinstance(v, dict) and (
                    "wrapper_module" in v
                    or "wrapper_class" in v
                    or "display_name" in v
                )
                for v in value.values()
            ):
                for solver_name, solver_info in value.items():
                    if not isinstance(solver_info, dict):
                        continue
                    flat[solver_name] = solver_info
            else:
                # Caso 2: estructura plana, donde key ya es el solver
                flat[key] = value

    return flat


def load_enabled_solvers(registry_path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    registry = _load_json(registry_path)

    enabled_solvers = registry.get("enabled_solvers", [])
    available_solvers = registry.get("available_solvers", {})

    if not isinstance(enabled_solvers, list):
        raise ValueError("'enabled_solvers' debe ser una lista")

    if not isinstance(available_solvers, dict):
        raise ValueError("'available_solvers' debe ser un diccionario")

    if not enabled_solvers:
        raise ValueError("No hay solvers habilitados en 'enabled_solvers'")

    flat_available = _flatten_available_solvers(available_solvers)

    missing = [solver for solver in enabled_solvers if solver not in flat_available]
    if missing:
        raise ValueError(
            f"Los siguientes solvers de 'enabled_solvers' no existen en "
            f"'available_solvers': {missing}"
        )

    return {solver: flat_available[solver] for solver in enabled_solvers}


def _import_wrapper_class(module_name: str, class_name: str):
    module = importlib.import_module(module_name)

    if not hasattr(module, class_name):
        raise AttributeError(
            f"El módulo '{module_name}' no contiene la clase '{class_name}'"
        )

    return getattr(module, class_name)


def _safe_runtime(result: dict[str, Any]) -> float:
    """
    Extrae el runtime desde el resultado normalizado del wrapper.
    Si no existe o no es convertible, retorna NaN.
    """
    if not isinstance(result, dict):
        return float("nan")

    value = result.get("runtime", float("nan"))

    try:
        return float(value)
    except Exception:
        return float("nan")


def _instance_display_name(instance_path: Path) -> str:
    """
    Usa el nombre de la instancia sin extensión principal.
    Ejemplo:
    arch0.dat-s -> arch0
    """
    name = instance_path.name
    if name.endswith(".dat-s"):
        return name[:-6]
    return instance_path.stem


def build_solver_runtime_table(
    instance_paths: Iterable[str | Path],
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    solver_config_path: str | Path = DEFAULT_SOLVER_CONFIG_PATH,
) -> pd.DataFrame:
    """
    Construye y retorna un DataFrame con forma:

    | Instance | algo_sdpt3 | algo_sedumi |
    |----------|------------|-------------|
    | arch0    | 12.53      | 8.91        |
    | arch2    | 20.11      | 14.77       |

    Parámetros
    ----------
    instance_paths:
        Lista iterable de rutas a instancias entregadas por el orquestador mayor.
    registry_path:
        Ruta a config/solver_registry.json
    solver_config_path:
        Ruta a config/solver_config.json

    Retorna
    -------
    pd.DataFrame
    """
    registry_path = Path(registry_path)
    solver_config_path = Path(solver_config_path)

    enabled_solver_info = load_enabled_solvers(registry_path)

    normalized_instances: list[Path] = []
    for instance in instance_paths:
        instance_path = Path(instance).resolve()
        if not instance_path.is_file():
            raise FileNotFoundError(f"No existe la instancia: {instance_path}")
        normalized_instances.append(instance_path)

    if not normalized_instances:
        return pd.DataFrame(columns=["Instance"])

    wrappers: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    try:
        # Instanciar cada wrapper una sola vez.
        # Esto es importante porque SDPT3 y SeDuMi usan MatlabRunner.
        for solver_name, solver_info in enabled_solver_info.items():
            module_name = solver_info.get("wrapper_module")
            class_name = solver_info.get("wrapper_class")

            if not module_name or not class_name:
                raise ValueError(
                    f"El solver '{solver_name}' debe definir "
                    f"'wrapper_module' y 'wrapper_class' en solver_registry.json"
                )

            wrapper_class = _import_wrapper_class(module_name, class_name)
            wrappers[solver_name] = wrapper_class(
                config_path=str(solver_config_path),
                project_root=str(PROJECT_ROOT),
            )

        # Ejecutar todas las instancias en todos los solvers.
        for instance_path in normalized_instances:
            row: dict[str, Any] = {
                "Instance": _instance_display_name(instance_path)
            }

            for solver_name, wrapper in wrappers.items():
                result = wrapper.solve(str(instance_path))
                row[f"algo_{solver_name}"] = _safe_runtime(result)

            rows.append(row)

    finally:
        # Cerrar wrappers si exponen close()
        for wrapper in wrappers.values():
            close_method = getattr(wrapper, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except Exception:
                    pass

    df = pd.DataFrame(rows)

    # Orden de columnas: Instance primero, luego columnas de solver
    solver_columns = [f"algo_{solver_name}" for solver_name in enabled_solver_info.keys()]
    ordered_columns = ["Instance", *solver_columns]
    df = df[ordered_columns]

    return df