#!/usr/bin/env python
"""Build a DIMACS SDP-only instance directory.

The script creates data/instances/DIMACS/instances by default, preserving the
family subfolders. It copies files that are already SDP instances and converts
raw DIMACS .dat files for the families whose official generators define SDP
formulations: BISECT, FAP, and TORUS.

Large graph conversions can create very large sparse matrices. By default the
script skips conversions with n > --max-convert-n unless --allow-huge is used.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from scipy import io as sio
from scipy import sparse

from audit_dimacs_instances import classify_file


DEFAULT_SOURCE = Path("data/instances/DIMACS/extracted")
DEFAULT_OUTPUT = Path("data/instances/DIMACS/instances")
DEFAULT_MANIFEST = Path("tools/DIMACS/sdp_instances_manifest.csv")


@dataclass(frozen=True)
class DatInstance:
    n: int
    m: int
    k: int | None
    data: np.ndarray


@dataclass(frozen=True)
class Action:
    source: Path
    target: Path
    status: str
    detail: str


Converter = Callable[[Path, Path], None]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (_repo_root() / path).resolve()


def _read_dat(path: Path, has_k: bool) -> DatInstance:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        header = handle.readline().split()

    if has_k:
        if len(header) < 3:
            raise ValueError("expected header: n m k")
        n, m, k = int(header[0]), int(header[1]), int(header[2])
    else:
        if len(header) < 2:
            raise ValueError("expected header: n m")
        n, m, k = int(header[0]), int(header[1]), None

    data = np.loadtxt(path, skiprows=1, dtype=np.float64)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[0] != m or data.shape[1] < 3:
        raise ValueError(f"expected {m} rows with at least 3 columns, got {data.shape}")

    data = data[:, :3]
    ij = data[:, :2].astype(np.int64)
    lo = np.minimum(ij[:, 0], ij[:, 1])
    hi = np.maximum(ij[:, 0], ij[:, 1])
    data[:, 0] = lo
    data[:, 1] = hi
    return DatInstance(n=n, m=m, k=k, data=data)


def _k_struct(l: int, q: int, r: int, s: int) -> dict[str, np.ndarray]:
    return {
        "l": np.array([[l]], dtype=np.float64),
        "q": np.array([[q]], dtype=np.float64),
        "r": np.array([[r]], dtype=np.float64),
        "s": np.array([[s]], dtype=np.float64),
    }


def _vec_sparse_row(matrix: sparse.spmatrix) -> sparse.csc_matrix:
    coo = matrix.tocoo()
    n_rows = matrix.shape[0]
    linear_index = coo.row + coo.col * n_rows
    return sparse.coo_matrix(
        (coo.data, (np.zeros_like(linear_index), linear_index)),
        shape=(1, matrix.shape[0] * matrix.shape[1]),
    ).tocsc()


def _symmetric_weight_matrix(instance: DatInstance) -> sparse.csc_matrix:
    n = instance.n
    rows = instance.data[:, 0].astype(np.int64) - 1
    cols = instance.data[:, 1].astype(np.int64) - 1
    weights = instance.data[:, 2]
    row_idx = np.concatenate([rows, cols])
    col_idx = np.concatenate([cols, rows])
    values = np.concatenate([weights, weights])
    return sparse.coo_matrix((values, (row_idx, col_idx)), shape=(n, n)).tocsc()


def _save_sedumi(path: Path, *, A: sparse.spmatrix, b: np.ndarray, c: sparse.spmatrix, K: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sio.savemat(
        path,
        {
            "A": A.tocsc(),
            "b": np.asarray(b, dtype=np.float64).reshape(-1, 1),
            "c": c.tocsc(),
            "K": K,
        },
        do_compression=True,
    )


def convert_bisect(source: Path, target: Path) -> None:
    instance = _read_dat(source, has_k=False)
    n = instance.n
    W = _symmetric_weight_matrix(instance)
    degree = np.asarray(W.sum(axis=0)).ravel()
    C = 0.25 * (sparse.diags(degree, format="csc") - W)

    diag_positions = np.arange(n, dtype=np.int64) * (n + 1)
    diag_rows = sparse.coo_matrix(
        (np.ones(n), (np.arange(n), diag_positions)),
        shape=(n, n * n),
    )
    balance_row = sparse.coo_matrix(
        (np.ones(n * n), (np.zeros(n * n, dtype=np.int64), np.arange(n * n))),
        shape=(1, n * n),
    )
    A = sparse.vstack([diag_rows, balance_row], format="csc")
    b = np.concatenate([np.ones(n), np.array([0.0])])
    c = _vec_sparse_row(C)
    _save_sedumi(target, A=A, b=b, c=c, K=_k_struct(0, 0, 0, n))


def convert_fap(source: Path, target: Path) -> None:
    instance = _read_dat(source, has_k=True)
    if instance.k is None or instance.k <= 1:
        raise ValueError("FAP requires k > 1")
    n = instance.n
    k = instance.k

    W = _symmetric_weight_matrix(instance)
    degree = np.asarray(W.sum(axis=0)).ravel()
    C = (1.0 / (2.0 * k)) * (sparse.diags(degree, format="csc") + (k - 1) * W)

    rows = instance.data[:, 0].astype(np.int64) - 1
    cols = instance.data[:, 1].astype(np.int64) - 1
    fixed = instance.data[:, 2] > 900
    fixed_positions = np.concatenate([rows[fixed] + cols[fixed] * n, cols[fixed] + rows[fixed] * n])
    diag_positions = np.arange(n, dtype=np.int64) * (n + 1)
    constrained = np.unique(np.concatenate([diag_positions, fixed_positions]))

    all_positions = np.arange(n * n, dtype=np.int64)
    ind_geq = np.setdiff1d(all_positions, constrained, assume_unique=False)
    n_geq = ind_geq.size

    Al = sparse.coo_matrix(
        (-np.ones(n_geq), (ind_geq, np.arange(n_geq))),
        shape=(n * n, n_geq),
    )
    A = sparse.hstack([Al, sparse.eye(n * n, format="coo")], format="csc")

    b = (-1.0 / (k - 1.0)) * np.ones(n * n)
    b[diag_positions] = 1.0
    c = sparse.hstack([sparse.csc_matrix((1, n_geq)), _vec_sparse_row(C)], format="csc")
    _save_sedumi(target, A=A, b=b, c=c, K=_k_struct(int(n_geq), 0, 0, n))


def convert_torus(source: Path, target: Path) -> None:
    instance = _read_dat(source, has_k=False)
    if source.stem.startswith("torusg"):
        data = instance.data.copy()
        data[:, 2] = data[:, 2] / 100000.0
        instance = DatInstance(n=instance.n, m=instance.m, k=instance.k, data=data)

    n = instance.n
    W = _symmetric_weight_matrix(instance)
    degree = np.asarray(W.sum(axis=0)).ravel()
    C = 0.5 * (sparse.diags(degree, format="csc") - W)

    diag_positions = np.arange(n, dtype=np.int64) * (n + 1)
    A = sparse.coo_matrix(
        (np.ones(n), (np.arange(n), diag_positions)),
        shape=(n, n * n),
    ).tocsc()
    b = np.ones(n)
    c = _vec_sparse_row(C)
    _save_sedumi(target, A=A, b=b, c=c, K=_k_struct(0, 0, 0, n))


CONVERTERS: dict[str, tuple[bool, Converter]] = {
    "BISECT": (False, convert_bisect),
    "FAP": (True, convert_fap),
    "TORUS": (False, convert_torus),
}


def _dat_header_n(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        return int(handle.readline().split()[0])


def _target_for(source_root: Path, output_root: Path, source: Path, suffix: str | None = None) -> Path:
    relative = source.relative_to(source_root)
    if suffix is not None:
        relative = relative.with_suffix(suffix)
    return output_root / relative


def build_instances(
    source_root: Path,
    output_root: Path,
    *,
    overwrite: bool,
    dry_run: bool,
    max_convert_n: int,
    allow_huge: bool,
    convert_existing_raw: bool,
) -> list[Action]:
    actions: list[Action] = []
    output_root.mkdir(parents=True, exist_ok=True)
    existing_sdp_mats = {
        path.with_suffix(".mat").relative_to(source_root).as_posix()
        for path in sorted(source_root.rglob("*.mat"))
        if classify_file(path).is_sdp
    }

    for source in sorted(source_root.rglob("*")):
        if not source.is_file():
            continue

        classification = classify_file(source)
        family = source.relative_to(source_root).parts[0].upper()

        if classification.is_instance and classification.is_sdp and source.suffix.lower() == ".mat":
            target = _target_for(source_root, output_root, source)
            if target.exists() and not overwrite:
                actions.append(Action(source, target, "exists", "SDP .mat already present"))
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            actions.append(Action(source, target, "copied", "already SDP"))
            continue

        if source.suffix.lower() != ".dat" or family not in CONVERTERS:
            continue

        target = _target_for(source_root, output_root, source, ".mat")
        relative_mat = source.with_suffix(".mat").relative_to(source_root).as_posix()
        if relative_mat in existing_sdp_mats and not convert_existing_raw:
            actions.append(
                Action(
                    source,
                    target,
                    "skipped",
                    "official same-name SDP .mat exists and will be copied",
                )
            )
            continue

        if target.exists() and not overwrite and not convert_existing_raw:
            actions.append(Action(source, target, "skipped", "target SDP .mat already exists"))
            continue

        n = _dat_header_n(source)
        if not allow_huge and n > max_convert_n:
            actions.append(
                Action(
                    source,
                    target,
                    "skipped-huge",
                    f"n={n} exceeds --max-convert-n={max_convert_n}; use --allow-huge to force",
                )
            )
            continue

        _has_k, converter = CONVERTERS[family]
        if not dry_run:
            converter(source, target)
        actions.append(Action(source, target, "converted", f"{family} .dat converted to SDP SeDuMi .mat"))

    return actions


def write_manifest(actions: list[Action], source_root: Path, manifest: Path) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "target", "status", "detail"])
        writer.writeheader()
        for action in actions:
            try:
                source = action.source.relative_to(source_root).as_posix()
            except ValueError:
                source = action.source.as_posix()
            writer.writerow(
                {
                    "source": source,
                    "target": action.target.as_posix(),
                    "status": action.status,
                    "detail": action.detail,
                }
            )


def print_summary(actions: list[Action]) -> None:
    counts: dict[str, int] = {}
    for action in actions:
        counts[action.status] = counts.get(action.status, 0) + 1

    print("Summary")
    for status in sorted(counts):
        print(f"  {status}: {counts[status]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create DIMACS SDP instance directory.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--overwrite", action="store_true", help="replace existing output files")
    parser.add_argument("--dry-run", action="store_true", help="show planned actions without writing files")
    parser.add_argument(
        "--max-convert-n",
        type=int,
        default=5000,
        help="skip raw .dat conversions above this n unless --allow-huge is used",
    )
    parser.add_argument(
        "--allow-huge",
        action="store_true",
        help="allow conversions above --max-convert-n",
    )
    parser.add_argument(
        "--convert-existing-raw",
        action="store_true",
        help="convert raw .dat even when a same-name .mat was copied already",
    )
    args = parser.parse_args(argv)

    source_root = _resolve(args.source)
    output_root = _resolve(args.output)
    manifest = _resolve(args.manifest)

    if not source_root.exists():
        print(f"ERROR: source directory does not exist: {source_root}", file=sys.stderr)
        return 2

    actions = build_instances(
        source_root,
        output_root,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        max_convert_n=args.max_convert_n,
        allow_huge=args.allow_huge,
        convert_existing_raw=args.convert_existing_raw,
    )

    if not args.dry_run:
        write_manifest(actions, source_root, manifest)
        print(f"Manifest written to: {manifest}")
    else:
        for action in actions:
            print(f"{action.status}: {action.source} -> {action.target} ({action.detail})")

    print_summary(actions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
