from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from tqdm import tqdm

from tools.features.instance_reader import (
    collect_supported_instances,
    instance_display_name,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config" / "solver_registry.json"
DEFAULT_SOLVER_CONFIG_PATH = PROJECT_ROOT / "config" / "solver_config.json"
DEFAULT_INSTANCES_DIR = PROJECT_ROOT / "data" / "instances" / "sdplib"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "ISA metadata" / "intermediates" / "solver_runtime_table.csv"
)


def _load_json(path: Path) -> dict[str, Any]:
    """
    Load and validate a JSON file.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"File does not contain a valid JSON object: {path}")

    return data


def _flatten_available_solvers(
    available_solvers: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """
    Flatten the available_solvers structure.
    """
    flat: dict[str, dict[str, Any]] = {}

    for key, value in available_solvers.items():
        if isinstance(value, dict):
            nested_solver_like = all(isinstance(v, dict) for v in value.values())

            if nested_solver_like and any(
                isinstance(v, dict)
                and (
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
                flat[key] = value

    return flat


def load_enabled_solvers(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> dict[str, dict[str, Any]]:
    registry = _load_json(registry_path)

    enabled_solvers = registry.get("enabled_solvers", [])
    available_solvers = registry.get("available_solvers", {})

    if not isinstance(enabled_solvers, list):
        raise ValueError("'enabled_solvers' must be a list.")

    if not isinstance(available_solvers, dict):
        raise ValueError("'available_solvers' must be a dictionary.")

    if not enabled_solvers:
        raise ValueError("No solvers were found in 'enabled_solvers'.")

    flat_available = _flatten_available_solvers(available_solvers)

    missing = [solver for solver in enabled_solvers if solver not in flat_available]
    if missing:
        raise ValueError(
            "The following solvers in 'enabled_solvers' do not exist in "
            f"'available_solvers': {missing}"
        )

    return {solver: flat_available[solver] for solver in enabled_solvers}


def _import_wrapper_class(module_name: str, class_name: str):
    module = importlib.import_module(module_name)

    if not hasattr(module, class_name):
        raise AttributeError(
            f"Module '{module_name}' does not contain class '{class_name}'."
        )

    return getattr(module, class_name)


def _safe_runtime(result: dict[str, Any]) -> float:
    if not isinstance(result, dict):
        return float("nan")

    value = result.get("runtime", float("nan"))

    try:
        return float(value)
    except Exception:
        return float("nan")


def _instance_display_name(instance_path: Path) -> str:
    return instance_display_name(instance_path)


def _normalize_instance_paths(instance_paths: Iterable[str | Path]) -> list[Path]:
    normalized_instances: list[Path] = []

    for instance in instance_paths:
        instance_path = Path(instance).resolve()

        if not instance_path.exists():
            raise FileNotFoundError(f"Instance file does not exist: {instance_path}")

        if not instance_path.is_file():
            raise ValueError(f"Instance path is not a file: {instance_path}")

        normalized_instances.append(instance_path)

    return normalized_instances


def _clear_solver_sandbox_logs() -> None:
    sandbox = PROJECT_ROOT / "sandbox"
    for logs_dir in (sandbox / "sdpt3_logs_v2", sandbox / "sedumi_logs_v2"):
        if logs_dir.exists():
            shutil.rmtree(logs_dir)


def build_solver_runtime_table(
    instance_paths: Iterable[str | Path],
    registry_path: str | Path = DEFAULT_REGISTRY_PATH,
    solver_config_path: str | Path = DEFAULT_SOLVER_CONFIG_PATH,
) -> pd.DataFrame:

    registry_path = Path(registry_path)
    solver_config_path = Path(solver_config_path)

    _clear_solver_sandbox_logs()

    enabled_solver_info = load_enabled_solvers(registry_path)
    normalized_instances = _normalize_instance_paths(instance_paths)

    if not normalized_instances:
        return pd.DataFrame(columns=["Instance"])

    wrappers: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    try:
        # Instantiate each wrapper only once.
        for solver_name, solver_info in enabled_solver_info.items():
            module_name = solver_info.get("wrapper_module")
            class_name = solver_info.get("wrapper_class")

            if not module_name or not class_name:
                raise ValueError(
                    f"Solver '{solver_name}' must define "
                    f"'wrapper_module' and 'wrapper_class' in solver_registry.json."
                )

            wrapper_class = _import_wrapper_class(module_name, class_name)
            wrappers[solver_name] = wrapper_class(
                config_path=str(solver_config_path),
                project_root=str(PROJECT_ROOT),
            )

        # Run every instance on every enabled solver.
        for instance_path in tqdm(normalized_instances, desc="Processing instances", unit="instance"):
            row: dict[str, Any] = {
                "Instance": _instance_display_name(instance_path)
            }

            for solver_name, wrapper in wrappers.items():
                result = wrapper.solve(str(instance_path))
                row[f"algo_{solver_name}"] = _safe_runtime(result)

            rows.append(row)

    finally:
        for wrapper in wrappers.values():
            close_method = getattr(wrapper, "close", None)
            if callable(close_method):
                try:
                    close_method()
                except Exception:
                    pass

    df = pd.DataFrame(rows)

    solver_columns = [f"algo_{solver_name}" for solver_name in enabled_solver_info.keys()]
    ordered_columns = ["Instance", *solver_columns]
    df = df[ordered_columns]

    save_solver_runtime_table(df, DEFAULT_OUTPUT_PATH)

    return df


def save_solver_runtime_table(df: pd.DataFrame, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def _run_standalone() -> None:
    print("========================================")
    print("BUILD SOLVER RUNTIME TABLE")
    print("========================================")
    print(f"[INFO] Instances directory : {DEFAULT_INSTANCES_DIR}")
    print(f"[INFO] Registry path       : {DEFAULT_REGISTRY_PATH}")
    print(f"[INFO] Solver config path  : {DEFAULT_SOLVER_CONFIG_PATH}")
    print(f"[INFO] Output path         : {DEFAULT_OUTPUT_PATH}")

    instance_paths = collect_supported_instances(DEFAULT_INSTANCES_DIR)

    if not instance_paths:
        raise FileNotFoundError(
            f"No supported instance files were found in: {DEFAULT_INSTANCES_DIR}"
        )

    df = build_solver_runtime_table(
        instance_paths=instance_paths,
        registry_path=DEFAULT_REGISTRY_PATH,
        solver_config_path=DEFAULT_SOLVER_CONFIG_PATH,
    )

    print(f"[OK] Solver runtime table saved to: {DEFAULT_OUTPUT_PATH}")
    print(f"[INFO] Rows: {len(df)}")
    print(f"[INFO] Columns: {len(df.columns)}")

    print("\n[INFO] Preview:")
    print(df.head())


if __name__ == "__main__":
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    _run_standalone()
