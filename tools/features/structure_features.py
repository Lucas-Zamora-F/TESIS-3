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


def _read_header_lines(instance_path: Path) -> tuple[int, int, list[int]]:
    """
    Lee el header relevante de un archivo .dat-s:
      1) m
      2) n_blocks
      3) block_sizes
    """
    relevant_lines: list[str] = []

    with instance_path.open("r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            if _is_comment_or_empty(raw_line):
                continue
            relevant_lines.append(raw_line.strip())
            if len(relevant_lines) >= 3:
                break

    if len(relevant_lines) < 3:
        raise ValueError(
            f"Header incompleto en {instance_path}. "
            f"Se esperaban al menos 3 líneas relevantes."
        )

    try:
        m = int(relevant_lines[0])
    except ValueError as e:
        raise ValueError(
            f"No se pudo parsear m en {instance_path}: {relevant_lines[0]}"
        ) from e

    try:
        n_blocks = int(relevant_lines[1])
    except ValueError as e:
        raise ValueError(
            f"No se pudo parsear n_blocks en {instance_path}: {relevant_lines[1]}"
        ) from e

    block_sizes = _clean_block_line(relevant_lines[2])

    if len(block_sizes) != n_blocks:
        raise ValueError(
            f"Inconsistencia en {instance_path}: "
            f"n_blocks={n_blocks}, pero se parsearon {len(block_sizes)} block sizes."
        )

    return m, n_blocks, block_sizes


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


def _coefficient_of_variation(values: list[float]) -> float | None:
    if not values:
        return None
    mean_val = _safe_mean(values)
    std_val = _safe_std(values)
    if mean_val is None or std_val is None or mean_val == 0:
        return None
    return std_val / mean_val


def _entropy_from_sizes(sizes: list[int]) -> float | None:
    """
    Entropía de Shannon sobre la distribución relativa de tamaños de bloque.
    """
    if not sizes:
        return None

    total = sum(sizes)
    if total <= 0:
        return None

    probs = [size / total for size in sizes if size > 0]
    if not probs:
        return None

    return -sum(p * math.log(p) for p in probs)


def extract_structure_features(instance_path: str | Path) -> dict[str, Any]:
    """
    Extrae features de estructura del problema desde un archivo .dat-s.

    Estas features se basan en la organización por bloques del problema,
    no en sparsity, scaling ni propiedades espectrales.

    Retorna un diccionario listo para agregarse a una fila de DataFrame.
    """
    instance_path = Path(instance_path)

    _, n_blocks, block_sizes = _read_header_lines(instance_path)

    abs_block_sizes = [abs(b) for b in block_sizes]
    positive_blocks = [b for b in block_sizes if b > 0]   # bloques SDP
    negative_blocks = [abs(b) for b in block_sizes if b < 0]  # bloques diagonales / LP

    n_total_matrix = sum(abs_block_sizes)

    num_sdp_blocks = len(positive_blocks)
    num_lp_like_blocks = len(negative_blocks)

    is_single_block = 1 if n_blocks == 1 else 0
    is_multi_block = 1 if n_blocks > 1 else 0
    has_lp_blocks = 1 if num_lp_like_blocks > 0 else 0
    has_sdp_blocks = 1 if num_sdp_blocks > 0 else 0
    is_pure_sdp = 1 if num_sdp_blocks == n_blocks else 0
    is_mixed_sdp_lp = 1 if num_sdp_blocks > 0 and num_lp_like_blocks > 0 else 0

    max_block_size = max(abs_block_sizes) if abs_block_sizes else 0
    min_block_size = min(abs_block_sizes) if abs_block_sizes else 0

    largest_block_fraction = (
        max_block_size / n_total_matrix if n_total_matrix > 0 else None
    )

    smallest_block_fraction = (
        min_block_size / n_total_matrix if n_total_matrix > 0 else None
    )

    block_size_range = max_block_size - min_block_size if abs_block_sizes else 0

    mean_abs_block_size = _safe_mean(abs_block_sizes)
    std_abs_block_size = _safe_std(abs_block_sizes)
    cv_abs_block_size = _coefficient_of_variation(abs_block_sizes)

    sdp_total_size = sum(positive_blocks)
    lp_total_size = sum(negative_blocks)

    sdp_size_fraction = (
        sdp_total_size / n_total_matrix if n_total_matrix > 0 else None
    )
    lp_size_fraction = (
        lp_total_size / n_total_matrix if n_total_matrix > 0 else None
    )

    num_singleton_blocks = sum(1 for x in abs_block_sizes if x == 1)
    singleton_block_fraction = (
        num_singleton_blocks / n_blocks if n_blocks > 0 else None
    )

    num_large_blocks_ge_10 = sum(1 for x in abs_block_sizes if x >= 10)
    num_large_blocks_ge_50 = sum(1 for x in abs_block_sizes if x >= 50)

    large_blocks_ge_10_fraction = (
        num_large_blocks_ge_10 / n_blocks if n_blocks > 0 else None
    )
    large_blocks_ge_50_fraction = (
        num_large_blocks_ge_50 / n_blocks if n_blocks > 0 else None
    )

    block_size_entropy = _entropy_from_sizes(abs_block_sizes)

    # Índice simple de desbalance:
    # mientras más cerca de 1, más dominante es el bloque más grande.
    block_dominance_ratio = (
        max_block_size / mean_abs_block_size
        if mean_abs_block_size not in (None, 0)
        else None
    )

    # Cuánto del total está fuera del bloque más grande
    nonlargest_fraction = (
        1.0 - largest_block_fraction
        if largest_block_fraction is not None
        else None
    )

    features = {
        "Instance": instance_path.name,

        # tipo de estructura
        "feature_num_sdp_blocks": num_sdp_blocks,
        "feature_num_lp_like_blocks": num_lp_like_blocks,
        "feature_is_single_block": is_single_block,
        "feature_is_multi_block": is_multi_block,
        "feature_has_sdp_blocks": has_sdp_blocks,
        "feature_has_lp_blocks": has_lp_blocks,
        "feature_is_pure_sdp": is_pure_sdp,
        "feature_is_mixed_sdp_lp": is_mixed_sdp_lp,

        # composición por tamaño
        "feature_sdp_total_size": sdp_total_size,
        "feature_lp_total_size": lp_total_size,
        "feature_sdp_size_fraction": sdp_size_fraction,
        "feature_lp_size_fraction": lp_size_fraction,

        # balance / concentración
        "feature_largest_block_fraction": largest_block_fraction,
        "feature_smallest_block_fraction": smallest_block_fraction,
        "feature_nonlargest_fraction": nonlargest_fraction,
        "feature_block_dominance_ratio": block_dominance_ratio,
        "feature_block_size_entropy": block_size_entropy,

        # dispersión
        "feature_block_size_range": block_size_range,
        "feature_cv_block_size": cv_abs_block_size,

        # conteos estructurales
        "feature_num_singleton_blocks": num_singleton_blocks,
        "feature_singleton_block_fraction": singleton_block_fraction,
        "feature_num_large_blocks_ge_10": num_large_blocks_ge_10,
        "feature_num_large_blocks_ge_50": num_large_blocks_ge_50,
        "feature_large_blocks_ge_10_fraction": large_blocks_ge_10_fraction,
        "feature_large_blocks_ge_50_fraction": large_blocks_ge_50_fraction,
    }

    return features