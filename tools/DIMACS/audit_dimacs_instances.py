#!/usr/bin/env python
"""Audit extracted DIMACS files and classify optimization/SDP instances.

By default this scans data/instances/DIMACS/extracted and prints a CSV with one
row per file. The classifier is intentionally conservative:

- MATLAB files with SeDuMi-style variables (A/At, b, c, K) are optimization
  instances. They are SDP instances when K.s is present and non-empty.
- SDPA sparse text files (.dat-s/.sdpa) are SDP instances when their block
  structure contains at least one positive block size.
- Raw DIMACS-style .dat files are data instances, but not SDP formulations.
- MATLAB .m files and unrecognized/binary files are not counted as instances.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_ROOT = Path("data/instances/DIMACS/extracted")


FAMILY_METADATA = {
    "ANTENNA": {
        "description": "Antenna array design problems",
        "conversion_note": "SeDuMi cone model; not necessarily SDP unless K.s is present.",
    },
    "BISECT": {
        "description": "Min bisection problems from circuit partitioning",
        "conversion_note": "Raw .dat graph files can be converted with genbisect.m/vec.m when available.",
    },
    "COPOS": {
        "description": "Checking a sufficient condition for copositivity of a matrix",
        "conversion_note": "Distributed as SeDuMi SDP instances.",
    },
    "FAP": {
        "description": "Min k-uncut problems from frequency assignment",
        "conversion_note": "Raw .dat graph files can be converted with genfap.m when available; fap36 has no .mat listed upstream.",
    },
    "FILTER": {
        "description": "Mixed SDP/SOCP problems from PAM filter design",
        "conversion_note": "Mixed cone SeDuMi models; SDP status depends on K.s.",
    },
    "HAMMING": {
        "description": "Theta function instances of Hamming graphs",
        "conversion_note": "Distributed as SDP instances; generate_hamming.m can create more.",
    },
    "HINF": {
        "description": "LMI problems",
        "conversion_note": "LMI models are SDP instances.",
    },
    "NQL": {
        "description": "Quadratic plastic-collapse problems: plain strain models",
        "conversion_note": "Quadratic cone SeDuMi models; converting to SDP would be a reformulation/lifting.",
    },
    "QSSP": {
        "description": "Quadratic plastic-collapse problems: supported plate models",
        "conversion_note": "Quadratic cone SeDuMi models; converting to SDP would be a reformulation/lifting.",
    },
    "SCHED": {
        "description": "Quadratic relaxations of scheduling problems",
        "conversion_note": "Quadratic cone SeDuMi models; scaled files are reformulations with c_mult.",
    },
    "TORUS": {
        "description": "Max-cut problems from the Ising model of spin glasses",
        "conversion_note": "Raw .dat graph files can be converted with gentorus.m when available.",
    },
    "TRUSS": {
        "description": "Truss topology design problems",
        "conversion_note": "Distributed as SeDuMi SDP instances.",
    },
}


@dataclass(frozen=True)
class Classification:
    is_instance: bool
    is_sdp: bool
    kind: str
    reason: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _as_float(value: str) -> float | None:
    try:
        return float(value.replace("D", "E").replace("d", "e"))
    except ValueError:
        return None


def _as_int(value: str) -> int | None:
    number = _as_float(value)
    if number is None or not math.isfinite(number) or not number.is_integer():
        return None
    return int(number)


def _numeric_lines(path: Path, limit: int = 10000) -> Iterable[list[str]]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for index, raw_line in enumerate(handle):
            if index >= limit:
                break
            line = raw_line.strip()
            if not line or line.startswith(('"', "*", "#", "%")):
                continue
            yield line.split()


def _classify_dimacs_dat(path: Path) -> Classification:
    """Detect raw DIMACS graph-like files.

    The extracted DIMACS .dat files in this dataset use a compact numeric form:
    first line "n m" or "n m k", followed by edge/entry rows "i j value".
    These are problem data instances, but not SDP solver-ready formulations.
    """
    try:
        rows = list(_numeric_lines(path, limit=200))
    except OSError as exc:
        return Classification(False, False, "unreadable", f"cannot read text: {exc}")

    if not rows:
        return Classification(False, False, "empty", "empty or comment-only file")

    header = rows[0]
    if len(header) not in (2, 3) or any(_as_int(token) is None for token in header):
        return Classification(False, False, "text", "header is not DIMACS numeric data")

    n = _as_int(header[0])
    m = _as_int(header[1])
    if n is None or m is None or n <= 0 or m < 0:
        return Classification(False, False, "text", "invalid DIMACS dimensions")

    checked = 0
    for row in rows[1:]:
        if len(row) < 3:
            continue
        i = _as_int(row[0])
        j = _as_int(row[1])
        value = _as_float(row[2])
        if i is None or j is None or value is None:
            continue
        if not (1 <= i <= n and 1 <= j <= n):
            return Classification(False, False, "text", "entry index outside header dimensions")
        checked += 1
        if checked >= 5:
            break

    if m > 0 and checked == 0:
        return Classification(False, False, "text", "no valid DIMACS data rows found")

    return Classification(
        True,
        False,
        "raw-dimacs-data",
        "numeric DIMACS data file; not a solver-ready SDP formulation",
    )


def _classify_sdpa_text(path: Path) -> Classification:
    """Detect sparse SDPA text format used by SDPLIB (.dat-s)."""
    try:
        rows = list(_numeric_lines(path, limit=1000))
    except OSError as exc:
        return Classification(False, False, "unreadable", f"cannot read text: {exc}")

    if len(rows) < 4:
        return Classification(False, False, "text", "too few numeric lines for SDPA")

    m = _as_int(rows[0][0]) if len(rows[0]) == 1 else None
    n_blocks = _as_int(rows[1][0]) if len(rows[1]) == 1 else None
    if m is None or n_blocks is None or m <= 0 or n_blocks <= 0:
        return Classification(False, False, "text", "missing SDPA m/block header")

    block_sizes = [_as_int(token) for token in rows[2]]
    if len(block_sizes) != n_blocks or any(size is None or size == 0 for size in block_sizes):
        return Classification(False, False, "text", "invalid SDPA block structure")

    c_values = [_as_float(token) for token in rows[3]]
    if len(c_values) != m or any(value is None for value in c_values):
        return Classification(False, False, "text", "invalid SDPA objective vector")

    is_sdp = any(size is not None and size > 0 for size in block_sizes)
    cone = "has semidefinite blocks" if is_sdp else "has only linear diagonal blocks"
    return Classification(True, is_sdp, "sdpa-text", cone)


def _has_nonempty_numeric(value: Any) -> bool:
    try:
        import numpy as np
    except Exception:
        np = None

    if value is None:
        return False
    if np is not None:
        array = np.asarray(value)
        if array.size == 0:
            return False
        return any(float(item) != 0 for item in array.ravel())
    if isinstance(value, (list, tuple)):
        return any(_has_nonempty_numeric(item) for item in value)
    try:
        return float(value) != 0
    except Exception:
        return False


def _get_struct_field(obj: Any, name: str) -> Any:
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name)
    try:
        return obj[name]
    except Exception:
        return None


def _classify_mat(path: Path) -> Classification:
    try:
        import scipy.io as sio
    except Exception as exc:
        return Classification(False, False, "matlab-mat", f"scipy unavailable: {exc}")

    try:
        variables = {name for name, _shape, _class in sio.whosmat(path)}
    except Exception as exc:
        return Classification(False, False, "matlab-mat", f"cannot inspect .mat file: {exc}")

    has_sedumi = "K" in variables and {"b", "c"}.issubset(variables) and bool(
        {"A", "At"} & variables
    )
    has_sdpt3 = {"blk", "At", "C", "b"}.issubset(variables)

    if not has_sedumi and not has_sdpt3:
        return Classification(False, False, "matlab-mat", "missing known SDP solver variables")

    if has_sdpt3:
        return Classification(
            True,
            True,
            "sdpt3-mat",
            "contains SDPT3 variables blk/At/C/b",
        )

    try:
        data = sio.loadmat(path, variable_names=["K"], squeeze_me=True, struct_as_record=False)
        k_struct = data.get("K")
        has_sdp_cone = _has_nonempty_numeric(_get_struct_field(k_struct, "s"))
    except Exception as exc:
        return Classification(True, False, "sedumi-mat", f"could not read K.s: {exc}")

    if has_sdp_cone:
        return Classification(True, True, "sedumi-mat", "contains SeDuMi K.s semidefinite cone")

    return Classification(True, False, "sedumi-mat", "SeDuMi instance without K.s cone")


def classify_file(path: Path) -> Classification:
    suffix = path.suffix.lower()
    name = path.name.lower()

    if suffix == ".m":
        return Classification(False, False, "matlab-script", "source/generator script")
    if suffix == ".mat":
        return _classify_mat(path)
    if name.endswith(".dat-s") or suffix in {".sdpa", ".sdp"}:
        return _classify_sdpa_text(path)
    if suffix == ".dat":
        return _classify_dimacs_dat(path)
    return Classification(False, False, "unknown", f"unsupported extension '{path.suffix}'")


def iter_files(root: Path) -> Iterable[Path]:
    return (path for path in sorted(root.rglob("*")) if path.is_file())


def audit(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in iter_files(root):
        result = classify_file(path)
        relative = path.relative_to(root)
        family = relative.parts[0] if len(relative.parts) > 1 else ""
        metadata = FAMILY_METADATA.get(family.upper(), {})
        rows.append(
            {
                "path": relative.as_posix(),
                "family": family,
                "official_description": metadata.get("description", ""),
                "extension": path.suffix.lower(),
                "size_bytes": str(path.stat().st_size),
                "is_instance": str(result.is_instance).lower(),
                "is_sdp": str(result.is_sdp).lower() if result.is_instance else "",
                "kind": result.kind,
                "reason": result.reason,
                "conversion_note": metadata.get("conversion_note", ""),
            }
        )
    return rows


def print_summary(rows: list[dict[str, str]]) -> None:
    total = len(rows)
    instances = sum(row["is_instance"] == "true" for row in rows)
    sdp = sum(row["is_sdp"] == "true" for row in rows)
    non_sdp_instances = sum(
        row["is_instance"] == "true" and row["is_sdp"] == "false" for row in rows
    )
    not_instances = total - instances

    print()
    print("Summary")
    print(f"  files:             {total}")
    print(f"  instances:         {instances}")
    print(f"  SDP instances:     {sdp}")
    print(f"  non-SDP instances: {non_sdp_instances}")
    print(f"  not instances:     {not_instances}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit extracted DIMACS files and classify SDP instances."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"directory to scan (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="optional path where the CSV report will be written",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="do not print the per-file CSV to stdout",
    )
    args = parser.parse_args(argv)

    root = args.root
    if not root.is_absolute():
        root = _repo_root() / root
    root = root.resolve()

    if not root.exists() or not root.is_dir():
        print(f"ERROR: root directory does not exist: {root}", file=sys.stderr)
        return 2

    rows = audit(root)
    fieldnames = [
        "path",
        "family",
        "official_description",
        "extension",
        "size_bytes",
        "is_instance",
        "is_sdp",
        "kind",
        "reason",
        "conversion_note",
    ]

    if not args.summary_only:
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    if args.csv:
        output = args.csv
        if not output.is_absolute():
            output = _repo_root() / output
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nCSV report written to: {output}")

    print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
