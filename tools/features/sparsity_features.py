from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.features.instance_reader import instance_display_name, read_problem_data


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_std(values: list[float]) -> float | None:
    if not values:
        return None
    mean_val = sum(values) / len(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    return variance ** 0.5


def _block_upper_capacity(block_size: int) -> int:
    if block_size > 0:
        return block_size * (block_size + 1) // 2
    return abs(block_size)


def _block_full_capacity(block_size: int) -> int:
    if block_size > 0:
        return block_size * block_size
    return abs(block_size)


def _full_implied_nnz_from_upper_entries(entries: set[tuple[int, int, int]]) -> int:
    total = 0
    for _, row, col in entries:
        total += 1 if row == col else 2
    return total


def extract_sparsity_features(instance_path: str | Path) -> dict[str, Any]:
    """
    Extract sparsity features from SDPA text (.dat-s) or SeDuMi MATLAB (.mat)
    instances.
    """
    problem = read_problem_data(instance_path)
    m = problem.m
    block_sizes = problem.block_sizes

    upper_capacity_per_matrix = sum(_block_upper_capacity(b) for b in block_sizes)
    full_capacity_per_matrix = sum(_block_full_capacity(b) for b in block_sizes)

    matrix_patterns: dict[int, set[tuple[int, int, int]]] = {
        mat_id: set() for mat_id in range(m + 1)
    }

    for entry in problem.entries:
        if entry.mat_id < 0 or entry.mat_id > m:
            continue
        if entry.block_id < 1 or entry.block_id > problem.n_blocks:
            continue

        row, col = entry.row, entry.col
        if row > col:
            row, col = col, row

        matrix_patterns[entry.mat_id].add((entry.block_id, row, col))

    c_entries = matrix_patterns[0]
    nnz_c_upper = len(c_entries)
    density_c_upper = (
        nnz_c_upper / upper_capacity_per_matrix
        if upper_capacity_per_matrix > 0
        else None
    )

    nnz_c_full_implied = _full_implied_nnz_from_upper_entries(c_entries)
    density_c_full_implied = (
        nnz_c_full_implied / full_capacity_per_matrix
        if full_capacity_per_matrix > 0
        else None
    )

    ai_upper_counts: list[int] = []
    ai_full_counts: list[int] = []
    ai_upper_densities: list[float] = []
    ai_full_densities: list[float] = []
    num_empty_ai = 0

    for mat_id in range(1, m + 1):
        entries = matrix_patterns[mat_id]
        nnz_upper = len(entries)
        nnz_full = _full_implied_nnz_from_upper_entries(entries)

        ai_upper_counts.append(nnz_upper)
        ai_full_counts.append(nnz_full)

        if upper_capacity_per_matrix > 0:
            ai_upper_densities.append(nnz_upper / upper_capacity_per_matrix)

        if full_capacity_per_matrix > 0:
            ai_full_densities.append(nnz_full / full_capacity_per_matrix)

        if nnz_upper == 0:
            num_empty_ai += 1

    total_nnz_ai_upper = sum(ai_upper_counts)
    total_nnz_ai_full_implied = sum(ai_full_counts)

    avg_nnz_ai_upper = _safe_mean(ai_upper_counts)
    max_nnz_ai_upper = max(ai_upper_counts) if ai_upper_counts else None
    min_nnz_ai_upper = min(ai_upper_counts) if ai_upper_counts else None
    std_nnz_ai_upper = _safe_std(ai_upper_counts)

    avg_density_ai_upper = _safe_mean(ai_upper_densities)
    max_density_ai_upper = max(ai_upper_densities) if ai_upper_densities else None
    min_density_ai_upper = min(ai_upper_densities) if ai_upper_densities else None
    std_density_ai_upper = _safe_std(ai_upper_densities)

    avg_nnz_ai_full_implied = _safe_mean(ai_full_counts)
    avg_density_ai_full_implied = _safe_mean(ai_full_densities)

    fraction_empty_ai = num_empty_ai / m if m > 0 else None

    total_possible_upper_all_ai = m * upper_capacity_per_matrix
    total_possible_full_all_ai = m * full_capacity_per_matrix

    total_density_all_ai_upper = (
        total_nnz_ai_upper / total_possible_upper_all_ai
        if total_possible_upper_all_ai > 0
        else None
    )
    total_density_all_ai_full_implied = (
        total_nnz_ai_full_implied / total_possible_full_all_ai
        if total_possible_full_all_ai > 0
        else None
    )

    return {
        "Instance": instance_display_name(instance_path),
        "feature_upper_capacity_per_matrix": upper_capacity_per_matrix,
        "feature_full_capacity_per_matrix": full_capacity_per_matrix,
        "feature_total_possible_upper_all_ai": total_possible_upper_all_ai,
        "feature_total_possible_full_all_ai": total_possible_full_all_ai,
        "feature_nnz_c_upper": nnz_c_upper,
        "feature_density_c_upper": density_c_upper,
        "feature_nnz_c_full_implied": nnz_c_full_implied,
        "feature_density_c_full_implied": density_c_full_implied,
        "feature_total_nnz_ai_upper": total_nnz_ai_upper,
        "feature_avg_nnz_ai_upper": avg_nnz_ai_upper,
        "feature_max_nnz_ai_upper": max_nnz_ai_upper,
        "feature_min_nnz_ai_upper": min_nnz_ai_upper,
        "feature_std_nnz_ai_upper": std_nnz_ai_upper,
        "feature_avg_density_ai_upper": avg_density_ai_upper,
        "feature_max_density_ai_upper": max_density_ai_upper,
        "feature_min_density_ai_upper": min_density_ai_upper,
        "feature_std_density_ai_upper": std_density_ai_upper,
        "feature_total_density_all_ai_upper": total_density_all_ai_upper,
        "feature_total_nnz_ai_full_implied": total_nnz_ai_full_implied,
        "feature_avg_nnz_ai_full_implied": avg_nnz_ai_full_implied,
        "feature_avg_density_ai_full_implied": avg_density_ai_full_implied,
        "feature_total_density_all_ai_full_implied": total_density_all_ai_full_implied,
        "feature_num_empty_ai": num_empty_ai,
        "feature_fraction_empty_ai": fraction_empty_ai,
    }
