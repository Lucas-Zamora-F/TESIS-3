from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def _is_comment_or_empty(line: str) -> bool:
    stripped = line.strip()
    return (
        not stripped
        or stripped.startswith('"')
        or stripped.startswith("*")
    )


def _clean_block_line(block_line: str) -> list[int]:
    """
    Parsea la línea de block sizes de un archivo .dat-s (formato SDPA).

    Soporta variantes como:
        {2, 3, -5}
        2 3 -5
        2, 3, -5
        (2, 3, -5)
    """
    cleaned = block_line.strip()
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = cleaned.replace(",", " ")

    tokens = cleaned.split()
    block_sizes = [int(tok) for tok in tokens]

    if not block_sizes:
        raise ValueError("No se pudieron parsear los block sizes.")

    return block_sizes


def _read_relevant_noncomment_lines(instance_path: Path) -> list[str]:
    relevant_lines: list[str] = []

    with instance_path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            if _is_comment_or_empty(raw_line):
                continue
            relevant_lines.append(raw_line.strip())

    return relevant_lines


def _read_sdpa_header(instance_path: Path) -> tuple[int, int, list[int], list[float], list[str]]:
    """
    Lee el header estándar de un .dat-s:
      1) m
      2) n_blocks
      3) block_sizes
      4) vector b
      5+) cuerpo sparse
    """
    lines = _read_relevant_noncomment_lines(instance_path)

    if len(lines) < 4:
        raise ValueError(
            f"Archivo {instance_path} demasiado corto. "
            f"Se esperaban al menos 4 líneas relevantes."
        )

    try:
        m = int(lines[0])
    except ValueError as e:
        raise ValueError(f"No se pudo parsear m en {instance_path}: {lines[0]}") from e

    try:
        n_blocks = int(lines[1])
    except ValueError as e:
        raise ValueError(f"No se pudo parsear n_blocks en {instance_path}: {lines[1]}") from e

    block_sizes = _clean_block_line(lines[2])

    if len(block_sizes) != n_blocks:
        raise ValueError(
            f"Inconsistencia en {instance_path}: "
            f"n_blocks={n_blocks}, pero se parsearon {len(block_sizes)} block sizes."
        )

    b_line = lines[3].replace("{", " ").replace("}", " ").replace(",", " ")
    try:
        b = [float(tok) for tok in b_line.split()]
    except ValueError as e:
        raise ValueError(f"No se pudo parsear vector b en {instance_path}: {lines[3]}") from e

    if len(b) != m:
        raise ValueError(
            f"Inconsistencia en {instance_path}: "
            f"m={m}, pero se parsearon {len(b)} entradas en b."
        )

    body_lines = lines[4:]
    return m, n_blocks, block_sizes, b, body_lines


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _safe_std(values: list[float]) -> float | None:
    if not values:
        return None
    mean_val = sum(values) / len(values)
    variance = sum((x - mean_val) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def _safe_cv(values: list[float]) -> float | None:
    if not values:
        return None
    mean_val = _safe_mean(values)
    std_val = _safe_std(values)
    if mean_val is None or std_val is None or mean_val == 0:
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
    """
    Rango dinámico = max_abs / min_abs_nonzero.
    """
    max_abs = _safe_max_abs(values)
    min_abs_nonzero = _safe_min_abs_nonzero(values)

    if max_abs is None or min_abs_nonzero is None or min_abs_nonzero == 0:
        return None

    return max_abs / min_abs_nonzero


def _fro_norm_from_upper_entries(entries: list[tuple[int, int, int, float]]) -> float:
    """
    Norma de Frobenius de la matriz simétrica implícita a partir
    de entradas de la triangular superior.

    Cada entry: (block_id, row, col, value)
    - si row == col, contribuye value^2
    - si row < col, contribuye 2 * value^2
    """
    total_sq = 0.0

    for _, row, col, value in entries:
        if row == col:
            total_sq += value * value
        else:
            total_sq += 2.0 * value * value

    return math.sqrt(total_sq)


def _l1_norm(values: list[float]) -> float:
    return sum(abs(v) for v in values)


def _l2_norm(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values))


def extract_scaling_features(instance_path: str | Path) -> dict[str, Any]:
    """
    Extrae scaling features desde un archivo .dat-s en formato SDPA sparse.

    Se asume cuerpo tipo:
        matrix_number block_number row col value

    Donde:
    - matrix_number = 0  -> C
    - matrix_number = 1..m -> A_i
    """
    instance_path = Path(instance_path)

    m, n_blocks, block_sizes, b, body_lines = _read_sdpa_header(instance_path)

    # Guardamos entradas por matriz:
    # matrix_entries[mat_id] = list[(block_id, row, col, value)]
    matrix_entries: dict[int, list[tuple[int, int, int, float]]] = {
        mat_id: [] for mat_id in range(m + 1)
    }

    all_nonzero_values: list[float] = []

    for line in body_lines:
        parts = line.split()
        if len(parts) < 5:
            continue

        try:
            mat_id = int(parts[0])
            block_id = int(parts[1])
            row = int(parts[2])
            col = int(parts[3])
            value = float(parts[4])
        except ValueError:
            continue

        if value == 0.0:
            continue

        if mat_id < 0 or mat_id > m:
            continue
        if block_id < 1 or block_id > n_blocks:
            continue

        # Normalizamos por seguridad a triangular superior
        if row > col:
            row, col = col, row

        matrix_entries[mat_id].append((block_id, row, col, value))
        all_nonzero_values.append(value)

    # =========================
    # C
    # =========================
    c_entries = matrix_entries[0]
    c_values = [value for _, _, _, value in c_entries]

    c_fro_norm_upper = _fro_norm_from_upper_entries(c_entries)
    c_max_abs_entry = _safe_max_abs(c_values)
    c_min_abs_nonzero_entry = _safe_min_abs_nonzero(c_values)
    c_dynamic_range = _dynamic_range_from_values(c_values)

    # =========================
    # A_i
    # =========================
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

    # =========================
    # b
    # =========================
    b_l1_norm = _l1_norm(b)
    b_l2_norm = _l2_norm(b)
    b_max_abs = _safe_max_abs(b)
    b_min_abs_nonzero = _safe_min_abs_nonzero(b)
    b_dynamic_range = _dynamic_range_from_values(b)
    b_mean = _safe_mean(b)
    b_std = _safe_std(b)

    # =========================
    # Globales / combinadas
    # =========================
    global_all_coeff_max_abs = _safe_max_abs(all_nonzero_values)
    global_all_coeff_min_abs_nonzero = _safe_min_abs_nonzero(all_nonzero_values)
    global_all_coeff_dynamic_range = _dynamic_range_from_values(all_nonzero_values)

    ratio_c_to_avg_ai_fro = (
        c_fro_norm_upper / avg_ai_fro_norm_upper
        if avg_ai_fro_norm_upper not in (None, 0)
        else None
    )

    ratio_c_to_b_l2 = (
        c_fro_norm_upper / b_l2_norm
        if b_l2_norm != 0
        else None
    )

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

    features = {
        "Instance": instance_path.name,

        # C
        "feature_c_fro_norm_upper": c_fro_norm_upper,
        "feature_c_max_abs_entry": c_max_abs_entry,
        "feature_c_min_abs_nonzero_entry": c_min_abs_nonzero_entry,
        "feature_c_dynamic_range": c_dynamic_range,

        # A_i - normas
        "feature_avg_ai_fro_norm_upper": avg_ai_fro_norm_upper,
        "feature_max_ai_fro_norm_upper": max_ai_fro_norm_upper,
        "feature_min_ai_fro_norm_upper": min_ai_fro_norm_upper,
        "feature_std_ai_fro_norm_upper": std_ai_fro_norm_upper,
        "feature_ai_fro_norm_cv": ai_fro_norm_cv,

        "feature_avg_ai_l1_norm": avg_ai_l1_norm,
        "feature_max_ai_l1_norm": max_ai_l1_norm,
        "feature_min_ai_l1_norm": min_ai_l1_norm,

        # A_i - entradas
        "feature_avg_ai_max_abs_entry": avg_ai_max_abs_entry,
        "feature_max_ai_max_abs_entry": max_ai_max_abs_entry,
        "feature_avg_ai_min_abs_nonzero_entry": avg_ai_min_abs_nonzero_entry,
        "feature_min_ai_min_abs_nonzero_entry": min_ai_min_abs_nonzero_entry,

        # A_i - rango dinámico
        "feature_avg_ai_dynamic_range": avg_ai_dynamic_range,
        "feature_max_ai_dynamic_range": max_ai_dynamic_range,
        "feature_min_ai_dynamic_range": min_ai_dynamic_range,

        # b
        "feature_b_l1_norm": b_l1_norm,
        "feature_b_l2_norm": b_l2_norm,
        "feature_b_max_abs": b_max_abs,
        "feature_b_min_abs_nonzero": b_min_abs_nonzero,
        "feature_b_dynamic_range": b_dynamic_range,
        "feature_b_mean": b_mean,
        "feature_b_std": b_std,

        # globales
        "feature_global_all_coeff_max_abs": global_all_coeff_max_abs,
        "feature_global_all_coeff_min_abs_nonzero": global_all_coeff_min_abs_nonzero,
        "feature_global_all_coeff_dynamic_range": global_all_coeff_dynamic_range,

        # combinadas
        "feature_ratio_c_to_avg_ai_fro": ratio_c_to_avg_ai_fro,
        "feature_ratio_c_to_b_l2": ratio_c_to_b_l2,
        "feature_ratio_avg_ai_to_b_l2": ratio_avg_ai_to_b_l2,
        "feature_max_ai_to_min_ai_fro_ratio": max_ai_to_min_ai_fro_ratio,
        "feature_max_ai_to_avg_ai_fro_ratio": max_ai_to_avg_ai_fro_ratio,
    }

    return features