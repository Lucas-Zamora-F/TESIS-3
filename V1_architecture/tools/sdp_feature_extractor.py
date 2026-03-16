from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def natural_key(path: Path) -> list[Any]:
    parts = re.split(r"(\d+)", path.stem.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def numbers(line: str) -> list[str]:
    """
    Extrae números desde una línea en formato SDPA.
    Soporta enteros, flotantes y notación científica.
    """
    return re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", line)


def infer_family(file_path: Path) -> str:
    """
    Intenta inferir la familia del problema desde el nombre del archivo.
    Si no encuentra prefijo alfabético, devuelve 'unknown'.
    Ejemplos:
    - arch0.dat-s  -> arch
    - control1.dat-s -> control
    - thetaG51.dat-s -> thetag
    """
    stem = file_path.stem.lower()
    match = re.match(r"([a-zA-Z_]+)", stem)
    if match:
        return match.group(1).lower()
    return "unknown"


def _clean_lines(file_path: Path) -> list[str]:
    """
    Lee el archivo y elimina:
    - líneas vacías
    - comentarios que empiezan con * o "
    """
    cleaned: list[str] = []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line:
                continue

            if line.startswith("*") or line.startswith('"'):
                continue

            cleaned.append(line)

    if not cleaned:
        raise ValueError(f"El archivo está vacío o no contiene datos útiles: {file_path}")

    return cleaned


def parse_sdpa_instance(file_path: str | Path) -> dict[str, Any]:
    """
    Parsea una instancia .dat-s en formato SDPA y devuelve su estructura base:
    - m
    - n_blocks
    - block_sizes
    - b
    - entries_raw

    Cada entrada en entries_raw corresponde a una línea con al menos 5 números,
    usualmente del tipo:
        matrix_id, block_id, i, j, value
    """
    path = Path(file_path)
    lines = _clean_lines(path)

    idx = 0

    # Número de restricciones
    m_tokens = numbers(lines[idx])
    if not m_tokens:
        raise ValueError(f"No se pudo leer m en la línea 1 de {path.name}")
    m = int(float(m_tokens[0]))
    idx += 1

    # Número de bloques
    nb_tokens = numbers(lines[idx])
    if not nb_tokens:
        raise ValueError(f"No se pudo leer n_blocks en la línea 2 de {path.name}")
    n_blocks = int(float(nb_tokens[0]))
    idx += 1

    # Tamaños de bloques
    block_sizes: list[int] = []
    while len(block_sizes) < n_blocks:
        if idx >= len(lines):
            raise ValueError(f"Archivo incompleto leyendo block_sizes en {path.name}")

        block_sizes.extend(int(float(x)) for x in numbers(lines[idx]))
        idx += 1

    # Vector b
    b: list[float] = []
    while len(b) < m:
        if idx >= len(lines):
            raise ValueError(f"Archivo incompleto leyendo b en {path.name}")

        b.extend(float(x) for x in numbers(lines[idx]))
        idx += 1

    # Entradas restantes
    entries_raw: list[list[float]] = []
    while idx < len(lines):
        vals = numbers(lines[idx])
        if len(vals) >= 5:
            entries_raw.append([float(x) for x in vals[:5]])
        idx += 1

    return {
        "m": m,
        "n_blocks": n_blocks,
        "block_sizes": block_sizes,
        "b": b,
        "entries_raw": entries_raw,
    }


def compute_sdpa_features(file_path: str | Path) -> dict[str, Any]:
    """
    Extrae features estructurales de una instancia SDPA (.dat-s).
    """
    path = Path(file_path)
    parsed = parse_sdpa_instance(path)

    m = parsed["m"]
    n_blocks = parsed["n_blocks"]
    block_sizes = parsed["block_sizes"]
    entries_raw = parsed["entries_raw"]

    # Valores absolutos no nulos
    abs_values: list[float] = []
    nnz = 0

    # block_id distintos usados en las entradas
    used_blocks: set[int] = set()

    for row in entries_raw:
        # Formato típico: [mat_id, block_id, i, j, value]
        if len(row) < 5:
            continue

        block_id = int(row[1])
        value = float(row[4])

        nnz += 1
        used_blocks.add(block_id)

        if value != 0:
            abs_values.append(abs(value))

    # Tamaño total "vectorizado" del problema
    # Para bloques semidefinidos positivos:
    #   s > 0  -> aporta s*(s+1)/2
    # Para bloques diagonales o lineales:
    #   s < 0  -> aporta abs(s)
    size = 0
    for s in block_sizes:
        if s > 0:
            size += s * (s + 1) // 2
        else:
            size += abs(s)

    # Suma simple de tamaños absolutos de bloque
    sum_block_size = sum(abs(s) for s in block_sizes)

    positive_blocks = [s for s in block_sizes if s > 0]
    absolute_blocks = [abs(s) for s in block_sizes]

    max_block_size = max(absolute_blocks) if absolute_blocks else None
    min_block_size = min(absolute_blocks) if absolute_blocks else None

    n_positive_blocks = len(positive_blocks)
    n_negative_blocks = sum(1 for s in block_sizes if s < 0)

    # Densidad aproximada usada antes
    sparsity = None
    if m > 0 and size > 0:
        sparsity = nnz / (m * size)

    # Escalamiento numérico básico
    scaling = None
    min_abs_value = None
    max_abs_value = None

    if abs_values:
        min_abs_value = min(abs_values)
        max_abs_value = max(abs_values)

        if min_abs_value > 0:
            scaling = max_abs_value / min_abs_value

    return {
        "instance": path.stem,
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "family": infer_family(path),
        "m": m,
        "n_blocks": n_blocks,
        "n_positive_blocks": n_positive_blocks,
        "n_negative_blocks": n_negative_blocks,
        "n_used_blocks": len(used_blocks),
        "feature_size": size,
        "feature_sum_block_size": sum_block_size,
        "feature_max_block_size": max_block_size,
        "feature_min_block_size": min_block_size,
        "feature_nnz": nnz,
        "feature_sparsity": sparsity,
        "feature_scaling": scaling,
        "feature_min_abs_value": min_abs_value,
        "feature_max_abs_value": max_abs_value,
    }


def extract_features_for_directory(instances_dir: str | Path) -> list[dict[str, Any]]:
    """
    Recorre todos los .dat-s de una carpeta y devuelve una lista de diccionarios.
    """
    root = Path(instances_dir)

    if not root.exists():
        raise FileNotFoundError(f"No existe la carpeta: {root}")

    files = sorted(root.glob("*.dat-s"), key=natural_key)

    if not files:
        raise FileNotFoundError(f"No se encontraron archivos .dat-s en: {root}")

    rows: list[dict[str, Any]] = []

    for file_path in files:
        try:
            row = compute_sdpa_features(file_path)
            rows.append(row)
        except Exception as e:
            rows.append(
                {
                    "instance": file_path.stem,
                    "file_name": file_path.name,
                    "file_path": str(file_path.resolve()),
                    "family": infer_family(file_path),
                    "error": str(e),
                }
            )

    return rows