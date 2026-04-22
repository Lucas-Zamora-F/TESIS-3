"""
Generate one SDP instance for a user-selected point in the Instance Space.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.genetic_algorithms.fill_empty_space import (
    DEFAULT_BUILD_DIR,
    DEFAULT_EXPLORE_DIR,
    DEFAULT_FEATURES_CONFIG,
    DEFAULT_OUTPUT_DIR,
    _dark_scatter_plot,
    _default_coordinates_csv,
    _find_default_metadata_test_template,
    _load_coordinates_csv,
    _load_instance_space_outline,
)
from tools.genetic_algorithms.generate_instance_for_target import (
    InstanceSpaceContext,
    ModelMatProjector,
    generate_instance_for_target,
)

DEFAULT_POINT_OUTPUT_DIR = DEFAULT_OUTPUT_DIR.parent / "fill_point_target"
POINT_TARGET_DEST_DIR = (
    PROJECT_ROOT / "data" / "instances" / "genetic generated" / "point target"
)


def _copy_candidate_to_instance_library(candidate_path: Path, target_id: str) -> Path:
    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate file not found: {candidate_path}")

    POINT_TARGET_DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest_name = f"{target_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.dat-s"
    dest_path = POINT_TARGET_DEST_DIR / dest_name

    counter = 2
    while dest_path.exists():
        dest_path = INSTANCE_DEST_DIR / f"{Path(dest_name).stem}_v{counter}.dat-s"
        counter += 1

    shutil.copy2(candidate_path, dest_path)
    return dest_path


def fill_point_target(
    *,
    target_z1: float,
    target_z2: float,
    target_id: str | None = None,
    explore_dir: Path = DEFAULT_EXPLORE_DIR,
    build_dir: Path = DEFAULT_BUILD_DIR,
    output_dir: Path = DEFAULT_POINT_OUTPUT_DIR,
    metadata_test_template_csv: Path | None = None,
    instances_dir: Path | None = None,
    config: Path | None = None,
    model_mat: Path | None = None,
    mu: int = 10,
    lam: int = 30,
    generations: int = 60,
    tolerance: float = 0.05,
    seed: int = 42,
) -> dict[str, Any]:
    target_id = target_id or f"point_target_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = output_dir / target_id
    run_dir.mkdir(parents=True, exist_ok=True)

    coordinates_csv = _default_coordinates_csv(build_dir, explore_dir)
    coords = _load_coordinates_csv(coordinates_csv)
    outline = _load_instance_space_outline(build_dir, explore_dir)

    metadata_test_template_csv = (
        metadata_test_template_csv
        or _find_default_metadata_test_template(build_dir, explore_dir)
    )
    metadata_test_df = pd.read_csv(metadata_test_template_csv)

    instances_dir = instances_dir or (PROJECT_ROOT / "data" / "instances")
    config = config or DEFAULT_FEATURES_CONFIG
    model_mat = model_mat or (build_dir / "model.mat")
    if not model_mat.exists():
        model_mat = explore_dir / "model.mat"

    candidate_path = run_dir / "candidate.dat-s"
    plot_before_path = run_dir / "plot_before.png"
    plot_after_path = run_dir / "plot_after.png"
    result_json_path = run_dir / "result.json"

    print("=" * 72)
    print("FILL POINT TARGET")
    print("=" * 72)
    print(f"[INFO] Target id     : {target_id}")
    print(f"[INFO] Target coords : ({target_z1:.6f}, {target_z2:.6f})")
    print(f"[INFO] Run dir       : {run_dir}")

    _dark_scatter_plot(
        coords=coords,
        out_path=plot_before_path,
        title="Instance Space - selected target",
        target_z=(target_z1, target_z2),
        outline=outline,
        target_label=f"Target: {target_id}",
    )

    context = InstanceSpaceContext(
        coordinates_df=coords,
        metadata_test_df=metadata_test_df,
        instances_dir=instances_dir,
        features_config_path=config,
        projector=ModelMatProjector(model_mat),
    )

    generation_result = generate_instance_for_target(
        context=context,
        target_z1=target_z1,
        target_z2=target_z2,
        output_path=candidate_path,
        mu=mu,
        lam=lam,
        generations=generations,
        tolerance=tolerance,
        seed=seed,
    )

    generated_row = pd.DataFrame(
        [
            {
                "Instance": candidate_path.name,
                "z_1": generation_result.best_z1,
                "z_2": generation_result.best_z2,
            }
        ]
    )

    _dark_scatter_plot(
        coords=coords,
        out_path=plot_after_path,
        title="Instance Space - selected target vs generated instance",
        target_z=(target_z1, target_z2),
        generated_points=generated_row,
        outline=outline,
        target_label=f"Target: {target_id}",
        generated_label="Generated instance",
    )

    features_path = run_dir / "candidate_features.csv"
    metadata_row_path = run_dir / "candidate_metadata_test_row.csv"
    generation_result.features_df.to_csv(features_path, index=False)
    generation_result.metadata_test_candidate_df.to_csv(metadata_row_path, index=False)

    result = {
        "target_id": target_id,
        "target_z1": target_z1,
        "target_z2": target_z2,
        "best_fitness": generation_result.best_fitness,
        "best_z1": generation_result.best_z1,
        "best_z2": generation_result.best_z2,
        "candidate_path": str(candidate_path.resolve()),
        "seed_instance": generation_result.seed_instance,
        "generations_run": generation_result.generations_run,
        "candidate_features_csv": str(features_path.resolve()),
        "candidate_metadata_test_row_csv": str(metadata_row_path.resolve()),
        "plot_before": str(plot_before_path.resolve()),
        "plot_after": str(plot_after_path.resolve()),
        "generated_at": datetime.now().isoformat(),
        "ga_params": {
            "mu": mu,
            "lam": lam,
            "generations": generations,
            "tolerance": tolerance,
            "seed": seed,
        },
    }

    with open(result_json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=4)

    print("\n" + "=" * 72)
    print("FINAL RESULT")
    print("=" * 72)
    print(f"[DONE] Candidate   : {candidate_path}")
    print(f"[DONE] Result JSON : {result_json_path}")
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an SDP instance for a manually selected Instance Space point.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--target-z1", type=float, required=True)
    parser.add_argument("--target-z2", type=float, required=True)
    parser.add_argument("--target-id", default=None)
    parser.add_argument("--explore-dir", type=Path, default=DEFAULT_EXPLORE_DIR)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_POINT_OUTPUT_DIR)
    parser.add_argument("--metadata-test-template-csv", type=Path, default=None)
    parser.add_argument("--instances-dir", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--model-mat", type=Path, default=None)
    parser.add_argument("--mu", type=int, default=10)
    parser.add_argument("--lam", type=int, default=30)
    parser.add_argument("--generations", type=int, default=60)
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    fill_point_target(
        target_z1=args.target_z1,
        target_z2=args.target_z2,
        target_id=args.target_id,
        explore_dir=args.explore_dir,
        build_dir=args.build_dir,
        output_dir=args.output_dir,
        metadata_test_template_csv=args.metadata_test_template_csv,
        instances_dir=args.instances_dir,
        config=args.config,
        model_mat=args.model_mat,
        mu=args.mu,
        lam=args.lam,
        generations=args.generations,
        tolerance=args.tolerance,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
