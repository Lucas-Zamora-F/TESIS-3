from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Callable, Any, Iterable

import pandas as pd


FeatureExtractor = Callable[[str | Path], dict[str, Any]]


def load_features_config(config_path: str | Path) -> dict[str, Any]:
    """
    Carga y valida el archivo de configuración de features.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"No existe el archivo de configuración: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    if "enabled_features" not in config:
        raise KeyError("Falta 'enabled_features' en el JSON de configuración.")

    if "available_features" not in config:
        raise KeyError("Falta 'available_features' en el JSON de configuración.")

    if not isinstance(config["enabled_features"], list):
        raise TypeError("'enabled_features' debe ser una lista.")

    if not isinstance(config["available_features"], dict):
        raise TypeError("'available_features' debe ser un diccionario.")

    return config


def import_extractor_from_path(import_path: str) -> FeatureExtractor:
    """
    Importa dinámicamente un extractor desde un string tipo:
        tools.features.size_features.extract_size_features
    """
    if "." not in import_path:
        raise ValueError(f"Ruta de importación inválida: {import_path}")

    module_path, function_name = import_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    extractor = getattr(module, function_name)

    if not callable(extractor):
        raise TypeError(f"El extractor '{import_path}' no es callable.")

    return extractor


def collect_dat_s_instances(instances: str | Path | Iterable[str | Path]) -> list[Path]:
    """
    Permite recibir:
    - un directorio con .dat-s
    - una lista de rutas a instancias
    """
    if isinstance(instances, (str, Path)):
        instances_path = Path(instances)

        if instances_path.is_dir():
            instance_paths = sorted(instances_path.glob("*.dat-s"))
            if not instance_paths:
                raise FileNotFoundError(
                    f"No se encontraron archivos .dat-s en: {instances_path}"
                )
            return instance_paths

        if instances_path.is_file():
            return [instances_path]

        raise FileNotFoundError(f"No existe la ruta de instancias: {instances_path}")

    instance_paths = [Path(p) for p in instances]

    if not instance_paths:
        raise ValueError("La lista de instancias está vacía.")

    for path in instance_paths:
        if not path.exists():
            raise FileNotFoundError(f"No existe la instancia: {path}")
        if not path.is_file():
            raise ValueError(f"La ruta no es un archivo: {path}")

    return sorted(instance_paths)


def parse_feature_configuration(
    config_path: str | Path,
) -> tuple[set[str], dict[str, dict[str, Any]], dict[str, list[str]]]:
    """
    Retorna:
    - enabled_features_set
    - available_features raw
    - group_to_enabled_features: mapping grupo -> features habilitadas de ese grupo
    """
    config = load_features_config(config_path)

    enabled_features = config["enabled_features"]
    available_features = config["available_features"]

    enabled_features_set = set(enabled_features)

    if len(enabled_features_set) != len(enabled_features):
        raise ValueError("Hay features duplicadas en 'enabled_features'.")

    all_available_features: set[str] = set()
    feature_to_group: dict[str, str] = {}

    for group_name, group_info in available_features.items():
        if not isinstance(group_info, dict):
            raise TypeError(
                f"El grupo '{group_name}' debe ser un objeto con 'extractor' y 'features'."
            )

        if "extractor" not in group_info:
            raise KeyError(f"Falta 'extractor' en el grupo '{group_name}'.")

        if "features" not in group_info:
            raise KeyError(f"Falta 'features' en el grupo '{group_name}'.")

        if not isinstance(group_info["features"], list):
            raise TypeError(f"'features' del grupo '{group_name}' debe ser una lista.")

        for feature_name in group_info["features"]:
            if feature_name in all_available_features:
                raise ValueError(
                    f"La feature '{feature_name}' está repetida en más de un grupo."
                )
            all_available_features.add(feature_name)
            feature_to_group[feature_name] = group_name

    unknown_enabled = enabled_features_set - all_available_features
    if unknown_enabled:
        raise ValueError(
            "Las siguientes features habilitadas no existen en 'available_features': "
            + ", ".join(sorted(unknown_enabled))
        )

    group_to_enabled_features: dict[str, list[str]] = {}

    for feature_name in enabled_features:
        group_name = feature_to_group[feature_name]
        group_to_enabled_features.setdefault(group_name, []).append(feature_name)

    return enabled_features_set, available_features, group_to_enabled_features


def build_features_table(
    instances: str | Path | Iterable[str | Path],
    config_path: str | Path,
) -> pd.DataFrame:
    """
    Construye la tabla de features para las instancias indicadas,
    usando solo las features habilitadas en el archivo JSON.
    """
    instance_paths = collect_dat_s_instances(instances)
    _, available_features, group_to_enabled_features = parse_feature_configuration(
        config_path
    )

    rows: list[dict[str, Any]] = []

    for instance_path in instance_paths:
        row: dict[str, Any] = {"Instance": instance_path.name}

        for group_name, enabled_group_features in group_to_enabled_features.items():
            extractor_path = available_features[group_name]["extractor"]
            extractor = import_extractor_from_path(extractor_path)

            feature_dict = extractor(instance_path)

            if not isinstance(feature_dict, dict):
                raise TypeError(
                    f"El extractor '{extractor_path}' no retornó un dict para {instance_path.name}."
                )

            for feature_name in enabled_group_features:
                if feature_name not in feature_dict:
                    raise KeyError(
                        f"La feature '{feature_name}' fue habilitada en el grupo '{group_name}', "
                        f"pero el extractor '{extractor_path}' no la retornó."
                    )

                if feature_name in row:
                    raise ValueError(
                        f"La feature '{feature_name}' quedó duplicada en la instancia {instance_path.name}."
                    )

                row[feature_name] = feature_dict[feature_name]

        rows.append(row)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    feature_columns = sorted(col for col in df.columns if col != "Instance")
    return df[["Instance", *feature_columns]]


def save_features_table(df: pd.DataFrame, output_path: str | Path) -> Path:
    """
    Guarda la tabla de features en CSV.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path