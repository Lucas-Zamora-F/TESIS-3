"""
add_instance_to_metadata_test.py

Extract features and solver runtimes for a single instance and append
a new row to an existing metadata_test.csv.

Only the feature_ and algo_ columns already present in metadata_test are
computed, so no new columns are introduced.

Usage:
    python tools/isa/add_instance_to_metadata_test.py \
        --instance-path data/instances/sdplib/arch0.dat-s \
        --metadata-test-path matilda_out/explore_inputs/metadata_test.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from tools.isa.build_metadata.build_features_table import (
    import_extractor_from_path,
    parse_feature_configuration,
)
from tools.isa.build_metadata.build_solver_runtime_table import (
    DEFAULT_REGISTRY_PATH,
    DEFAULT_SOLVER_CONFIG_PATH,
    _import_wrapper_class,
    _safe_runtime,
    load_enabled_solvers,
)
from tools.features.instance_reader import instance_display_name

FEATURES_CONFIG_PATH = PROJECT_ROOT / "config" / "features_config.json"
INSTANCES_CONFIG_PATH = PROJECT_ROOT / "config" / "instances_config.json"


# ── Source detection ───────────────────────────────────────────────────────────

def _detect_source(instance_path: Path) -> str:
    path = instance_path.resolve()

    if "sdplib" in str(path):
        return "SDPLIB"

    if "DIMACS" in str(path):
        return "DIMACS"

    if "genetic generated" in str(path) and "point target" in str(path):
        return "Genetically Generated from Point Target"

    if "genetic generated" in str(path):
        return "Genetically Generated to Fill Empty Space"

    return "Unknown"

# ── Feature extraction (no file save side-effect) ─────────────────────────────

def _extract_features(instance_path: Path, needed_cols: set[str]) -> dict[str, object]:
    """Extract only the feature_ columns present in metadata_test."""
    _, available_features, group_to_enabled = parse_feature_configuration(FEATURES_CONFIG_PATH)

    result: dict[str, object] = {}
    for group_name, enabled_group_features in group_to_enabled.items():
        group_needed = [f for f in enabled_group_features if f in needed_cols]
        if not group_needed:
            continue

        extractor_path = available_features[group_name]["extractor"]
        extractor = import_extractor_from_path(extractor_path)

        print(f"[INFO] Extracting '{group_name}' ({len(group_needed)} features) ...")
        try:
            feature_dict = extractor(instance_path)
        except MemoryError:
            print(f"[WARN] Not enough memory for group '{group_name}' — filling with NaN.")
            feature_dict = {}

        for fname in group_needed:
            result[fname] = feature_dict.get(fname, None)

    return result


# ── Solver runtime extraction (no file save side-effect) ──────────────────────

def _extract_solver_runtimes(instance_path: Path, needed_cols: set[str]) -> dict[str, object]:
    """Extract only the algo_ columns present in metadata_test."""
    enabled_solver_info = load_enabled_solvers(DEFAULT_REGISTRY_PATH)
    needed_solvers = {
        name: info
        for name, info in enabled_solver_info.items()
        if f"algo_{name}" in needed_cols
    }

    if not needed_solvers:
        return {}

    result: dict[str, object] = {}
    wrappers: dict = {}
    try:
        for solver_name, solver_info in needed_solvers.items():
            module_name = solver_info.get("wrapper_module")
            class_name = solver_info.get("wrapper_class")
            if not module_name or not class_name:
                continue
            wrapper_class = _import_wrapper_class(module_name, class_name)
            wrappers[solver_name] = wrapper_class(
                config_path=str(DEFAULT_SOLVER_CONFIG_PATH),
                project_root=str(PROJECT_ROOT),
            )

        for solver_name, wrapper in wrappers.items():
            print(f"[INFO] Running solver '{solver_name}' ...")
            try:
                solve_result = wrapper.solve(str(instance_path))
                result[f"algo_{solver_name}"] = _safe_runtime(solve_result)
            except Exception as exc:
                print(f"[WARN] Solver '{solver_name}' failed: {exc}")
                result[f"algo_{solver_name}"] = None
    finally:
        for wrapper in wrappers.values():
            close_fn = getattr(wrapper, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass

    return result


# ── Main entry point ──────────────────────────────────────────────────────────

def add_instance(instance_path: Path, metadata_test_path: Path) -> None:
    instance_path = instance_path.resolve()

    if not instance_path.exists():
        raise FileNotFoundError(f"Instance not found: {instance_path}")

    if not metadata_test_path.exists():
        raise FileNotFoundError(f"metadata_test.csv not found: {metadata_test_path}")

    existing_df = pd.read_csv(metadata_test_path)

    display_name = instance_display_name(instance_path)
    print(f"[INFO] Instance : {display_name}")

    inst_col = next((c for c in existing_df.columns if c.lower() == "instances"), None)
    if inst_col and display_name in existing_df[inst_col].astype(str).values:
        print(f"[WARN] '{display_name}' is already in metadata_test.csv — skipping.")
        return

    feature_cols = {c for c in existing_df.columns if c.startswith("feature_")}
    algo_cols = {c for c in existing_df.columns if c.startswith("algo_")}
    print(f"[INFO] Features needed : {len(feature_cols)}")
    print(f"[INFO] Solver columns  : {len(algo_cols)}")

    source = _detect_source(instance_path)
    print(f"[INFO] Source          : {source}")

    feature_values = _extract_features(instance_path, feature_cols)
    algo_values = _extract_solver_runtimes(instance_path, algo_cols)

    new_row: dict[str, object] = {"instances": display_name, "source": source}
    for col in existing_df.columns:
        if col in ("instances", "source"):
            continue
        if col in feature_values:
            new_row[col] = feature_values[col]
        elif col in algo_values:
            new_row[col] = algo_values[col]
        else:
            new_row[col] = None

    result_df = pd.concat([existing_df, pd.DataFrame([new_row])], ignore_index=True, sort=False)
    result_df.to_csv(metadata_test_path, index=False)

    feat_ok = sum(1 for v in feature_values.values() if v is not None)
    algo_ok = sum(1 for v in algo_values.values() if v is not None)
    print(f"[OK] Added '{display_name}' to {metadata_test_path.name}")
    print(f"[INFO] Features  : {feat_ok}/{len(feature_cols)} extracted")
    print(f"[INFO] Solvers   : {algo_ok}/{len(algo_cols)} extracted")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract features/runtimes for a single instance and append to metadata_test.csv"
    )
    parser.add_argument("--instance-path", required=True, type=Path)
    parser.add_argument("--metadata-test-path", required=True, type=Path)
    args = parser.parse_args()
    add_instance(args.instance_path, args.metadata_test_path)


if __name__ == "__main__":
    main()
