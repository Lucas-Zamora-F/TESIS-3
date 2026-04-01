from __future__ import annotations

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
    """
    Lee todas las líneas relevantes (sin comentarios ni vacías).
    """
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

    Retorna:
      - m
      - n_blocks
      - block_sizes
      - b
      - body_lines
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
    return variance ** 0.5


def _block_upper_capacity(block_size: int) -> int:
    """
    Número máximo de posiciones almacenables en triangular superior
    para un bloque SDPA.

    Convención:
    - bloque positivo k > 0: bloque SDP simétrico k x k
      capacidad upper = k(k+1)/2
    - bloque negativo -k < 0: bloque diagonal/LP-like de tamaño k
      capacidad = k
    """
    if block_size > 0:
        return block_size * (block_size + 1) // 2
    return abs(block_size)


def _block_full_capacity(block_size: int) -> int:
    """
    Número máximo de posiciones implícitas en la matriz completa.
    """
    if block_size > 0:
        k = block_size
        return k * k
    return abs(block_size)


def _full_implied_nnz_from_upper_entries(
    entries: set[tuple[int, int, int]]
) -> int:
    """
    Convierte un patrón upper-triangular en nnz de matriz simétrica completa.

    Cada entry es (block_id, row, col), con row <= col.
    - si row == col, cuenta 1
    - si row < col, cuenta 2
    """
    total = 0
    for _, row, col in entries:
        total += 1 if row == col else 2
    return total


def extract_sparsity_features(instance_path: str | Path) -> dict[str, Any]:
    """
    Extrae features de sparsity desde un archivo .dat-s.

    Se asume formato SDPA sparse:
        matrix_number block_number row col value

    Donde:
    - matrix_number = 0 corresponde a C
    - matrix_number = 1..m corresponden a A_i

    Las features se calculan sobre el patrón de no ceros almacenado
    (triangular superior) y también sobre la matriz simétrica implícita.
    """
    instance_path = Path(instance_path)

    m, n_blocks, block_sizes, _, body_lines = _read_sdpa_header(instance_path)

    # Capacidad total por matriz (upper y full)
    upper_capacity_per_matrix = sum(_block_upper_capacity(b) for b in block_sizes)
    full_capacity_per_matrix = sum(_block_full_capacity(b) for b in block_sizes)

    # Patrones de no ceros:
    # matrix_patterns[mat_id] = set[(block_id, row, col)]
    # mat_id = 0 para C, 1..m para A_i
    matrix_patterns: dict[int, set[tuple[int, int, int]]] = {
        mat_id: set() for mat_id in range(m + 1)
    }

    for line in body_lines:
        parts = line.split()
        if len(parts) < 5:
            # ignoramos líneas mal formadas en lugar de reventar todo
            continue

        try:
            mat_id = int(parts[0])
            block_id = int(parts[1])
            row = int(parts[2])
            col = int(parts[3])
            value = float(parts[4])
        except ValueError:
            continue

        # Nos quedamos solo con no ceros reales
        if value == 0.0:
            continue

        # Validaciones suaves
        if mat_id < 0 or mat_id > m:
            continue
        if block_id < 1 or block_id > n_blocks:
            continue

        # Normalizamos a triangular superior por seguridad
        if row > col:
            row, col = col, row

        matrix_patterns[mat_id].add((block_id, row, col))

    # ===== C =====
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

    # ===== A_i =====
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

    features = {
        "Instance": instance_path.name,

        # capacidades base
        "feature_upper_capacity_per_matrix": upper_capacity_per_matrix,
        "feature_full_capacity_per_matrix": full_capacity_per_matrix,
        "feature_total_possible_upper_all_ai": total_possible_upper_all_ai,
        "feature_total_possible_full_all_ai": total_possible_full_all_ai,

        # C
        "feature_nnz_c_upper": nnz_c_upper,
        "feature_density_c_upper": density_c_upper,
        "feature_nnz_c_full_implied": nnz_c_full_implied,
        "feature_density_c_full_implied": density_c_full_implied,

        # A_i upper
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

        # A_i full implied
        "feature_total_nnz_ai_full_implied": total_nnz_ai_full_implied,
        "feature_avg_nnz_ai_full_implied": avg_nnz_ai_full_implied,
        "feature_avg_density_ai_full_implied": avg_density_ai_full_implied,
        "feature_total_density_all_ai_full_implied": total_density_all_ai_full_implied,

        # vacíos
        "feature_num_empty_ai": num_empty_ai,
        "feature_fraction_empty_ai": fraction_empty_ai,
    }

    return features