"""
Iteratively generate SDP instances to fill the largest empty regions.

The loop starts from the current Explore coordinates, finds the farthest point
inside the Instance Space outline, generates one candidate for that point,
adds the candidate to temporary coordinates/metadata, and repeats until the
largest nearest-instance distance is below the user threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.genetic_algorithms.fill_empty_space import (
    DEFAULT_BUILD_DIR,
    DEFAULT_EXPLORE_DIR,
    DEFAULT_FEATURES_CONFIG,
    DEFAULT_OUTPUT_DIR,
    INSTANCE_DEST_DIR,
    _dark_scatter_plot,
    _default_coordinates_csv,
    _find_default_metadata_test_template,
    _load_coordinates_csv,
    _load_instance_space_outline,
    _normalize_common_columns,
)
from tools.genetic_algorithms.generate_instance_for_target import (
    GenerationResult,
    InstanceSpaceContext,
    ModelMatProjector,
    generate_instance_for_target,
)
from tools.isa.analyze_explore_empty_space import (
    _convex_hull,
    _point_in_polygon,
)

DEFAULT_MULTIPLE_OUTPUT_DIR = DEFAULT_OUTPUT_DIR.parent / "fill_empty_space_multiple"


def _make_grid(
    min_z1: float,
    max_z1: float,
    min_z2: float,
    max_z2: float,
    grid_size: int,
) -> list[tuple[float, float]]:
    if grid_size < 2:
        raise ValueError("grid_size must be at least 2.")

    return [
        (x, y)
        for x in np.linspace(min_z1, max_z1, grid_size)
        for y in np.linspace(min_z2, max_z2, grid_size)
    ]


def _nearest_distance(
    x: float,
    y: float,
    points: list[tuple[float, float]],
) -> float:
    if not points:
        return float("inf")
    arr = np.asarray(points, dtype=float)
    diffs = arr - np.array([x, y], dtype=float)
    return float(np.sqrt((diffs ** 2).sum(axis=1).min()))


def _closed_polygon_from_outline(
    outline: pd.DataFrame | None,
    coords: pd.DataFrame,
) -> list[tuple[float, float]]:
    if outline is not None and not outline.empty:
        outline = _normalize_common_columns(outline.copy())
        polygon = list(zip(outline["z_1"].astype(float), outline["z_2"].astype(float)))
    else:
        polygon = _convex_hull(
            list(zip(coords["z_1"].astype(float), coords["z_2"].astype(float)))
        )

    if polygon and polygon[0] != polygon[-1]:
        polygon.append(polygon[0])

    return polygon


def _dist_to_polygon_boundary(
    x: float, y: float, polygon: list[tuple[float, float]]
) -> float:
    """Minimum distance from (x, y) to any edge segment of the polygon."""
    min_d = float("inf")
    n = len(polygon) - 1
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[i + 1]
        abx, aby = bx - ax, by - ay
        ab2 = abx * abx + aby * aby
        if ab2 < 1e-24:
            d = math.sqrt((x - ax) ** 2 + (y - ay) ** 2)
        else:
            t = max(0.0, min(1.0, ((x - ax) * abx + (y - ay) * aby) / ab2))
            px, py = ax + t * abx, ay + t * aby
            d = math.sqrt((x - px) ** 2 + (y - py) ** 2)
        if d < min_d:
            min_d = d
    return min_d


def _find_farthest_point(
    coords: pd.DataFrame,
    outline: pd.DataFrame | None,
    grid_size: int,
) -> dict[str, float]:
    coords = _normalize_common_columns(coords.copy())
    pts_arr = np.column_stack([
        coords["z_1"].astype(float).values,
        coords["z_2"].astype(float).values,
    ])
    polygon = _closed_polygon_from_outline(outline, coords)
    if len(polygon) < 4:
        raise ValueError("Could not build a valid Instance Space outline.")

    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    x_range = max(xs) - min(xs)
    y_range = max(ys) - min(ys)
    # Auto margin: 4 % of the bounding-box diagonal so targets can't sit
    # right on the outline edge.
    border_margin = 0.04 * math.sqrt(x_range ** 2 + y_range ** 2)

    grid = np.array(_make_grid(min(xs), max(xs), min(ys), max(ys), grid_size))

    # Keep only points that are inside AND at least border_margin from the edge.
    inside_with_margin = np.array([
        _point_in_polygon(x, y, polygon)
        and _dist_to_polygon_boundary(x, y, polygon) >= border_margin
        for x, y in grid
    ])
    inside = grid[inside_with_margin]

    if len(inside) == 0:
        # Fallback: relax the margin so we always return something.
        inside_mask = np.array([_point_in_polygon(x, y, polygon) for x, y in grid])
        inside = grid[inside_mask]
        if len(inside) == 0:
            raise ValueError("No grid point was found inside the Instance Space outline.")

    tree = cKDTree(pts_arr)
    distances, _ = tree.query(inside, k=1)

    best_idx = int(np.argmax(distances))
    return {
        "z_1": float(inside[best_idx, 0]),
        "z_2": float(inside[best_idx, 1]),
        "nearest_instance_distance": float(distances[best_idx]),
    }


def _load_first_explore_target(
    explore_dir: Path,
    coords: pd.DataFrame,
) -> dict[str, Any] | None:
    targets_path = explore_dir / "empty_space_targets.csv"
    if not targets_path.exists():
        return None

    targets = pd.read_csv(targets_path)
    if targets.empty or not {"z_1", "z_2"}.issubset(targets.columns):
        return None

    if "target_id" in targets.columns:
        target_id_series = targets["target_id"].astype(str)
        preferred = targets[target_id_series == "empty_space_001"]
        row = preferred.iloc[0] if not preferred.empty else targets.iloc[0]
        target_id = str(row.get("target_id", "empty_space_001"))
    else:
        row = targets.iloc[0]
        target_id = "empty_space_001"

    z1 = float(row["z_1"])
    z2 = float(row["z_2"])
    nearest_distance_value = row.get("nearest_instance_distance", float("nan"))
    nearest_distance = (
        float("nan")
        if pd.isna(nearest_distance_value)
        else float(nearest_distance_value)
    )
    if math.isnan(nearest_distance):
        normalized = _normalize_common_columns(coords.copy())
        points = list(zip(normalized["z_1"].astype(float), normalized["z_2"].astype(float)))
        nearest_distance = _nearest_distance(z1, z2, points)

    return {
        "z_1": z1,
        "z_2": z2,
        "nearest_instance_distance": nearest_distance,
        "target_id": target_id,
        "source": str(targets_path.resolve()),
    }


def _plot_multiple_progress(
    initial_coords: pd.DataFrame,
    generated_rows: list[dict[str, Any]],
    outline: pd.DataFrame | None,
    out_path: Path,
) -> None:
    """Render cumulative progress: existing instances + all (target★ → generated●) pairs."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(7, 6))
    fig.patch.set_facecolor("#1e1e1e")
    ax.set_facecolor("#1e1e1e")

    initial_coords = _normalize_common_columns(initial_coords.copy())
    ax.scatter(
        initial_coords["z_1"], initial_coords["z_2"],
        s=22, color="#808080", alpha=0.75, zorder=2, label="Existing instances",
    )

    if outline is not None and not outline.empty:
        out = _normalize_common_columns(outline.copy()).dropna(subset=["z_1", "z_2"])
        if not out.empty:
            ax.plot(
                out["z_1"], out["z_2"],
                color="#d8d8d8", linewidth=2.0, alpha=0.9, zorder=3,
                label="Instance space outline",
            )

    n = len(generated_rows)
    for i, row in enumerate(generated_rows):
        tz1, tz2 = float(row["target_z1"]), float(row["target_z2"])
        gz1, gz2 = float(row["best_z1"]),   float(row["best_z2"])
        is_latest = (i == n - 1)
        alpha = 0.45 + 0.55 * (i / max(n - 1, 1))

        ax.plot(
            [tz1, gz1], [tz2, gz2],
            linestyle="--", linewidth=1.1, color="#bbbbbb",
            alpha=0.55 * alpha, zorder=4,
        )
        ax.scatter(
            [tz1], [tz2],
            s=200 if is_latest else 130,
            color="#f0c040", marker="*", zorder=5,
            edgecolors="white", linewidths=0.8,
            alpha=1.0 if is_latest else alpha,
            label="Target" if i == 0 else None,
        )
        ax.scatter(
            [gz1], [gz2],
            s=120 if is_latest else 75,
            color="#e05050", marker="o", zorder=6,
            edgecolors="white", linewidths=0.8,
            alpha=1.0 if is_latest else alpha,
            label="Generated" if i == 0 else None,
        )

    ax.set_title(
        f"Instance Space — progress ({n} generated)",
        color="#f3f3f3", fontsize=13, fontweight="bold", pad=10,
    )
    ax.set_xlabel("z₁", color="#a8a8a8", fontsize=11)
    ax.set_ylabel("z₂", color="#a8a8a8", fontsize=11)
    ax.tick_params(colors="#a8a8a8")
    ax.grid(True, alpha=0.1, color="#555555")
    for spine in ax.spines.values():
        spine.set_edgecolor("#3a3a3a")
    ax.legend(loc="best", fontsize=8, facecolor="#2d2d30",
              edgecolor="#3a3a3a", labelcolor="#f3f3f3")
    fig.tight_layout()
    fig.savefig(out_path, dpi=110, bbox_inches="tight", facecolor="#1e1e1e")
    plt.close(fig)


def _copy_generated_to_library(
    candidates: list[dict[str, Any]],
    target_dir: Path = INSTANCE_DEST_DIR,
) -> list[dict[str, str]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []

    for candidate in candidates:
        src = Path(candidate["candidate_path"])
        if not src.exists():
            raise FileNotFoundError(f"Generated candidate not found: {src}")

        dest = target_dir / src.name
        counter = 2
        while dest.exists():
            dest = target_dir / f"{src.stem}_v{counter}{src.suffix}"
            counter += 1

        shutil.copy2(src, dest)
        copied.append(
            {
                "source": str(src.resolve()),
                "destination": str(dest.resolve()),
                "instance_name": dest.name,
            }
        )

    return copied


def _append_metadata_row(
    metadata_working: pd.DataFrame,
    candidate_metadata: pd.DataFrame,
    candidate_name: str,
) -> pd.DataFrame:
    source_row = candidate_metadata.iloc[0].to_dict()
    lower_to_key = {str(key).lower(): key for key in source_row}

    row: dict[str, Any] = {}
    for column in metadata_working.columns:
        lower = str(column).lower()
        if lower in ("instance", "instances", "row"):
            row[column] = candidate_name
        elif lower == "source":
            source_key = lower_to_key.get("source")
            row[column] = (
                source_row.get(source_key)
                if source_key is not None
                else "Genetically Generated to Fill Empty Space"
            )
        else:
            source_key = lower_to_key.get(lower)
            row[column] = source_row.get(source_key) if source_key is not None else None

    return pd.concat([metadata_working, pd.DataFrame([row])], ignore_index=True)


def fill_empty_space_multiple(
    *,
    max_nearest_distance: float,
    explore_dir: Path = DEFAULT_EXPLORE_DIR,
    build_dir: Path = DEFAULT_BUILD_DIR,
    output_dir: Path = DEFAULT_MULTIPLE_OUTPUT_DIR,
    metadata_test_template_csv: Path | None = None,
    instances_dir: Path | None = None,
    config: Path | None = None,
    model_mat: Path | None = None,
    outline_csv: Path | None = None,
    grid_size: int = 80,
    max_iterations: int = 10,
    mu: int = 2,
    lam: int = 4,
    generations: int = 20,
    stall_generations: int = 6,
    tolerance: float = 0.05,
    seed: int = 42,
    copy_to_library: bool = False,
) -> dict[str, Any]:
    if max_nearest_distance < 0:
        raise ValueError("max_nearest_distance must be non-negative.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"multiple_{timestamp}"
    candidates_dir = run_dir / "candidates"
    run_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    coordinates_csv = _default_coordinates_csv(build_dir, explore_dir)
    coords = _load_coordinates_csv(coordinates_csv)
    initial_coords = coords.copy()

    outline = _load_instance_space_outline(build_dir, explore_dir, outline_csv)
    metadata_test_template_csv = (
        metadata_test_template_csv
        or _find_default_metadata_test_template(build_dir, explore_dir)
    )
    metadata_working = pd.read_csv(metadata_test_template_csv)

    instances_dir = instances_dir or (PROJECT_ROOT / "data" / "instances")
    config = config or DEFAULT_FEATURES_CONFIG
    model_mat = model_mat or (build_dir / "model.mat")
    if not model_mat.exists():
        model_mat = explore_dir / "model.mat"

    plot_initial_path = run_dir / "plot_initial.png"
    plot_final_path = run_dir / "plot_final.png"
    metadata_working_path = run_dir / "metadata_test_multiple_working.csv"
    coordinates_working_path = run_dir / "coordinates_multiple_working.csv"
    result_json_path = run_dir / "result.json"

    _dark_scatter_plot(
        coords=initial_coords,
        out_path=plot_initial_path,
        title="Instance Space - initial",
        outline=outline,
    )

    print("=" * 72)
    print("FILL EMPTY SPACE MULTIPLE")
    print("=" * 72)
    print(f"[INFO] Max nearest distance : {max_nearest_distance:.6f}")
    print(f"[INFO] Grid size            : {grid_size}")
    print(f"[INFO] Max iterations       : {max_iterations}")
    print(f"[INFO] GA budget            : mu={mu}, lambda={lam}, generations={generations}")
    print(f"[INFO] GA stall generations : {stall_generations}")
    print(f"[INFO] Coordinates CSV      : {coordinates_csv}")
    print(f"[INFO] Metadata template    : {metadata_test_template_csv}")
    print(f"[INFO] Run dir              : {run_dir}")
    print("[INFO] Initial map written  : " f"{plot_initial_path}", flush=True)

    instance_paths: dict[str, Path] = {}
    generated_rows: list[dict[str, Any]] = []
    generated_coord_rows: list[dict[str, Any]] = []
    mutation_weight_prior: dict[str, float] | None = None
    loop_polygon = _closed_polygon_from_outline(outline, coords)
    loop_polygon = loop_polygon if len(loop_polygon) >= 4 else None
    consecutive_out_of_bounds = 0
    first_explore_target = _load_first_explore_target(explore_dir, coords)
    if first_explore_target is not None:
        print(
            "[INFO] First objective source : "
            f"{first_explore_target['target_id']} from empty_space_targets.csv",
            flush=True,
        )
    else:
        print(
            "[INFO] First objective source : dynamic farthest-point search",
            flush=True,
        )

    for iteration in range(1, max_iterations + 1):
        if iteration == 1 and first_explore_target is not None:
            target = first_explore_target
            target_source = "explore target"
        else:
            target = _find_farthest_point(coords, outline, grid_size)
            target_source = "dynamic farthest point"
        nearest_distance = target["nearest_instance_distance"]
        remaining = nearest_distance - max_nearest_distance
        current_instances = len(coords)
        _dark_scatter_plot(
            coords=coords,
            out_path=plot_initial_path,
            title="Instance Space - current objective",
            target_z=(target["z_1"], target["z_2"]),
            target_label=f"Objective {iteration:03d}",
            outline=outline,
        )
        print(
            "\n"
            f"[ITER {iteration:03d}] Current instances        : {current_instances}\n"
            f"[ITER {iteration:03d}] Objective source         : {target_source}\n"
            f"[ITER {iteration:03d}] Objective point z        : "
            f"({target['z_1']:.6f}, {target['z_2']:.6f})\n"
            f"[ITER {iteration:03d}] Max nearest distance    : {nearest_distance:.6f}\n"
            f"[ITER {iteration:03d}] Stop threshold          : {max_nearest_distance:.6f}\n"
            f"[ITER {iteration:03d}] Distance over threshold : {remaining:.6f}\n"
            f"[ITER {iteration:03d}] Current target plot      : {plot_initial_path}",
            flush=True,
        )

        if nearest_distance <= max_nearest_distance:
            print("[STOP] Target distance threshold reached.", flush=True)
            break

        candidate_name = f"multiple_{timestamp}_{iteration:03d}.dat-s"
        candidate_path = candidates_dir / candidate_name
        print(
            f"[ITER {iteration:03d}] Running GA candidate     : {candidate_name}",
            flush=True,
        )

        context = InstanceSpaceContext(
            coordinates_df=coords,
            metadata_test_df=metadata_working,
            instances_dir=instances_dir,
            features_config_path=config,
            projector=ModelMatProjector(model_mat),
            instance_paths=instance_paths,
            outline_polygon=loop_polygon,
        )

        result: GenerationResult = generate_instance_for_target(
            context=context,
            target_z1=target["z_1"],
            target_z2=target["z_2"],
            output_path=candidate_path,
            mu=mu,
            lam=lam,
            generations=generations,
            tolerance=tolerance,
            seed=seed + iteration - 1,
            verbose_children=False,
            stall_generations=stall_generations,
            mutation_weight_prior=mutation_weight_prior,
        )
        mutation_weight_prior = dict(result.mutation_weights)

        print(
            f"[ITER {iteration:03d}] Candidate projected z   : "
            f"({result.best_z1:.6f}, {result.best_z2:.6f})\n"
            f"[ITER {iteration:03d}] Candidate fitness       : {result.best_fitness:.6f}\n"
            f"[ITER {iteration:03d}] Seed instance           : {result.seed_instance}",
            flush=True,
        )

        # Reject candidates that project outside the instance space boundary.
        if loop_polygon is not None and not _point_in_polygon(
            result.best_z1, result.best_z2, loop_polygon
        ):
            consecutive_out_of_bounds += 1
            print(
                f"[ITER {iteration:03d}] Candidate is outside the instance space boundary "
                f"— skipping ({consecutive_out_of_bounds} consecutive).",
                flush=True,
            )
            if consecutive_out_of_bounds >= 3:
                print("[STOP] Too many consecutive out-of-bounds results.", flush=True)
                break
            continue
        consecutive_out_of_bounds = 0

        instance_paths[candidate_name] = candidate_path

        metadata_working = _append_metadata_row(
            metadata_working=metadata_working,
            candidate_metadata=result.metadata_test_candidate_df,
            candidate_name=candidate_name,
        )

        coord_row = {
            "Instance": candidate_name,
            "z_1": result.best_z1,
            "z_2": result.best_z2,
        }
        coords = pd.concat([coords, pd.DataFrame([coord_row])], ignore_index=True)
        generated_coord_rows.append(coord_row)
        print(
            f"[ITER {iteration:03d}] Temporary map size      : {len(coords)} instances",
            flush=True,
        )

        generated_rows.append(
            {
                "iteration": iteration,
                "target_z1": target["z_1"],
                "target_z2": target["z_2"],
                "target_nearest_instance_distance": nearest_distance,
                "target_source": target_source,
                "target_id": target.get("target_id"),
                "candidate_path": str(candidate_path.resolve()),
                "candidate_name": candidate_name,
                "best_fitness": result.best_fitness,
                "best_z1": result.best_z1,
                "best_z2": result.best_z2,
                "seed_instance": result.seed_instance,
                "generations_run": result.generations_run,
                "mutation_weights": result.mutation_weights,
            }
        )

        _plot_multiple_progress(
            initial_coords=initial_coords,
            generated_rows=generated_rows,
            outline=outline,
            out_path=plot_final_path,
        )
        print(f"[PROGRESS PLOT] {plot_final_path.resolve()}", flush=True)

    final_target = _find_farthest_point(coords, outline, grid_size)
    print(
        "\n"
        f"[INFO] Final max nearest distance : "
        f"{final_target['nearest_instance_distance']:.6f}",
        flush=True,
    )
    generated_points_df = pd.DataFrame(generated_coord_rows)

    _dark_scatter_plot(
        coords=coords,
        out_path=plot_final_path,
        title="Instance Space - after multiple generation",
        generated_points=generated_points_df,
        outline=outline,
        generated_label="Generated instances",
    )

    metadata_working.to_csv(metadata_working_path, index=False)
    coords.to_csv(coordinates_working_path, index=False)

    copied = _copy_generated_to_library(generated_rows) if copy_to_library else []
    result_payload = {
        "run_dir": str(run_dir.resolve()),
        "max_nearest_distance": max_nearest_distance,
        "final_nearest_instance_distance": final_target["nearest_instance_distance"],
        "stopped_because_threshold_reached": (
            final_target["nearest_instance_distance"] <= max_nearest_distance
        ),
        "iterations_run": len(generated_rows),
        "generated_candidates": generated_rows,
        "copied_to_library": copied,
        "plot_initial": str(plot_initial_path.resolve()),
        "plot_final": str(plot_final_path.resolve()),
        "metadata_test_working_csv": str(metadata_working_path.resolve()),
        "coordinates_working_csv": str(coordinates_working_path.resolve()),
        "coordinates_source_csv": str(coordinates_csv.resolve()),
        "metadata_template_csv": str(metadata_test_template_csv.resolve()),
        "model_mat": str(model_mat.resolve()),
        "generated_at": datetime.now().isoformat(),
        "ga_params": {
            "mu": mu,
            "lam": lam,
            "generations": generations,
            "stall_generations": stall_generations,
            "tolerance": tolerance,
            "seed": seed,
        },
        "search_params": {
            "grid_size": grid_size,
            "max_iterations": max_iterations,
        },
    }

    with open(result_json_path, "w", encoding="utf-8") as fh:
        json.dump(result_payload, fh, indent=4)

    print("\n" + "=" * 72)
    print("FINAL RESULT")
    print("=" * 72)
    print(f"[DONE] Generated instances    : {len(generated_rows)}")
    print(f"[DONE] Final nearest distance : {final_target['nearest_instance_distance']:.6f}")
    print(f"[DONE] Initial plot           : {plot_initial_path}")
    print(f"[DONE] Final plot             : {plot_final_path}")
    print(f"[DONE] Result JSON            : {result_json_path}")

    return result_payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate multiple instances until the largest empty-space distance is small enough.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--max-nearest-distance", type=float, required=True)
    parser.add_argument("--explore-dir", type=Path, default=DEFAULT_EXPLORE_DIR)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_MULTIPLE_OUTPUT_DIR)
    parser.add_argument("--metadata-test-template-csv", type=Path, default=None)
    parser.add_argument("--instances-dir", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--model-mat", type=Path, default=None)
    parser.add_argument("--outline-csv", type=Path, default=None)
    parser.add_argument("--grid-size", type=int, default=80)
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--mu", type=int, default=2)
    parser.add_argument("--lam", type=int, default=4)
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--stall-generations", type=int, default=6)
    parser.add_argument("--tolerance", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--copy-to-library", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    fill_empty_space_multiple(
        max_nearest_distance=args.max_nearest_distance,
        explore_dir=args.explore_dir,
        build_dir=args.build_dir,
        output_dir=args.output_dir,
        metadata_test_template_csv=args.metadata_test_template_csv,
        instances_dir=args.instances_dir,
        config=args.config,
        model_mat=args.model_mat,
        outline_csv=args.outline_csv,
        grid_size=args.grid_size,
        max_iterations=args.max_iterations,
        mu=args.mu,
        lam=args.lam,
        generations=args.generations,
        stall_generations=args.stall_generations,
        tolerance=args.tolerance,
        seed=args.seed,
        copy_to_library=args.copy_to_library,
    )


if __name__ == "__main__":
    main()
