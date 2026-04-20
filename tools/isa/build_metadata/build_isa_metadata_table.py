from __future__ import annotations

import pandas as pd


def build_isa_metadata_table(
    features_df: pd.DataFrame,
    solver_runtime_df: pd.DataFrame,
    source_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge three dataframes on the 'Instance' column and return the result.

    Final column order:
        1. Instances
        2. Source
        3. all feature_* columns
        4. all algo_* columns
        5. any remaining columns

    Parameters
    ----------
    features_df : pd.DataFrame
        DataFrame containing feature columns and 'Instance'.
    solver_runtime_df : pd.DataFrame
        DataFrame containing runtime columns (algo_*) and 'Instance'.
    source_df : pd.DataFrame
        DataFrame containing 'Instance' and 'Source'.

    Returns
    -------
    pd.DataFrame
        Final merged dataframe.
    """
    _validate_input_dataframe(features_df, "features_df")
    _validate_input_dataframe(solver_runtime_df, "solver_runtime_df")
    _validate_input_dataframe(source_df, "source_df")

    _validate_required_columns(source_df, "source_df", ["Instance", "Source"])

    # Copy to avoid mutating original inputs
    features_df = features_df.copy()
    solver_runtime_df = solver_runtime_df.copy()
    source_df = source_df.copy()

    # Validate uniqueness of merge key
    _validate_no_duplicate_instances(features_df, "features_df")
    _validate_no_duplicate_instances(solver_runtime_df, "solver_runtime_df")
    _validate_no_duplicate_instances(source_df, "source_df")

    # Merge features + solver runtimes
    merged_df = pd.merge(
        features_df,
        solver_runtime_df,
        on="Instance",
        how="inner",
        validate="one_to_one",
    )

    # Merge with source table
    merged_df = pd.merge(
        merged_df,
        source_df,
        on="Instance",
        how="inner",
        validate="one_to_one",
    )

    if merged_df.empty:
        raise ValueError(
            "Final merge produced an empty dataframe. "
            "Check that all inputs share common 'Instance' values."
        )

    # Rename main column
    merged_df = merged_df.rename(columns={"Instance": "Instances"})

    # Reorder columns
    ordered_columns = _build_ordered_columns(merged_df)
    merged_df = merged_df[ordered_columns]

    return merged_df


def _validate_input_dataframe(df: pd.DataFrame, df_name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{df_name} must be a pandas.DataFrame.")

    if "Instance" not in df.columns:
        raise ValueError(f"{df_name} must contain the 'Instance' column.")

    if df.empty:
        raise ValueError(f"{df_name} is empty.")


def _validate_required_columns(
    df: pd.DataFrame,
    name: str,
    required_columns: list[str],
) -> None:
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"{name} is missing required columns: {missing_columns}"
        )


def _validate_no_duplicate_instances(df: pd.DataFrame, df_name: str) -> None:
    duplicated = df[df["Instance"].duplicated(keep=False)]["Instance"].tolist()
    if duplicated:
        raise ValueError(
            f"{df_name} contains duplicate values in 'Instance': {duplicated}"
        )


def _build_ordered_columns(df: pd.DataFrame) -> list[str]:
    all_columns = df.columns.tolist()

    if "Instances" not in all_columns:
        raise ValueError("Final dataframe does not contain 'Instances' column.")

    # Identify column groups
    feature_columns = sorted([col for col in all_columns if col.startswith("feature_")])
    algo_columns = sorted([col for col in all_columns if col.startswith("algo_")])
    source_column = ["Source"] if "Source" in all_columns else []

    remaining_columns = [
        col
        for col in all_columns
        if col not in ["Instances"] + source_column + feature_columns + algo_columns
    ]

    return (
        ["Instances"]
        + source_column
        + feature_columns
        + algo_columns
        + remaining_columns
    )