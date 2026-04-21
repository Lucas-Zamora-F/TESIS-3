from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.features.instance_reader import instance_display_name, read_problem_data


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

    # remover delimitadores comunes
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
    Lee las primeras líneas relevantes de un .dat-s:
      1) m
      2) n_blocks
      3) block_sizes

    Ignora líneas vacías y comentarios.
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


def extract_size_features(instance_path: str | Path) -> dict[str, Any]:
    """
    Extrae size features desde una instancia .dat-s o .mat SeDuMi.

    Retorna un diccionario listo para agregarse a una fila de DataFrame.
    """
    instance_path = Path(instance_path)

    problem = read_problem_data(instance_path, include_entries=False)
    m = problem.m
    n_blocks = problem.n_blocks
    block_sizes = problem.block_sizes

    positive_blocks = [b for b in block_sizes if b > 0]
    negative_blocks = [b for b in block_sizes if b < 0]
    abs_block_sizes = [abs(b) for b in block_sizes]

    n_total_matrix = sum(abs_block_sizes)

    num_positive_blocks = len(positive_blocks)
    num_negative_blocks = len(negative_blocks)
    num_unit_blocks = sum(1 for b in abs_block_sizes if b == 1)

    sum_positive_blocks = sum(positive_blocks)
    sum_negative_abs_blocks = sum(abs(b) for b in negative_blocks)

    max_block_size = max(abs_block_sizes) if abs_block_sizes else 0
    min_block_size = min(abs_block_sizes) if abs_block_sizes else 0
    mean_block_size = (
        sum(abs_block_sizes) / len(abs_block_sizes) if abs_block_sizes else 0.0
    )

    if abs_block_sizes:
        mean_val = mean_block_size
        variance = sum((x - mean_val) ** 2 for x in abs_block_sizes) / len(abs_block_sizes)
        std_block_size = variance ** 0.5
    else:
        std_block_size = 0.0

    aspect_ratio_m_over_n = m / n_total_matrix if n_total_matrix > 0 else None
    aspect_ratio_m_over_nsq = m / (n_total_matrix ** 2) if n_total_matrix > 0 else None

    features = {
        "Instance": instance_display_name(instance_path),
        "feature_m": m,
        "feature_n_blocks": n_blocks,
        "feature_n_total_matrix": n_total_matrix,
        "feature_max_block_size": max_block_size,
        "feature_min_block_size": min_block_size,
        "feature_mean_block_size": mean_block_size,
        "feature_std_block_size": std_block_size,
        "feature_num_positive_blocks": num_positive_blocks,
        "feature_num_negative_blocks": num_negative_blocks,
        "feature_num_unit_blocks": num_unit_blocks,
        "feature_sum_positive_blocks": sum_positive_blocks,
        "feature_sum_negative_abs_blocks": sum_negative_abs_blocks,
        "feature_aspect_ratio_m_over_n": aspect_ratio_m_over_n,
        "feature_aspect_ratio_m_over_nsq": aspect_ratio_m_over_nsq,
        # útil para inspección/debug
        "feature_block_sizes_raw": ";".join(str(b) for b in block_sizes),
    }

    return features
