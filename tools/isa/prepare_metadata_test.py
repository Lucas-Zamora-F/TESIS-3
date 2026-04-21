from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_METADATA = PROJECT_ROOT / "ISA metadata" / "metadata.csv"
DEFAULT_OUTPUT_METADATA_TEST = PROJECT_ROOT / "ISA metadata" / "metadata_test.csv"


def _normalize_core_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    for col in df.columns:
        lowered = col.lower()
        if lowered == "instances" and col != "instances":
            rename_map[col] = "instances"
        elif lowered == "source" and col != "source":
            rename_map[col] = "source"

    if rename_map:
        df = df.rename(columns=rename_map)

    if "instances" not in df.columns:
        raise ValueError("CSV must contain an 'instances' column.")

    df["instances"] = df["instances"].astype(str)
    return df


def _read_metadata(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    return _normalize_core_columns(pd.read_csv(path))


def _prefixed_columns(df: pd.DataFrame, prefix: str) -> list[str]:
    return [col for col in df.columns if col.startswith(prefix)]


def _validate_patch_columns(
    patch: pd.DataFrame,
    allowed_prefixes: Iterable[str],
    patch_name: str,
) -> None:
    allowed = {"instances", "source"}
    allowed.update(
        col
        for col in patch.columns
        if any(col.startswith(prefix) for prefix in allowed_prefixes)
    )
    unexpected = [col for col in patch.columns if col not in allowed]
    if unexpected:
        prefixes = ", ".join(f"'{prefix}*'" for prefix in allowed_prefixes)
        raise ValueError(
            f"{patch_name} contains unsupported columns: {unexpected}. "
            f"Use only 'instances', optional 'source', and {prefixes} columns."
        )


def _merge_patch(
    base: pd.DataFrame,
    patch: pd.DataFrame,
    value_prefixes: Iterable[str],
    patch_name: str,
    allow_new_instances: bool,
) -> pd.DataFrame:
    patch = _normalize_core_columns(patch)
    _validate_patch_columns(patch, value_prefixes, patch_name)

    if patch["instances"].duplicated().any():
        duplicated = patch.loc[patch["instances"].duplicated(), "instances"].tolist()
        raise ValueError(f"{patch_name} has duplicated instances: {duplicated[:10]}")

    if not allow_new_instances:
        missing = sorted(set(patch["instances"]) - set(base["instances"]))
        if missing:
            raise ValueError(
                f"{patch_name} references instances not present in the base metadata: "
                f"{missing[:10]}"
            )

    base = base.set_index("instances", drop=False)
    patch = patch.set_index("instances", drop=False)

    for col in patch.columns:
        if col == "instances":
            continue
        if col not in base.columns:
            base[col] = pd.NA
        base.loc[patch.index, col] = patch[col]

    return base.reset_index(drop=True)


def _append_instances(base: pd.DataFrame, new_instances: pd.DataFrame) -> pd.DataFrame:
    new_instances = _normalize_core_columns(new_instances)
    _validate_patch_columns(
        new_instances,
        allowed_prefixes=("feature_", "algo_"),
        patch_name="--add-instances",
    )

    duplicate_with_base = sorted(set(new_instances["instances"]) & set(base["instances"]))
    if duplicate_with_base:
        raise ValueError(
            "--add-instances contains instances already present in the base metadata: "
            f"{duplicate_with_base[:10]}"
        )

    if new_instances["instances"].duplicated().any():
        duplicated = new_instances.loc[
            new_instances["instances"].duplicated(), "instances"
        ].tolist()
        raise ValueError(f"--add-instances has duplicated instances: {duplicated[:10]}")

    return pd.concat([base, new_instances], ignore_index=True, sort=False)


def _order_columns(df: pd.DataFrame) -> pd.DataFrame:
    core_cols = [col for col in ("instances", "source") if col in df.columns]
    feature_cols = sorted(_prefixed_columns(df, "feature_"))
    algo_cols = sorted(_prefixed_columns(df, "algo_"))
    other_cols = [
        col
        for col in df.columns
        if col not in set(core_cols + feature_cols + algo_cols)
    ]
    return df[core_cols + feature_cols + algo_cols + other_cols]


def _print_summary(df: pd.DataFrame, output: Path) -> None:
    feature_cols = _prefixed_columns(df, "feature_")
    algo_cols = _prefixed_columns(df, "algo_")
    print("[OK] Wrote metadata_test.csv")
    print(f"[INFO] Output             : {output}")
    print(f"[INFO] Instances          : {len(df)}")
    print(f"[INFO] Feature columns    : {len(feature_cols)}")
    print(f"[INFO] Algorithm columns  : {len(algo_cols)}")


def build_metadata_test(
    base_metadata: Path = DEFAULT_BASE_METADATA,
    output: Path = DEFAULT_OUTPUT_METADATA_TEST,
    add_instances: Path | None = None,
    add_features: Path | None = None,
    add_algorithms: Path | None = None,
) -> Path:
    df = _read_metadata(base_metadata)

    if add_instances is not None:
        df = _append_instances(df, _read_metadata(add_instances))

    if add_features is not None:
        df = _merge_patch(
            df,
            _read_metadata(add_features),
            value_prefixes=("feature_",),
            patch_name="--add-features",
            allow_new_instances=False,
        )

    if add_algorithms is not None:
        df = _merge_patch(
            df,
            _read_metadata(add_algorithms),
            value_prefixes=("algo_",),
            patch_name="--add-algorithms",
            allow_new_instances=False,
        )

    df = _order_columns(df)

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    _print_summary(df, output)
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a metadata_test.csv by optionally appending instances and "
            "merging feature_/algo_ columns by instance name."
        )
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=DEFAULT_BASE_METADATA,
        help="Base metadata CSV. Default: ISA metadata/metadata.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_METADATA_TEST,
        help="Output metadata_test.csv path. Default: ISA metadata/metadata_test.csv",
    )
    parser.add_argument(
        "--add-instances",
        type=Path,
        help="CSV with new rows. Columns must be instances, optional source, feature_*, algo_*.",
    )
    parser.add_argument(
        "--add-features",
        type=Path,
        help="CSV keyed by instances with feature_* columns to add or overwrite.",
    )
    parser.add_argument(
        "--add-algorithms",
        type=Path,
        help="CSV keyed by instances with algo_* columns to add or overwrite.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    build_metadata_test(
        base_metadata=args.base,
        output=args.output,
        add_instances=args.add_instances,
        add_features=args.add_features,
        add_algorithms=args.add_algorithms,
    )


if __name__ == "__main__":
    main()
