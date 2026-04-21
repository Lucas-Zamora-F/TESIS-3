from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_INSTANCE_SUFFIXES = (".dat-s", ".mat")
MAX_ENTRY_EXTRACTION_VARIABLES = 20_000_000


@dataclass(frozen=True)
class MatrixEntry:
    mat_id: int
    block_id: int
    row: int
    col: int
    value: float


@dataclass(frozen=True)
class ProblemData:
    m: int
    n_blocks: int
    block_sizes: list[int]
    b: list[float]
    entries: list[MatrixEntry]


def is_supported_instance_path(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith(SUPPORTED_INSTANCE_SUFFIXES)


def collect_supported_instances(instances_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in instances_dir.rglob("*")
        if path.is_file() and is_supported_instance_path(path)
    )


def instance_display_name(instance_path: str | Path) -> str:
    path = Path(instance_path).resolve()
    dimacs_root = PROJECT_ROOT / "data" / "instances" / "DIMACS" / "instances"

    try:
        return path.relative_to(dimacs_root.resolve()).as_posix()
    except ValueError:
        return path.name


def read_problem_data(instance_path: str | Path, include_entries: bool = True) -> ProblemData:
    path = Path(instance_path)
    if path.name.lower().endswith(".dat-s"):
        return _read_sdpa_text(path, include_entries=include_entries)
    if path.suffix.lower() == ".mat":
        return _read_sedumi_mat(path, include_entries=include_entries)
    raise ValueError(f"Unsupported instance format: {path}")


def _is_comment_or_empty(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith('"') or stripped.startswith("*")


def clean_block_line(block_line: str) -> list[int]:
    cleaned = block_line.strip()
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = cleaned.replace(",", " ")

    block_sizes = [int(tok) for tok in cleaned.split()]
    if not block_sizes:
        raise ValueError("No block sizes could be parsed.")
    return block_sizes


def _read_relevant_noncomment_lines(instance_path: Path) -> list[str]:
    relevant_lines: list[str] = []

    with instance_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            if _is_comment_or_empty(raw_line):
                continue
            relevant_lines.append(raw_line.strip())

    return relevant_lines


def _read_sdpa_text(instance_path: Path, include_entries: bool = True) -> ProblemData:
    lines = _read_relevant_noncomment_lines(instance_path)

    if len(lines) < 4:
        raise ValueError(
            f"File {instance_path} is too short. Expected at least 4 relevant lines."
        )

    try:
        m = int(lines[0])
        n_blocks = int(lines[1])
    except ValueError as exc:
        raise ValueError(f"Could not parse SDPA header in {instance_path}.") from exc

    block_sizes = clean_block_line(lines[2])
    if len(block_sizes) != n_blocks:
        raise ValueError(
            f"Inconsistent block count in {instance_path}: "
            f"n_blocks={n_blocks}, parsed={len(block_sizes)}."
        )

    b_line = lines[3].replace("{", " ").replace("}", " ").replace(",", " ")
    try:
        b = [float(tok) for tok in b_line.split()]
    except ValueError as exc:
        raise ValueError(f"Could not parse vector b in {instance_path}.") from exc

    if len(b) != m:
        raise ValueError(
            f"Inconsistent b length in {instance_path}: m={m}, parsed={len(b)}."
        )

    entries: list[MatrixEntry] = []
    if include_entries:
        for line in lines[4:]:
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
            if row > col:
                row, col = col, row

            entries.append(MatrixEntry(mat_id, block_id, row, col, value))

    return ProblemData(
        m=m,
        n_blocks=n_blocks,
        block_sizes=block_sizes,
        b=b,
        entries=entries,
    )


def _as_1d_numeric(value: Any) -> list[float]:
    import numpy as np
    from scipy import sparse

    if value is None:
        return []

    if sparse.issparse(value):
        value = value.toarray()

    array = np.asarray(value).reshape(-1)
    if array.size == 0:
        return []

    return [float(v) for v in array]


def _as_int_list(value: Any) -> list[int]:
    values = _as_1d_numeric(value)
    return [int(v) for v in values if int(v) != 0]


def _k_value(k_struct: Any, name: str) -> Any:
    if hasattr(k_struct, name):
        return getattr(k_struct, name)
    if isinstance(k_struct, dict):
        return k_struct.get(name)
    return None


def _cone_block_sizes(k_struct: Any) -> list[int]:
    block_sizes: list[int] = []

    f = sum(_as_int_list(_k_value(k_struct, "f")))
    if f > 0:
        block_sizes.append(-f)

    l = sum(_as_int_list(_k_value(k_struct, "l")))
    if l > 0:
        block_sizes.append(-l)

    for q_size in _as_int_list(_k_value(k_struct, "q")):
        block_sizes.append(-q_size)

    for r_size in _as_int_list(_k_value(k_struct, "r")):
        block_sizes.append(-r_size)

    for s_size in _as_int_list(_k_value(k_struct, "s")):
        block_sizes.append(s_size)

    if not block_sizes:
        raise ValueError("The MATLAB K struct does not define any cone blocks.")

    return block_sizes


def _column_to_block_mapper(block_sizes: list[int]):
    sections: list[tuple[int, int, int, bool]] = []
    offset = 0

    for block_id, block_size in enumerate(block_sizes, start=1):
        size = abs(block_size)
        width = size * size if block_size > 0 else size
        sections.append((offset, offset + width, block_id, block_size > 0))
        offset += width

    def map_column(column_index: int) -> tuple[int, int, int] | None:
        for start, end, block_id, is_sdp in sections:
            if not start <= column_index < end:
                continue

            local = column_index - start
            size = abs(block_sizes[block_id - 1])

            if is_sdp:
                row = local % size + 1
                col = local // size + 1
                if row > col:
                    row, col = col, row
                return block_id, row, col

            row = local + 1
            return block_id, row, row

        return None

    return map_column, offset


def _iter_vector_nonzeros(vector: Any, expected_length: int):
    import numpy as np
    from scipy import sparse

    if sparse.issparse(vector):
        vector = vector.astype("float64")
        coo = vector.tocoo()

        if coo.shape == (1, expected_length):
            indices = coo.col
        elif coo.shape == (expected_length, 1):
            indices = coo.row
        elif coo.shape[0] * coo.shape[1] == expected_length:
            indices = coo.row + coo.col * coo.shape[0]
        else:
            raise ValueError(
                f"Unexpected sparse vector shape: expected length "
                f"{expected_length}, got shape {coo.shape}."
            )

        for index, value in zip(indices, coo.data):
            if value != 0:
                yield int(index), float(value)
        return

    array = np.asarray(vector).reshape(-1)
    if array.size == 1 and expected_length > 1:
        value = float(array[0])
        if value != 0:
            for index in range(expected_length):
                yield index, value
        return

    if array.size != expected_length:
        raise ValueError(
            f"Unexpected vector length: expected {expected_length}, got {array.size}."
        )

    for index in np.flatnonzero(array):
        value = float(array[index])
        if value != 0:
            yield int(index), value


def _read_sedumi_mat(instance_path: Path, include_entries: bool = True) -> ProblemData:
    from scipy import io as sio
    from scipy import sparse

    data = sio.loadmat(instance_path, squeeze_me=True, struct_as_record=False)

    if "K" not in data or "b" not in data:
        raise ValueError(f"{instance_path} is missing required SeDuMi variables K/b.")

    k_struct = data["K"]
    block_sizes = _cone_block_sizes(k_struct)
    mapper, n_variables = _column_to_block_mapper(block_sizes)

    b = _as_1d_numeric(data["b"])
    m = len(b)

    if "At" in data:
        at_matrix = data["At"]
        a_matrix = at_matrix.T
    elif "A" in data:
        a_candidate = data["A"]
        if getattr(a_candidate, "shape", (0, 0))[0] == m:
            a_matrix = a_candidate
        else:
            a_matrix = a_candidate.T
    else:
        a_matrix = sparse.csc_matrix((m, n_variables))

    if getattr(a_matrix, "shape", None) != (m, n_variables):
        raise ValueError(
            f"Unexpected constraint matrix shape in {instance_path}: "
            f"{getattr(a_matrix, 'shape', None)}; expected {(m, n_variables)}."
        )

    entries: list[MatrixEntry] = []

    def add_entry(mat_id: int, column_index: int, value: float) -> None:
        mapped = mapper(column_index)
        if mapped is None or value == 0.0:
            return
        block_id, row, col = mapped
        entries.append(MatrixEntry(mat_id, block_id, row, col, value))

    if not include_entries:
        return ProblemData(
            m=m,
            n_blocks=len(block_sizes),
            block_sizes=block_sizes,
            b=b,
            entries=[],
        )

    if n_variables > MAX_ENTRY_EXTRACTION_VARIABLES:
        raise MemoryError(
            f"Instance has {n_variables} variables; entry extraction limit is "
            f"{MAX_ENTRY_EXTRACTION_VARIABLES}."
        )

    c_vector = data.get("c", data.get("C"))
    if c_vector is not None:
        for column_index, value in _iter_vector_nonzeros(c_vector, n_variables):
            add_entry(0, column_index, value)

    if sparse.issparse(a_matrix):
        coo = a_matrix.astype("float64").tocoo()
        for row, col, value in zip(coo.row, coo.col, coo.data):
            add_entry(int(row) + 1, int(col), float(value))
    else:
        import numpy as np

        array = np.asarray(a_matrix)
        rows, cols = np.nonzero(array)
        for row, col in zip(rows, cols):
            add_entry(int(row) + 1, int(col), float(array[row, col]))

    return ProblemData(
        m=m,
        n_blocks=len(block_sizes),
        block_sizes=block_sizes,
        b=b,
        entries=entries,
    )
