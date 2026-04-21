from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPLORE_BASE = PROJECT_ROOT / "matilda_out" / "explore"


def _find_explore_output_dir(explore_base: Path) -> Path:
    if not explore_base.exists():
        raise FileNotFoundError(f"Explore output folder not found: {explore_base}")

    if not (explore_base / "coordinates.csv").exists():
        raise FileNotFoundError(f"coordinates.csv not found in explore output folder: {explore_base}")

    return explore_base


def _read_coordinates(explore_run_dir: Path) -> pd.DataFrame:
    coordinates_path = explore_run_dir / "coordinates.csv"
    if not coordinates_path.exists():
        raise FileNotFoundError(f"coordinates.csv not found: {coordinates_path}")

    df = pd.read_csv(coordinates_path)
    required = {"z_1", "z_2"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"coordinates.csv is missing required columns: {sorted(missing)}")

    df = df.dropna(subset=["z_1", "z_2"]).copy()
    if df.empty:
        raise ValueError("coordinates.csv has no valid z_1/z_2 rows.")

    return df


def _nearest_distance_squared(x: float, y: float, points: list[tuple[float, float]]) -> float:
    return min((x - px) ** 2 + (y - py) ** 2 for px, py in points)


def _make_grid(
    min_z1: float,
    max_z1: float,
    min_z2: float,
    max_z2: float,
    grid_size: int,
) -> list[tuple[float, float]]:
    if grid_size < 2:
        raise ValueError("--grid-size must be at least 2.")

    step_z1 = (max_z1 - min_z1) / (grid_size - 1)
    step_z2 = (max_z2 - min_z2) / (grid_size - 1)
    return [
        (min_z1 + i * step_z1, min_z2 + j * step_z2)
        for i in range(grid_size)
        for j in range(grid_size)
    ]


def _cross(
    origin: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])


def _convex_hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique_points = sorted(set(points))
    if len(unique_points) <= 1:
        return unique_points

    lower: list[tuple[float, float]] = []
    for point in unique_points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(unique_points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def _point_in_polygon(
    x: float,
    y: float,
    polygon: list[tuple[float, float]],
) -> bool:
    if len(polygon) < 3:
        return False

    inside = False
    j = len(polygon) - 1
    for i, point_i in enumerate(polygon):
        xi, yi = point_i
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi
        if intersects:
            inside = not inside
        j = i
    return inside


def _select_targets(
    candidates: list[dict[str, float]],
    top_k: int,
    min_separation: float,
) -> list[dict[str, float]]:
    selected: list[dict[str, float]] = []

    for candidate in candidates:
        if len(selected) >= top_k:
            break

        if all(
            math.dist(
                (candidate["z_1"], candidate["z_2"]),
                (other["z_1"], other["z_2"]),
            )
            >= min_separation
            for other in selected
        ):
            selected.append(candidate)

    return selected


def find_empty_space_centers(
    explore_run_dir: Path | None = None,
    explore_base: Path = DEFAULT_EXPLORE_BASE,
    grid_size: int = 80,
    top_k: int = 10,
    padding_ratio: float = 0.05,
    min_separation_ratio: float = 0.12,
    inside_convex_hull: bool = True,
) -> tuple[Path, pd.DataFrame]:
    if explore_run_dir is None:
        explore_run_dir = _find_explore_output_dir(explore_base)

    coords = _read_coordinates(explore_run_dir)
    points = list(zip(coords["z_1"].astype(float), coords["z_2"].astype(float)))

    min_z1 = min(x for x, _ in points)
    max_z1 = max(x for x, _ in points)
    min_z2 = min(y for _, y in points)
    max_z2 = max(y for _, y in points)

    span_z1 = max_z1 - min_z1
    span_z2 = max_z2 - min_z2
    if span_z1 == 0 or span_z2 == 0:
        raise ValueError("The instance-space coordinates are degenerate.")

    pad_z1 = span_z1 * padding_ratio
    pad_z2 = span_z2 * padding_ratio
    min_z1 -= pad_z1
    max_z1 += pad_z1
    min_z2 -= pad_z2
    max_z2 += pad_z2

    diagonal = math.dist((min_z1, min_z2), (max_z1, max_z2))
    min_separation = diagonal * min_separation_ratio

    grid = _make_grid(min_z1, max_z1, min_z2, max_z2, grid_size)
    hull = _convex_hull(points)
    candidates: list[dict[str, float]] = []
    for x, y in grid:
        if inside_convex_hull and not _point_in_polygon(x, y, hull):
            continue
        nearest_dist_sq = _nearest_distance_squared(x, y, points)
        candidates.append(
            {
                "z_1": x,
                "z_2": y,
                "nearest_instance_distance": math.sqrt(nearest_dist_sq),
            }
        )

    candidates.sort(key=lambda row: row["nearest_instance_distance"], reverse=True)
    selected = _select_targets(candidates, top_k=top_k, min_separation=min_separation)

    output_df = pd.DataFrame(selected)
    output_df.insert(0, "target_id", [f"empty_space_{i:03d}" for i in range(1, len(output_df) + 1)])
    output_df["grid_size"] = grid_size
    output_df["min_separation"] = min_separation

    output_csv = explore_run_dir / "empty_space_targets.csv"
    output_json = explore_run_dir / "empty_space_targets.json"
    output_df.to_csv(output_csv, index=False)

    payload = {
        "explore_run_dir": str(explore_run_dir.resolve()),
        "source_coordinates": str((explore_run_dir / "coordinates.csv").resolve()),
        "method": "grid_maximin_nearest_instance_distance",
        "grid_size": grid_size,
        "top_k": top_k,
        "padding_ratio": padding_ratio,
        "min_separation_ratio": min_separation_ratio,
        "inside_convex_hull": inside_convex_hull,
        "bounds": {
            "min_z_1": min_z1,
            "max_z_1": max_z1,
            "min_z_2": min_z2,
            "max_z_2": max_z2,
        },
        "targets": output_df.to_dict(orient="records"),
    }
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)

    print("[OK] Empty-space targets written")
    print(f"[INFO] Explore run         : {explore_run_dir}")
    print(f"[INFO] CSV                 : {output_csv}")
    print(f"[INFO] JSON                : {output_json}")
    print(f"[INFO] Targets             : {len(output_df)}")
    if not output_df.empty:
        print("[INFO] Top targets:")
        for row in output_df.head(min(5, len(output_df))).itertuples(index=False):
            print(
                "       "
                f"{row.target_id}: z=({row.z_1:.6g}, {row.z_2:.6g}), "
                f"nearest_distance={row.nearest_instance_distance:.6g}"
            )

    return explore_run_dir, output_df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Detect empty regions in an exploreIS map and save center coordinates "
            "as targets for future instance generation."
        )
    )
    parser.add_argument(
        "--explore-run-dir",
        type=Path,
        help="Specific explore output directory. Defaults to matilda_out/explore.",
    )
    parser.add_argument(
        "--explore-base",
        type=Path,
        default=DEFAULT_EXPLORE_BASE,
        help="Current explore output folder.",
    )
    parser.add_argument(
        "--grid-size",
        type=int,
        default=80,
        help="Number of grid points per axis used to search for gaps.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of empty-space centers to save.",
    )
    parser.add_argument(
        "--padding-ratio",
        type=float,
        default=0.05,
        help="Extra search margin around the observed coordinate range.",
    )
    parser.add_argument(
        "--min-separation-ratio",
        type=float,
        default=0.12,
        help="Minimum spacing between selected targets as a fraction of map diagonal.",
    )
    parser.add_argument(
        "--include-outside-hull",
        action="store_true",
        help="Also consider empty rectangle regions outside the observed convex hull.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    find_empty_space_centers(
        explore_run_dir=args.explore_run_dir,
        explore_base=args.explore_base,
        grid_size=args.grid_size,
        top_k=args.top_k,
        padding_ratio=args.padding_ratio,
        min_separation_ratio=args.min_separation_ratio,
        inside_convex_hull=not args.include_outside_hull,
    )


if __name__ == "__main__":
    main()
