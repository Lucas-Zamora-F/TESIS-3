from __future__ import annotations

import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
import scipy.io as sio
from scipy.special import boxcox

from tools.features.instance_reader import (
    MatrixEntry,
    ProblemData,
    instance_display_name,
    read_problem_data,
)
from tools.isa.build_metadata.build_features_table import (
    import_extractor_from_path,
    parse_feature_configuration,
)


# =============================================================================
# PROTOCOLS
# =============================================================================

class FixedSpaceProjector(Protocol):
    """
    Object supplied by the caller.

    It must project a metadata_test dataframe into the already-fixed instance
    space and return the coordinates of the candidate row.
    """

    def project(self, metadata_test_df: pd.DataFrame) -> tuple[float, float]:
        ...


class ModelMatProjector:
    """
    Project one metadata_test row into the fixed Instance Space from model.mat.

    This mirrors the relevant InstanceSpace exploreIS steps:
    bound raw features, apply Box-Cox + z-score normalization, select the
    features stored in featsel.idx, then compute z = X * pilot.A'.
    """

    def __init__(self, model_mat_path: str | Path) -> None:
        self.model_mat_path = Path(model_mat_path)
        if not self.model_mat_path.exists():
            raise FileNotFoundError(f"model.mat not found: {self.model_mat_path}")

        model = sio.loadmat(
            self.model_mat_path,
            squeeze_me=True,
            struct_as_record=False,
        )
        self._data = model["data"]
        self._prelim = model["prelim"]
        self._featsel = model["featsel"]
        self._pilot = model["pilot"]

        self.selected_idx = np.atleast_1d(self._featsel.idx).astype(int) - 1
        self.feature_labels = [str(x) for x in np.atleast_1d(self._data.featlabels)]
        if len(self.feature_labels) != len(self.selected_idx):
            raise ValueError(
                "model.mat has inconsistent data.featlabels and featsel.idx lengths: "
                f"{len(self.feature_labels)} vs {len(self.selected_idx)}."
            )
        self.projection_matrix = np.asarray(self._pilot.A, dtype=float)

    def _feature_value(self, row: pd.Series, label: str) -> float:
        candidates = (label, f"feature_{label}")
        for column in candidates:
            if column in row.index:
                value = row[column]
                if pd.isna(value):
                    raise ValueError(f"Feature value is NaN for '{column}'.")
                return float(value)

        raise ValueError(
            f"metadata_test row is missing feature '{label}' "
            f"(also tried 'feature_{label}')."
        )

    def _preprocess(self, raw_x: np.ndarray) -> np.ndarray:
        x = raw_x.astype(float, copy=True)

        lobound = np.asarray(self._prelim.lobound, dtype=float)
        hibound = np.asarray(self._prelim.hibound, dtype=float)
        min_x = np.asarray(self._prelim.minX, dtype=float)
        lambda_x = np.asarray(self._prelim.lambdaX, dtype=float)
        mu_x = np.asarray(self._prelim.muX, dtype=float)
        sigma_x = np.asarray(self._prelim.sigmaX, dtype=float)

        x = np.minimum(np.maximum(x, lobound), hibound)
        x = x - min_x + 1.0
        x = np.maximum(x, np.finfo(float).tiny)
        x = boxcox(x, lambda_x)

        safe_sigma = np.where(sigma_x == 0, 1.0, sigma_x)
        return (x - mu_x) / safe_sigma

    def project(self, metadata_test_df: pd.DataFrame) -> tuple[float, float]:
        metadata_test_df = _normalize_columns(metadata_test_df.copy(), "metadata_test_df")
        if len(metadata_test_df) != 1:
            raise ValueError(
                "ModelMatProjector expects exactly one metadata_test row, "
                f"got {len(metadata_test_df)}."
            )

        row = metadata_test_df.iloc[0]
        raw_x = np.asarray(self._prelim.minX, dtype=float).copy()
        for label, idx in zip(self.feature_labels, self.selected_idx):
            raw_x[idx] = self._feature_value(row, label)

        processed_x = self._preprocess(raw_x)
        selected_x = processed_x[self.selected_idx]
        z = selected_x @ self.projection_matrix.T

        return float(z[0]), float(z[1])


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class InstanceSpaceContext:
    """
    Full context required by the generator.

    This module does NOT load any hardcoded files. Everything must be supplied
    by the caller.
    """
    coordinates_df: pd.DataFrame
    metadata_test_df: pd.DataFrame
    instances_dir: Path
    features_config_path: Path
    projector: FixedSpaceProjector
    instance_paths: dict[str, Path] | None = None
    outline_polygon: "list[tuple[float, float]] | None" = None


@dataclass
class CandidateEvaluation:
    fitness: float
    z1: float
    z2: float
    features_df: pd.DataFrame
    metadata_test_df: pd.DataFrame


@dataclass
class GenerationResult:
    target_z1: float
    target_z2: float
    best_fitness: float
    best_z1: float
    best_z2: float
    output_path: Path
    seed_instance: str
    generations_run: int
    metadata_test_candidate_df: pd.DataFrame
    features_df: pd.DataFrame
    mutation_weights: dict[str, float]


@dataclass
class Individual:
    payload: "MutableInstance"
    evaluation: CandidateEvaluation | None = None
    seed_instance_name: str | None = None


@dataclass
class MutationOutcome:
    payload: "MutableInstance"
    operations: list[str]


class AdaptiveMutationStrategy:
    """
    Lightweight operator weighting for the GA.

    Operators that produce children closer to the target receive more sampling
    weight. Operators that do not help decay gently but never disappear.
    """

    def __init__(
        self,
        rng: random.Random,
        initial_weights: dict[str, float] | None = None,
    ) -> None:
        self.rng = rng
        self.step_scale = 1.0
        self.weights = {
            "scale_C": 1.0,
            "scale_b": 1.0,
            "scale_A": 1.0,
            "perturb_C": 1.0,
            "perturb_A": 1.0,
            "add_C": 1.0,
            "remove_C": 1.0,
            "add_A": 1.0,
            "remove_A": 1.0,
            "add_constraint": 0.7,
            "remove_constraint": 0.7,
        }
        if initial_weights:
            step_value = initial_weights.get("__step_scale")
            if step_value is not None and math.isfinite(float(step_value)):
                self.step_scale = float(min(3.5, max(0.35, step_value)))
            for operation, value in initial_weights.items():
                if operation in self.weights and math.isfinite(float(value)):
                    self.weights[operation] = float(min(6.0, max(0.12, value)))

    def choose(self, np_rng: np.random.Generator) -> str:
        operations = list(self.weights)
        weights = np.array([self.weights[op] for op in operations], dtype=float)
        weights = weights / weights.sum()
        return str(np_rng.choice(operations, p=weights))

    def boost(self, operations: list[str], factor: float) -> None:
        for operation in operations:
            if operation in self.weights:
                self.weights[operation] = float(
                    min(6.0, max(0.12, self.weights[operation] * factor))
                )

    def adapt_step(
        self,
        *,
        previous_best: float,
        current_best: float,
        tolerance: float,
    ) -> None:
        if current_best <= tolerance:
            self.step_scale = max(0.45, self.step_scale * 0.85)
            return

        improvement = max(0.0, previous_best - current_best)
        relative = improvement / max(previous_best, 1e-12)

        if relative < 0.01:
            self.step_scale = min(3.5, self.step_scale * 1.35)
        elif relative < 0.04:
            self.step_scale = min(3.5, self.step_scale * 1.12)
        elif relative > 0.18:
            self.step_scale = max(0.55, self.step_scale * 0.82)
        elif relative > 0.08:
            self.step_scale = max(0.65, self.step_scale * 0.92)

    def learn(
        self,
        operations: list[str],
        parent_fitness: float,
        child_fitness: float,
    ) -> None:
        if not operations:
            return

        improved = child_fitness < parent_fitness
        gain = max(0.0, parent_fitness - child_fitness)
        reward = 1.0 + min(0.5, gain / max(parent_fitness, 1e-12))

        for operation in operations:
            current = self.weights[operation]
            if improved:
                self.weights[operation] = min(5.0, current * reward + 0.05)
            else:
                self.weights[operation] = max(0.15, current * 0.985)


class LocalFeatureSurrogate:
    """
    Local linear model that learns how feature changes move points in z-space.

    The GA still decides by true projected fitness. This guide only nudges the
    mutation operator weights toward operations whose feature deltas line up
    with the estimated feature direction needed to move toward the target.
    """

    def __init__(self, min_samples: int = 8, ridge: float = 1e-3) -> None:
        self.min_samples = min_samples
        self.ridge = ridge
        self.feature_columns: list[str] | None = None
        self.x_samples: list[np.ndarray] = []
        self.z_samples: list[np.ndarray] = []
        self.x_mean: np.ndarray | None = None
        self.x_scale: np.ndarray | None = None
        self.z_mean: np.ndarray | None = None
        self.coef: np.ndarray | None = None
        self.fit_count = 0

    @property
    def ready(self) -> bool:
        return self.coef is not None

    def _vector(self, evaluation: CandidateEvaluation) -> np.ndarray | None:
        df = evaluation.metadata_test_df
        columns = [c for c in df.columns if c.startswith("feature_")]
        if not columns:
            return None

        if self.feature_columns is None:
            self.feature_columns = columns

        row = df.iloc[0]
        values: list[float] = []
        for column in self.feature_columns:
            raw_value = row[column] if column in row.index else 0.0
            value = pd.to_numeric(pd.Series([raw_value]), errors="coerce").iloc[0]
            value = 0.0 if pd.isna(value) else float(value)
            values.append(value if math.isfinite(value) else 0.0)
        return np.asarray(values, dtype=float)

    def add(self, evaluation: CandidateEvaluation) -> None:
        vector = self._vector(evaluation)
        if vector is None:
            return

        self.x_samples.append(vector)
        self.z_samples.append(np.asarray([evaluation.z1, evaluation.z2], dtype=float))
        self._fit()

    def _fit(self) -> None:
        if len(self.x_samples) < self.min_samples:
            return

        x = np.vstack(self.x_samples)
        z = np.vstack(self.z_samples)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)

        self.x_mean = x.mean(axis=0)
        x_scale = x.std(axis=0)
        self.x_scale = np.where(x_scale < 1e-12, 1.0, x_scale)
        self.z_mean = z.mean(axis=0)

        x_scaled = (x - self.x_mean) / self.x_scale
        z_centered = z - self.z_mean
        xtx = x_scaled.T @ x_scaled
        reg = np.eye(xtx.shape[0]) * self.ridge
        self.coef = np.linalg.pinv(xtx + reg) @ x_scaled.T @ z_centered
        self.fit_count += 1

    def _scaled_delta(
        self,
        parent: CandidateEvaluation,
        child: CandidateEvaluation,
    ) -> np.ndarray | None:
        if self.x_scale is None:
            return None

        parent_x = self._vector(parent)
        child_x = self._vector(child)
        if parent_x is None or child_x is None:
            return None
        return (child_x - parent_x) / self.x_scale

    def _desired_feature_direction(
        self,
        parent: CandidateEvaluation,
        target_z1: float,
        target_z2: float,
    ) -> np.ndarray | None:
        if self.coef is None:
            return None

        desired_z = np.asarray(
            [target_z1 - parent.z1, target_z2 - parent.z2],
            dtype=float,
        )
        desired_norm = float(np.linalg.norm(desired_z))
        if desired_norm < 1e-12:
            return None

        gram = self.coef.T @ self.coef
        inv = np.linalg.pinv(gram + np.eye(2) * self.ridge)
        direction = self.coef @ inv @ desired_z
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm < 1e-12:
            return None
        return direction / direction_norm

    def learn(
        self,
        *,
        operations: list[str],
        parent: CandidateEvaluation,
        child: CandidateEvaluation,
        target_z1: float,
        target_z2: float,
        strategy: AdaptiveMutationStrategy,
    ) -> float | None:
        direction = self._desired_feature_direction(parent, target_z1, target_z2)
        delta = self._scaled_delta(parent, child)

        self.add(child)

        if direction is None or delta is None or not operations:
            return None

        delta_norm = float(np.linalg.norm(delta))
        if delta_norm < 1e-12:
            return 0.0

        feature_alignment = float(np.dot(delta / delta_norm, direction))
        parent_to_target = np.asarray([target_z1 - parent.z1, target_z2 - parent.z2])
        parent_to_child = np.asarray([child.z1 - parent.z1, child.z2 - parent.z2])
        z_norm = float(np.linalg.norm(parent_to_target) * np.linalg.norm(parent_to_child))
        z_alignment = (
            0.0
            if z_norm < 1e-12
            else float(np.dot(parent_to_child, parent_to_target) / z_norm)
        )

        score = 0.65 * feature_alignment + 0.35 * z_alignment
        if score > 0.05:
            strategy.boost(operations, 1.0 + min(0.35, 0.08 + 0.18 * score))
        elif score < -0.05:
            strategy.boost(operations, 0.985)

        return score


# =============================================================================
# GEOMETRY HELPERS
# =============================================================================

def _inside_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test."""
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# =============================================================================
# NORMALIZATION HELPERS
# =============================================================================

def _normalize_columns(df: pd.DataFrame, context_name: str) -> pd.DataFrame:
    column_map: dict[str, str] = {}

    for col in df.columns:
        col_lower = col.strip().lower()

        if col_lower in ("instance", "instances", "row"):
            column_map[col] = "Instance"
        elif col_lower == "source":
            column_map[col] = "Source"
        elif col_lower in ("z1", "z_1"):
            column_map[col] = "z_1"
        elif col_lower in ("z2", "z_2"):
            column_map[col] = "z_2"

    df = df.rename(columns=column_map)

    if "Instance" not in df.columns:
        raise ValueError(
            f"{context_name} must contain an Instance-like column. "
            f"Available columns: {list(df.columns)}"
        )

    return df


def _validate_context(context: InstanceSpaceContext) -> InstanceSpaceContext:
    coordinates_df = _normalize_columns(context.coordinates_df.copy(), "coordinates_df")
    metadata_test_df = _normalize_columns(context.metadata_test_df.copy(), "metadata_test_df")

    required_coord_cols = {"Instance", "z_1", "z_2"}
    missing_coord = required_coord_cols - set(coordinates_df.columns)
    if missing_coord:
        raise ValueError(
            f"coordinates_df is missing required columns: {sorted(missing_coord)}"
        )

    feature_cols = [c for c in metadata_test_df.columns if c.startswith("feature_")]
    algo_cols = [c for c in metadata_test_df.columns if c.startswith("algo_")]

    if not feature_cols:
        raise ValueError("metadata_test_df does not contain any feature_* columns.")

    if not algo_cols:
        raise ValueError("metadata_test_df does not contain any algo_* columns.")

    if context.instances_dir is None or not Path(context.instances_dir).exists():
        raise FileNotFoundError(f"instances_dir not found: {context.instances_dir}")

    if context.features_config_path is None or not Path(context.features_config_path).exists():
        raise FileNotFoundError(
            f"features_config_path not found: {context.features_config_path}"
        )

    return InstanceSpaceContext(
        coordinates_df=coordinates_df,
        metadata_test_df=metadata_test_df,
        instances_dir=Path(context.instances_dir),
        features_config_path=Path(context.features_config_path),
        projector=context.projector,
        instance_paths=context.instance_paths,
    )


def _get_feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("feature_")]


# =============================================================================
# SDP SERIALIZATION
# =============================================================================

def write_sdpa_dat_s(data: ProblemData, output_path: Path) -> None:
    """
    Serialize ProblemData as an SDPA .dat-s file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as fh:
        fh.write(f"{data.m}\n")
        fh.write(f"{data.n_blocks}\n")
        fh.write(" ".join(str(b) for b in data.block_sizes) + "\n")
        fh.write(" ".join(repr(v) for v in data.b) + "\n")

        for entry in sorted(
            data.entries,
            key=lambda e: (e.mat_id, e.block_id, e.row, e.col),
        ):
            fh.write(
                f"{entry.mat_id} {entry.block_id} {entry.row} "
                f"{entry.col} {entry.value}\n"
            )


def _prepare_work_dir(work_dir: Path) -> None:
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)


def _cleanup_work_dir(work_dir: Path, keep_work_dir: bool) -> None:
    if keep_work_dir:
        print(f"[INFO] Keeping GA work dir   : {work_dir}")
        return

    if work_dir.exists():
        shutil.rmtree(work_dir)
        print(f"[INFO] Removed GA work dir   : {work_dir}")


# =============================================================================
# MUTABLE SDP REPRESENTATION
# =============================================================================

class MutableInstance:
    """
    Editable in-memory representation of an SDP instance.
    """

    def __init__(
        self,
        m: int,
        n_blocks: int,
        block_sizes: list[int],
        b: list[float],
        entries: dict[tuple[int, int, int, int], float],
    ) -> None:
        self.m = m
        self.n_blocks = n_blocks
        self.block_sizes = list(block_sizes)
        self.b = list(b)
        self.entries = dict(entries)

    @classmethod
    def from_problem_data(cls, data: ProblemData) -> "MutableInstance":
        return cls(
            m=data.m,
            n_blocks=data.n_blocks,
            block_sizes=list(data.block_sizes),
            b=list(data.b),
            entries={(e.mat_id, e.block_id, e.row, e.col): e.value for e in data.entries},
        )

    def to_problem_data(self) -> ProblemData:
        return ProblemData(
            m=self.m,
            n_blocks=self.n_blocks,
            block_sizes=list(self.block_sizes),
            b=list(self.b),
            entries=[
                MatrixEntry(mid, bid, r, c, v)
                for (mid, bid, r, c), v in self.entries.items()
                if v != 0.0
            ],
        )

    def copy(self) -> "MutableInstance":
        return MutableInstance(
            self.m,
            self.n_blocks,
            self.block_sizes,
            self.b,
            self.entries.copy(),
        )

    def scale_C(self, factor: float) -> None:
        for key in list(self.entries):
            if key[0] == 0:
                self.entries[key] *= factor

    def scale_b(self, factor: float) -> None:
        self.b = [v * factor for v in self.b]

    def scale_A(self, factor: float) -> None:
        for key in list(self.entries):
            if key[0] >= 1:
                self.entries[key] *= factor

    def perturb_entries(
        self,
        mat_ids: set[int],
        noise_std: float,
        rng: np.random.Generator,
    ) -> None:
        for key in list(self.entries):
            if key[0] in mat_ids:
                self.entries[key] *= float(np.exp(rng.normal(0.0, noise_std)))

    def _ref_value(self, mat_id: int, rng: np.random.Generator) -> float:
        same = [abs(v) for (mid, *_), v in self.entries.items() if mid == mat_id and v != 0]
        any_a = [abs(v) for (mid, *_), v in self.entries.items() if mid >= 1 and v != 0]
        pool = same or any_a
        base = float(np.median(pool)) if pool else 1.0
        return float(rng.choice([-1.0, 1.0])) * base * float(np.exp(rng.normal(0.0, 0.3)))

    def _sample_positions(
        self,
        mat_id: int,
        n: int,
        rng: np.random.Generator,
    ) -> list[tuple[int, int, int, int]]:
        existing = {
            (mat_id, bid, r, c)
            for (mid, bid, r, c) in self.entries
            if mid == mat_id
        }
        result: list[tuple[int, int, int, int]] = []
        max_attempts = max(50, n * 50)

        for _ in range(max_attempts):
            if len(result) >= n:
                break

            bid_idx = int(rng.integers(0, self.n_blocks))
            bid = bid_idx + 1
            bs = self.block_sizes[bid_idx]

            if bs > 0:
                size = bs
                r = int(rng.integers(1, size + 1))
                c = int(rng.integers(r, size + 1))
            else:
                size = abs(bs)
                r = int(rng.integers(1, size + 1))
                c = r

            key = (mat_id, bid, r, c)
            if key not in existing and key not in result:
                result.append(key)

        return result

    def add_C_entries(self, n: int, rng: np.random.Generator) -> None:
        for key in self._sample_positions(0, n, rng):
            self.entries[key] = self._ref_value(0, rng)

    def remove_C_entries(self, n: int, rng: np.random.Generator) -> None:
        c_keys = [k for k in self.entries if k[0] == 0]
        if len(c_keys) <= 1:
            return

        chosen = rng.choice(len(c_keys), size=min(n, len(c_keys) - 1), replace=False)
        for idx in chosen:
            del self.entries[c_keys[int(idx)]]

    def add_A_entries(self, n: int, rng: np.random.Generator) -> None:
        if self.m == 0:
            return

        mat_id = int(rng.integers(1, self.m + 1))
        for key in self._sample_positions(mat_id, n, rng):
            self.entries[key] = self._ref_value(mat_id, rng)

    def remove_A_entries(self, n: int, rng: np.random.Generator) -> None:
        if self.m == 0:
            return

        mat_id = int(rng.integers(1, self.m + 1))
        a_keys = [k for k in self.entries if k[0] == mat_id]
        if not a_keys:
            return

        chosen = rng.choice(len(a_keys), size=min(n, len(a_keys)), replace=False)
        for idx in chosen:
            del self.entries[a_keys[int(idx)]]

    def add_constraint(self, rng: np.random.Generator) -> None:
        new_mid = self.m + 1
        b_ref = float(np.mean([abs(v) for v in self.b])) if self.b else 1.0

        for key in self._sample_positions(new_mid, int(rng.integers(1, 4)), rng):
            self.entries[key] = self._ref_value(new_mid, rng)

        self.b.append(float(rng.normal(0.0, b_ref + 1e-10)))
        self.m += 1

    def remove_constraint(self, rng: np.random.Generator) -> None:
        if self.m <= 1:
            return

        mat_id = int(rng.integers(1, self.m + 1))

        for key in [k for k in self.entries if k[0] == mat_id]:
            del self.entries[key]

        self.entries = {
            (mid - 1 if mid > mat_id else mid, bid, r, c): v
            for (mid, bid, r, c), v in self.entries.items()
        }

        del self.b[mat_id - 1]
        self.m -= 1


# =============================================================================
# SEED SELECTION
# =============================================================================

def _resolve_instance_path(
    instance_name: str,
    instances_dir: Path,
    instance_paths: dict[str, Path] | None = None,
) -> Path:
    if instance_paths and instance_name in instance_paths:
        path = Path(instance_paths[instance_name])
        if path.exists():
            return path

    candidates = list(instances_dir.rglob(instance_name))
    if not candidates:
        raise FileNotFoundError(
            f"Could not resolve instance '{instance_name}' under {instances_dir}"
        )

    if len(candidates) > 1:
        candidates = sorted(candidates, key=lambda p: (len(str(p)), str(p)))

    return candidates[0]


def _select_nearest_seed_instance(
    coordinates_df: pd.DataFrame,
    target_z1: float,
    target_z2: float,
) -> str:
    coords = coordinates_df.copy()
    coords["distance_to_target"] = np.sqrt(
        (coords["z_1"] - target_z1) ** 2 + (coords["z_2"] - target_z2) ** 2
    )
    coords = coords.sort_values("distance_to_target", ascending=True)

    if coords.empty:
        raise ValueError("coordinates_df is empty.")

    return str(coords.iloc[0]["Instance"])


# =============================================================================
# FEATURE EXTRACTION / PROJECTION
# =============================================================================

def _extract_candidate_features(
    candidate_instance_path: Path,
    features_config_path: Path,
) -> pd.DataFrame:
    _, available_features, group_to_enabled = parse_feature_configuration(
        features_config_path,
    )

    row: dict[str, Any] = {"Instance": instance_display_name(candidate_instance_path)}

    for group_name, enabled_features in group_to_enabled.items():
        extractor_path = available_features[group_name]["extractor"]
        extractor = import_extractor_from_path(extractor_path)

        try:
            feature_dict = extractor(candidate_instance_path)
        except MemoryError:
            feature_dict = {feature_name: None for feature_name in enabled_features}

        for feature_name in enabled_features:
            if feature_name not in feature_dict:
                raise KeyError(
                    f"Feature '{feature_name}' was enabled in group '{group_name}', "
                    f"but extractor '{extractor_path}' did not return it."
                )
            row[feature_name] = feature_dict[feature_name]

    return _normalize_columns(pd.DataFrame([row]), "candidate features")


def _build_candidate_metadata_test(
    candidate_features_df: pd.DataFrame,
    metadata_test_df: pd.DataFrame,
    seed_instance_name: str,
) -> pd.DataFrame:
    """
    Build a 1-row metadata_test candidate using the seed row as template.

    Important:
    - keeps all algo_* columns from the seed row
    - overwrites only feature_* columns with the real candidate features
    - keeps full schema expected by the fixed-space projector
    """
    metadata_test_df = metadata_test_df.copy()
    metadata_test_df = _normalize_columns(metadata_test_df, "metadata_test_df")

    seed_rows = metadata_test_df[metadata_test_df["Instance"] == seed_instance_name]
    if seed_rows.empty:
        raise ValueError(
            f"Seed instance '{seed_instance_name}' was not found in metadata_test_df."
        )

    template_row = seed_rows.iloc[0].copy()
    candidate_row = candidate_features_df.iloc[0].to_dict()

    feature_columns = _get_feature_columns(candidate_features_df)

    for feature_name in feature_columns:
        template_row[feature_name] = candidate_row[feature_name]

    template_row["Instance"] = candidate_row.get("Instance", "candidate.dat-s")

    if "Source" in template_row.index:
        template_row["Source"] = "Genetically Generated to Fill Empty Space"

    return pd.DataFrame([template_row], columns=metadata_test_df.columns)


def _evaluate_candidate(
    payload: MutableInstance,
    output_path: Path,
    context: InstanceSpaceContext,
    target_z1: float,
    target_z2: float,
    seed_instance_name: str,
) -> CandidateEvaluation:
    write_sdpa_dat_s(payload.to_problem_data(), output_path)

    features_df = _extract_candidate_features(
        candidate_instance_path=output_path,
        features_config_path=context.features_config_path,
    )

    metadata_test_candidate_df = _build_candidate_metadata_test(
        candidate_features_df=features_df,
        metadata_test_df=context.metadata_test_df,
        seed_instance_name=seed_instance_name,
    )

    z1, z2 = context.projector.project(metadata_test_candidate_df)

    fitness = float(
        math.sqrt((z1 - target_z1) ** 2 + (z2 - target_z2) ** 2)
    )

    if context.outline_polygon is not None and not _inside_polygon(z1, z2, context.outline_polygon):
        # Heavy penalty: always worse than any in-bounds solution so the GA
        # learns to stay inside the instance space outline.
        fitness = fitness + 10.0 + fitness * 5.0

    return CandidateEvaluation(
        fitness=fitness,
        z1=z1,
        z2=z2,
        features_df=features_df,
        metadata_test_df=metadata_test_candidate_df,
    )


# =============================================================================
# GA OPERATORS
# =============================================================================

def _apply_mutation_operation(
    child: MutableInstance,
    op: str,
    np_rng: np.random.Generator,
    step_scale: float = 1.0,
) -> None:
    step_scale = float(min(3.5, max(0.35, step_scale)))
    add_scale = max(1, int(math.ceil(step_scale)))

    if op == "scale_C":
        child.scale_C(float(np.exp(np_rng.normal(0.0, 0.4 * step_scale))))
    elif op == "scale_b":
        child.scale_b(float(np.exp(np_rng.normal(0.0, 0.4 * step_scale))))
    elif op == "scale_A":
        child.scale_A(float(np.exp(np_rng.normal(0.0, 0.4 * step_scale))))
    elif op == "perturb_C":
        child.perturb_entries({0}, 0.2 * step_scale, np_rng)
    elif op == "perturb_A":
        child.perturb_entries(set(range(1, child.m + 1)), 0.2 * step_scale, np_rng)
    elif op == "add_C":
        child.add_C_entries(int(np_rng.integers(1, 6 * add_scale)), np_rng)
    elif op == "remove_C":
        child.remove_C_entries(int(np_rng.integers(1, 4 * add_scale)), np_rng)
    elif op == "add_A":
        child.add_A_entries(int(np_rng.integers(1, 6 * add_scale)), np_rng)
    elif op == "remove_A":
        child.remove_A_entries(int(np_rng.integers(1, 4 * add_scale)), np_rng)
    elif op == "add_constraint":
        child.add_constraint(np_rng)
    elif op == "remove_constraint":
        child.remove_constraint(np_rng)


def _mutate_payload(
    payload: MutableInstance,
    rng: random.Random,
    strategy: AdaptiveMutationStrategy | None = None,
) -> MutationOutcome:
    child = payload.copy()
    np_rng = np.random.default_rng(rng.randint(0, 2**32 - 1))

    mutation_ops = (
        "scale_C",
        "scale_b",
        "scale_A",
        "perturb_C",
        "perturb_A",
        "add_C",
        "remove_C",
        "add_A",
        "remove_A",
        "add_constraint",
        "remove_constraint",
    )

    step_scale = strategy.step_scale if strategy is not None else 1.0
    max_ops = min(6, max(3, int(math.ceil(2 + step_scale))))
    n_ops = int(np_rng.integers(1, max_ops + 1))
    operations: list[str] = []

    for _ in range(n_ops):
        if strategy is None:
            op = mutation_ops[int(np_rng.integers(0, len(mutation_ops)))]
        else:
            op = strategy.choose(np_rng)

        _apply_mutation_operation(child, op, np_rng, step_scale=step_scale)
        operations.append(op)

    return MutationOutcome(payload=child, operations=operations)


def _crossover_payload(
    parent_a: MutableInstance,
    parent_b: MutableInstance,
    rng: random.Random,
) -> MutableInstance:
    child = parent_a.copy()
    np_rng = np.random.default_rng(rng.randint(0, 2**32 - 1))

    if len(parent_a.b) == len(parent_b.b):
        alpha = float(np_rng.uniform(0.25, 0.75))
        child.b = [
            alpha * a + (1.0 - alpha) * b
            for a, b in zip(parent_a.b, parent_b.b)
        ]

    if parent_a.m == parent_b.m:
        common_keys = set(parent_a.entries.keys()) & set(parent_b.entries.keys())
        for key in common_keys:
            if key[0] >= 1 and np_rng.random() < 0.5:
                alpha = float(np_rng.uniform(0.25, 0.75))
                child.entries[key] = (
                    alpha * parent_a.entries[key]
                    + (1.0 - alpha) * parent_b.entries[key]
                )

    c_keys_b = [k for k in parent_b.entries if k[0] == 0]
    if c_keys_b:
        take = min(len(c_keys_b), int(np_rng.integers(1, min(6, len(c_keys_b)) + 1)))
        chosen = np_rng.choice(len(c_keys_b), size=take, replace=False)
        for idx in chosen:
            key = c_keys_b[int(idx)]
            child.entries[key] = parent_b.entries[key]

    if parent_a.m == parent_b.m:
        a_keys_b = [k for k in parent_b.entries if k[0] >= 1]
        if a_keys_b:
            take = min(len(a_keys_b), int(np_rng.integers(1, min(8, len(a_keys_b)) + 1)))
            chosen = np_rng.choice(len(a_keys_b), size=take, replace=False)
            for idx in chosen:
                key = a_keys_b[int(idx)]
                child.entries[key] = parent_b.entries[key]

    return child


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def generate_instance_for_target(
    *,
    context: InstanceSpaceContext,
    target_z1: float,
    target_z2: float,
    output_path: str | Path,
    mu: int = 10,
    lam: int = 30,
    generations: int = 60,
    tolerance: float = 0.05,
    seed: int = 42,
    keep_work_dir: bool = False,
    verbose_children: bool = True,
    stall_generations: int | None = None,
    mutation_weight_prior: dict[str, float] | None = None,
) -> GenerationResult:
    """
    Generate a new SDP instance targeted to a fixed point in the instance space.

    This function does not run standalone.
    The caller must provide the full instance-space context.
    """
    context = _validate_context(context)

    rng = random.Random(seed)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("GENERATE INSTANCE FOR TARGET")
    print("=" * 80)
    print(f"[INFO] Target z               : ({target_z1:.6f}, {target_z2:.6f})")
    print(f"[INFO] Output path            : {output_path}")
    print(f"[INFO] Population size (mu)   : {mu}")
    print(f"[INFO] Offspring size (lam)   : {lam}")
    print(f"[INFO] Generations           : {generations}")
    print(f"[INFO] Tolerance             : {tolerance}")
    print(f"[INFO] Random seed           : {seed}")
    print("[INFO] Local feature guide   : enabled")

    seed_instance_name = _select_nearest_seed_instance(
        coordinates_df=context.coordinates_df,
        target_z1=target_z1,
        target_z2=target_z2,
    )
    seed_instance_path = _resolve_instance_path(
        seed_instance_name,
        context.instances_dir,
        context.instance_paths,
    )

    print(f"[INFO] Selected seed instance : {seed_instance_name}")
    print(f"[INFO] Seed path              : {seed_instance_path}")

    seed_payload = MutableInstance.from_problem_data(read_problem_data(seed_instance_path))
    mutation_strategy = AdaptiveMutationStrategy(rng, initial_weights=mutation_weight_prior)
    feature_surrogate = LocalFeatureSurrogate(
        min_samples=max(6, min(12, mu + 4)),
        ridge=1e-3,
    )
    surrogate_was_ready = False

    work_dir = output_path.parent / "_ga_work"
    _prepare_work_dir(work_dir)

    population: list[Individual] = []

    print("\n[INFO] Building initial population...")
    for idx in range(mu):
        if idx == 0:
            payload = seed_payload.copy()
        else:
            payload = _mutate_payload(seed_payload, rng, mutation_strategy).payload

        candidate_path = work_dir / f"init_{idx + 1:03d}.dat-s"
        evaluation = _evaluate_candidate(
            payload=payload,
            output_path=candidate_path,
            context=context,
            target_z1=target_z1,
            target_z2=target_z2,
            seed_instance_name=seed_instance_name,
        )

        population.append(
            Individual(
                payload=payload,
                evaluation=evaluation,
                seed_instance_name=seed_instance_name,
            )
        )
        feature_surrogate.add(evaluation)

        print(
            f"[INIT {idx + 1:03d}] "
            f"fitness={evaluation.fitness:.6f} "
            f"z=({evaluation.z1:.6f}, {evaluation.z2:.6f})"
        )

    best = min(population, key=lambda ind: ind.evaluation.fitness)

    print("\n[INFO] Initial best:")
    print(
        f"       fitness={best.evaluation.fitness:.6f} "
        f"z=({best.evaluation.z1:.6f}, {best.evaluation.z2:.6f})"
    )

    generations_run = 0
    generations_without_improvement = 0

    if best.evaluation.fitness > tolerance:
        for generation in range(1, generations + 1):
            generations_run = generation
            print(f"\n[GENERATION {generation:03d}]")

            population = sorted(population, key=lambda ind: ind.evaluation.fitness)
            parents = population[:mu]

            offspring: list[Individual] = []
            surrogate_scores: list[float] = []

            for child_idx in range(lam):
                parent_a = rng.choice(parents)
                parent_b = rng.choice(parents)

                if rng.random() < 0.5:
                    child_payload = _crossover_payload(parent_a.payload, parent_b.payload, rng)
                else:
                    child_payload = parent_a.payload.copy()

                parent_reference = (
                    parent_a
                    if parent_a.evaluation.fitness <= parent_b.evaluation.fitness
                    else parent_b
                )
                parent_reference_fitness = parent_reference.evaluation.fitness
                mutation = _mutate_payload(child_payload, rng, mutation_strategy)
                child_payload = mutation.payload

                candidate_path = work_dir / f"gen_{generation:03d}_{child_idx + 1:03d}.dat-s"
                child_eval = _evaluate_candidate(
                    payload=child_payload,
                    output_path=candidate_path,
                    context=context,
                    target_z1=target_z1,
                    target_z2=target_z2,
                    seed_instance_name=seed_instance_name,
                )
                mutation_strategy.learn(
                    operations=mutation.operations,
                    parent_fitness=parent_reference_fitness,
                    child_fitness=child_eval.fitness,
                )
                surrogate_score = feature_surrogate.learn(
                    operations=mutation.operations,
                    parent=parent_reference.evaluation,
                    child=child_eval,
                    target_z1=target_z1,
                    target_z2=target_z2,
                    strategy=mutation_strategy,
                )
                if surrogate_score is not None:
                    surrogate_scores.append(surrogate_score)

                offspring.append(
                    Individual(
                        payload=child_payload,
                        evaluation=child_eval,
                        seed_instance_name=seed_instance_name,
                    )
                )

                if verbose_children:
                    print(
                        f"  [CHILD {child_idx + 1:03d}] "
                        f"fitness={child_eval.fitness:.6f} "
                        f"z=({child_eval.z1:.6f}, {child_eval.z2:.6f})"
                    )

            population = sorted(
                parents + offspring,
                key=lambda ind: ind.evaluation.fitness,
            )[:mu]

            if feature_surrogate.ready and not surrogate_was_ready:
                print(
                    "[GUIDE] Local feature regression is active "
                    f"({len(feature_surrogate.x_samples)} samples)."
                )
                surrogate_was_ready = True

            previous_best_fitness = best.evaluation.fitness
            if population[0].evaluation.fitness < best.evaluation.fitness:
                best = population[0]
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1
            mutation_strategy.adapt_step(
                previous_best=previous_best_fitness,
                current_best=best.evaluation.fitness,
                tolerance=tolerance,
            )

            if not verbose_children:
                generation_best = population[0].evaluation
                guide_text = ""
                if surrogate_scores:
                    guide_text = (
                        " guide_alignment="
                        f"{float(np.mean(surrogate_scores)):.3f}"
                    )
                print(
                    f"  [GEN SUMMARY] best_in_generation="
                    f"{generation_best.fitness:.6f} "
                    f"z=({generation_best.z1:.6f}, {generation_best.z2:.6f})"
                    f"{guide_text}"
                    f" step_scale={mutation_strategy.step_scale:.2f}"
                )

            print(
                f"[BEST] fitness={best.evaluation.fitness:.6f} "
                f"z=({best.evaluation.z1:.6f}, {best.evaluation.z2:.6f})"
            )

            if best.evaluation.fitness <= tolerance:
                print("[STOP] Tolerance reached.")
                break

            if (
                stall_generations is not None
                and generations_without_improvement >= stall_generations
            ):
                print(
                    "[STOP] No improvement for "
                    f"{generations_without_improvement} generations."
                )
                break
    else:
        print("[STOP] Initial population already satisfies tolerance.")

    write_sdpa_dat_s(best.payload.to_problem_data(), output_path)
    _cleanup_work_dir(work_dir, keep_work_dir=keep_work_dir)

    print("\n" + "=" * 80)
    print("FINAL RESULT")
    print("=" * 80)
    print(f"[DONE] Output      : {output_path}")
    print(f"[DONE] Fitness     : {best.evaluation.fitness:.6f}")
    print(f"[DONE] Projected z : ({best.evaluation.z1:.6f}, {best.evaluation.z2:.6f})")

    return GenerationResult(
        target_z1=target_z1,
        target_z2=target_z2,
        best_fitness=best.evaluation.fitness,
        best_z1=best.evaluation.z1,
        best_z2=best.evaluation.z2,
        output_path=output_path,
        seed_instance=seed_instance_name,
        generations_run=generations_run,
        metadata_test_candidate_df=best.evaluation.metadata_test_df,
        features_df=best.evaluation.features_df,
        mutation_weights={
            **dict(mutation_strategy.weights),
            "__step_scale": mutation_strategy.step_scale,
        },
    )
