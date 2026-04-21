from __future__ import annotations

import math
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
    mean_val = _safe_mean(values)
    if mean_val is None:
        return None
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _safe_cv(values: list[float]) -> float | None:
    mean_val = _safe_mean(values)
    std_val = _safe_std(values)
    if mean_val in (None, 0) or std_val is None:
        return None
    return std_val / mean_val


def _safe_min_abs_nonzero(values: list[float]) -> float | None:
    nz = [abs(v) for v in values if v != 0]
    if not nz:
        return None
    return min(nz)


def _safe_max_abs(values: list[float]) -> float | None:
    if not values:
        return None
    return max(abs(v) for v in values)


def _dynamic_range_from_values(values: list[float]) -> float | None:
    max_abs = _safe_max_abs(values)
    min_abs_nonzero = _safe_min_abs_nonzero(values)
    if max_abs is None or min_abs_nonzero in (None, 0):
        return None
    return max_abs / min_abs_nonzero


def _fro_norm_from_upper_entries(entries: list[tuple[int, int, int, float]]) -> float:
    total_sq = 0.0
    for _, row, col, value in entries:
        total_sq += value * value if row == col else 2.0 * value * value
    return math.sqrt(total_sq)


def _l1_norm(values: list[float]) -> float:
    return sum(abs(v) for v in values)


def _l2_norm(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values))


def extract_scaling_features(instance_path: str | Path) -> dict[str, Any]:
    """
    Extract scaling features from SDPA text (.dat-s) or SeDuMi MATLAB (.mat)
    instances.
    """
    problem = read_problem_data(instance_path)
    m = problem.m
    b = problem.b

    matrix_entries: dict[int, list[tuple[int, int, int, float]]] = {
        mat_id: [] for mat_id in range(m + 1)
    }
    all_nonzero_values: list[float] = []

    for entry in problem.entries:
        if entry.mat_id < 0 or entry.mat_id > m:
            continue
        if entry.block_id < 1 or entry.block_id > problem.n_blocks:
            continue

        row, col = entry.row, entry.col
        if row > col:
            row, col = col, row

        matrix_entries[entry.mat_id].append((entry.block_id, row, col, entry.value))
        all_nonzero_values.append(entry.value)

    c_entries = matrix_entries[0]
    c_values = [value for _, _, _, value in c_entries]

    c_fro_norm_upper = _fro_norm_from_upper_entries(c_entries)
    c_max_abs_entry = _safe_max_abs(c_values)
    c_min_abs_nonzero_entry = _safe_min_abs_nonzero(c_values)
    c_dynamic_range = _dynamic_range_from_values(c_values)

    ai_fro_norms: list[float] = []
    ai_max_abs_entries: list[float] = []
    ai_min_abs_nonzero_entries: list[float] = []
    ai_dynamic_ranges: list[float] = []
    ai_l1_norms: list[float] = []

    for mat_id in range(1, m + 1):
        entries = matrix_entries[mat_id]
        values = [value for _, _, _, value in entries]

        fro_norm = _fro_norm_from_upper_entries(entries)
        ai_fro_norms.append(fro_norm)

        max_abs = _safe_max_abs(values)
        if max_abs is not None:
            ai_max_abs_entries.append(max_abs)

        min_abs_nonzero = _safe_min_abs_nonzero(values)
        if min_abs_nonzero is not None:
            ai_min_abs_nonzero_entries.append(min_abs_nonzero)

        dynamic_range = _dynamic_range_from_values(values)
        if dynamic_range is not None:
            ai_dynamic_ranges.append(dynamic_range)

        ai_l1_norms.append(_l1_norm(values))

    avg_ai_fro_norm_upper = _safe_mean(ai_fro_norms)
    max_ai_fro_norm_upper = max(ai_fro_norms) if ai_fro_norms else None
    min_ai_fro_norm_upper = min(ai_fro_norms) if ai_fro_norms else None
    std_ai_fro_norm_upper = _safe_std(ai_fro_norms)
    ai_fro_norm_cv = _safe_cv(ai_fro_norms)

    avg_ai_max_abs_entry = _safe_mean(ai_max_abs_entries)
    max_ai_max_abs_entry = max(ai_max_abs_entries) if ai_max_abs_entries else None

    avg_ai_min_abs_nonzero_entry = _safe_mean(ai_min_abs_nonzero_entries)
    min_ai_min_abs_nonzero_entry = (
        min(ai_min_abs_nonzero_entries) if ai_min_abs_nonzero_entries else None
    )

    avg_ai_dynamic_range = _safe_mean(ai_dynamic_ranges)
    max_ai_dynamic_range = max(ai_dynamic_ranges) if ai_dynamic_ranges else None
    min_ai_dynamic_range = min(ai_dynamic_ranges) if ai_dynamic_ranges else None

    avg_ai_l1_norm = _safe_mean(ai_l1_norms)
    max_ai_l1_norm = max(ai_l1_norms) if ai_l1_norms else None
    min_ai_l1_norm = min(ai_l1_norms) if ai_l1_norms else None

    b_l1_norm = _l1_norm(b)
    b_l2_norm = _l2_norm(b)
    b_max_abs = _safe_max_abs(b)
    b_min_abs_nonzero = _safe_min_abs_nonzero(b)
    b_dynamic_range = _dynamic_range_from_values(b)
    b_mean = _safe_mean(b)
    b_std = _safe_std(b)

    global_all_coeff_max_abs = _safe_max_abs(all_nonzero_values)
    global_all_coeff_min_abs_nonzero = _safe_min_abs_nonzero(all_nonzero_values)
    global_all_coeff_dynamic_range = _dynamic_range_from_values(all_nonzero_values)

    ratio_c_to_avg_ai_fro = (
        c_fro_norm_upper / avg_ai_fro_norm_upper
        if avg_ai_fro_norm_upper not in (None, 0)
        else None
    )
    ratio_c_to_b_l2 = c_fro_norm_upper / b_l2_norm if b_l2_norm != 0 else None
    ratio_avg_ai_to_b_l2 = (
        avg_ai_fro_norm_upper / b_l2_norm
        if avg_ai_fro_norm_upper is not None and b_l2_norm != 0
        else None
    )
    max_ai_to_min_ai_fro_ratio = (
        max_ai_fro_norm_upper / min_ai_fro_norm_upper
        if min_ai_fro_norm_upper not in (None, 0)
        and max_ai_fro_norm_upper is not None
        else None
    )
    max_ai_to_avg_ai_fro_ratio = (
        max_ai_fro_norm_upper / avg_ai_fro_norm_upper
        if avg_ai_fro_norm_upper not in (None, 0)
        and max_ai_fro_norm_upper is not None
        else None
    )

    return {
        "Instance": instance_display_name(instance_path),
        "feature_c_fro_norm_upper": c_fro_norm_upper,
        "feature_c_max_abs_entry": c_max_abs_entry,
        "feature_c_min_abs_nonzero_entry": c_min_abs_nonzero_entry,
        "feature_c_dynamic_range": c_dynamic_range,
        "feature_avg_ai_fro_norm_upper": avg_ai_fro_norm_upper,
        "feature_max_ai_fro_norm_upper": max_ai_fro_norm_upper,
        "feature_min_ai_fro_norm_upper": min_ai_fro_norm_upper,
        "feature_std_ai_fro_norm_upper": std_ai_fro_norm_upper,
        "feature_ai_fro_norm_cv": ai_fro_norm_cv,
        "feature_avg_ai_l1_norm": avg_ai_l1_norm,
        "feature_max_ai_l1_norm": max_ai_l1_norm,
        "feature_min_ai_l1_norm": min_ai_l1_norm,
        "feature_avg_ai_max_abs_entry": avg_ai_max_abs_entry,
        "feature_max_ai_max_abs_entry": max_ai_max_abs_entry,
        "feature_avg_ai_min_abs_nonzero_entry": avg_ai_min_abs_nonzero_entry,
        "feature_min_ai_min_abs_nonzero_entry": min_ai_min_abs_nonzero_entry,
        "feature_avg_ai_dynamic_range": avg_ai_dynamic_range,
        "feature_max_ai_dynamic_range": max_ai_dynamic_range,
        "feature_min_ai_dynamic_range": min_ai_dynamic_range,
        "feature_b_l1_norm": b_l1_norm,
        "feature_b_l2_norm": b_l2_norm,
        "feature_b_max_abs": b_max_abs,
        "feature_b_min_abs_nonzero": b_min_abs_nonzero,
        "feature_b_dynamic_range": b_dynamic_range,
        "feature_b_mean": b_mean,
        "feature_b_std": b_std,
        "feature_global_all_coeff_max_abs": global_all_coeff_max_abs,
        "feature_global_all_coeff_min_abs_nonzero": global_all_coeff_min_abs_nonzero,
        "feature_global_all_coeff_dynamic_range": global_all_coeff_dynamic_range,
        "feature_ratio_c_to_avg_ai_fro": ratio_c_to_avg_ai_fro,
        "feature_ratio_c_to_b_l2": ratio_c_to_b_l2,
        "feature_ratio_avg_ai_to_b_l2": ratio_avg_ai_to_b_l2,
        "feature_max_ai_to_min_ai_fro_ratio": max_ai_to_min_ai_fro_ratio,
        "feature_max_ai_to_avg_ai_fro_ratio": max_ai_to_avg_ai_fro_ratio,
    }
