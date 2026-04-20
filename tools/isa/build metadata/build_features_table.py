from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Callable, Any, Iterable

import pandas as pd


FeatureExtractor = Callable[[str | Path], dict[str, Any]]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "ISA metadata" / "intermediates" / "features_table.csv"
)


def load_features_config(config_path: str | Path) -> dict[str, Any]:
    """
    Load and validate the feature configuration file.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    if "enabled_features" not in config:
        raise KeyError("Missing 'enabled_features' in the configuration JSON.")

    if "available_features" not in config:
        raise KeyError("Missing 'available_features' in the configuration JSON.")

    if not isinstance(config["enabled_features"], list):
        raise TypeError("'enabled_features' must be a list.")

    if not isinstance(config["available_features"], dict):
        raise TypeError("'available_features' must be a dictionary.")

    return config


def import_extractor_from_path(import_path: str) -> FeatureExtractor:
    """
    Dynamically import an extractor from a string such as:
        tools.features.size_features.extract_size_features
    """
    if "." not in import_path:
        raise ValueError(f"Invalid import path: {import_path}")

    module_path, function_name = import_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    extractor = getattr(module, function_name)

    if not callable(extractor):
        raise TypeError(f"Extractor '{import_path}' is not callable.")

    return extractor


def collect_dat_s_instances(instances: str | Path | Iterable[str | Path]) -> list[Path]:
    """
    Accept:
    - a directory containing .dat-s files
    - a list of instance file paths
    - a single instance file path
    """
    if isinstance(instances, (str, Path)):
        instances_path = Path(instances)

        if instances_path.is_dir():
            instance_paths = sorted(instances_path.glob("*.dat-s"))
            if not instance_paths:
                raise FileNotFoundError(
                    f"No .dat-s files were found in: {instances_path}"
                )
            return instance_paths

        if instances_path.is_file():
            return [instances_path]

        raise FileNotFoundError(f"Instances path does not exist: {instances_path}")

    instance_paths = [Path(p) for p in instances]

    if not instance_paths:
        raise ValueError("The instance list is empty.")

    for path in instance_paths:
        if not path.exists():
            raise FileNotFoundError(f"Instance does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

    return sorted(instance_paths)


def parse_feature_configuration(
    config_path: str | Path,
) -> tuple[set[str], dict[str, dict[str, Any]], dict[str, list[str]]]:
    """
    Return:
    - enabled_features_set
    - available_features raw mapping
    - group_to_enabled_features: mapping group -> enabled features in that group
    """
    config = load_features_config(config_path)

    enabled_features = config["enabled_features"]
    available_features = config["available_features"]

    enabled_features_set = set(enabled_features)

    if len(enabled_features_set) != len(enabled_features):
        raise ValueError("Duplicate feature names found in 'enabled_features'.")

    all_available_features: set[str] = set()
    feature_to_group: dict[str, str] = {}

    for group_name, group_info in available_features.items():
        if not isinstance(group_info, dict):
            raise TypeError(
                f"Group '{group_name}' must be an object with 'extractor' and 'features'."
            )

        if "extractor" not in group_info:
            raise KeyError(f"Missing 'extractor' in group '{group_name}'.")

        if "features" not in group_info:
            raise KeyError(f"Missing 'features' in group '{group_name}'.")

        if not isinstance(group_info["features"], list):
            raise TypeError(f"'features' in group '{group_name}' must be a list.")

        for feature_name in group_info["features"]:
            if feature_name in all_available_features:
                raise ValueError(
                    f"Feature '{feature_name}' is repeated in more than one group."
                )
            all_available_features.add(feature_name)
            feature_to_group[feature_name] = group_name

    unknown_enabled = enabled_features_set - all_available_features
    if unknown_enabled:
        raise ValueError(
            "The following enabled features do not exist in 'available_features': "
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
    Build the features table for the given instances using only the
    enabled features from the JSON configuration.

    The resulting dataframe is also saved to:
        ISA metadata/intermediates/features_table.csv

    The CSV file is overwritten on every run.
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
                    f"Extractor '{extractor_path}' did not return a dict for "
                    f"{instance_path.name}."
                )

            for feature_name in enabled_group_features:
                if feature_name not in feature_dict:
                    raise KeyError(
                        f"Feature '{feature_name}' was enabled in group '{group_name}', "
                        f"but extractor '{extractor_path}' did not return it."
                    )

                if feature_name in row:
                    raise ValueError(
                        f"Feature '{feature_name}' is duplicated for instance "
                        f"{instance_path.name}."
                    )

                row[feature_name] = feature_dict[feature_name]

        rows.append(row)

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    feature_columns = sorted(col for col in df.columns if col != "Instance")
    df = df[["Instance", *feature_columns]]

    save_features_table(df, DEFAULT_OUTPUT_PATH)

    return df


def save_features_table(df: pd.DataFrame, output_path: str | Path) -> Path:
    """
    Save the features table to CSV.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def _run_standalone() -> None:
    """
    Run the module as a standalone script.
    """
    config_path = PROJECT_ROOT / "config" / "features_config.json"
    instances_dir = PROJECT_ROOT / "data" / "instances" / "sdplib"

    print("========================================")
    print("BUILD FEATURES TABLE")
    print("========================================")
    print(f"[INFO] Instances directory : {instances_dir}")
    print(f"[INFO] Config path         : {config_path}")
    print(f"[INFO] Output path         : {DEFAULT_OUTPUT_PATH}")

    df = build_features_table(
        instances=instances_dir,
        config_path=config_path,
    )

    print(f"[OK] Features table saved to: {DEFAULT_OUTPUT_PATH}")
    print(f"[INFO] Rows: {len(df)}")
    print(f"[INFO] Columns: {len(df.columns)}")

    print("\n[INFO] Preview:")
    print(df.head())


if __name__ == "__main__":
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    _run_standalone()