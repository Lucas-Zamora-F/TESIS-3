from __future__ import annotations

import pandas as pd


def build_isa_metadata_table(
    features_df: pd.DataFrame,
    solver_runtime_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combina dos dataframes por la columna 'Instance' y retorna el resultado.

    Orden final de columnas:
        1. Instances
        2. todas las columnas feature_*
        3. todas las columnas algo_*
        4. cualquier otra columna restante

    Parámetros
    ----------
    features_df : pd.DataFrame
        DataFrame con columnas de features y una columna 'Instance'.
    solver_runtime_df : pd.DataFrame
        DataFrame con columnas de runtimes (algo_*) y una columna 'Instance'.

    Retorna
    -------
    pd.DataFrame
        DataFrame combinado final.
    """
    _validate_input_dataframe(features_df, "features_df")
    _validate_input_dataframe(solver_runtime_df, "solver_runtime_df")

    # Copias para no modificar los dataframes originales
    features_df = features_df.copy()
    solver_runtime_df = solver_runtime_df.copy()

    # Validación de duplicados en la llave de merge
    _validate_no_duplicate_instances(features_df, "features_df")
    _validate_no_duplicate_instances(solver_runtime_df, "solver_runtime_df")

    # Merge por la columna común
    merged_df = pd.merge(
        features_df,
        solver_runtime_df,
        on="Instance",
        how="inner",
        validate="one_to_one",
    )

    if merged_df.empty:
        raise ValueError(
            "El merge entre features_df y solver_runtime_df produjo un dataframe vacío. "
            "Revisa que ambos compartan valores en la columna 'Instance'."
        )

    # Renombrar la primera columna a 'Instances'
    merged_df = merged_df.rename(columns={"Instance": "Instances"})

    # Reordenar columnas
    ordered_columns = _build_ordered_columns(merged_df)
    merged_df = merged_df[ordered_columns]

    return merged_df


def _validate_input_dataframe(df: pd.DataFrame, df_name: str) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"{df_name} debe ser un pandas.DataFrame.")

    if "Instance" not in df.columns:
        raise ValueError(f"{df_name} debe contener la columna 'Instance'.")

    if df.empty:
        raise ValueError(f"{df_name} está vacío.")


def _validate_no_duplicate_instances(df: pd.DataFrame, df_name: str) -> None:
    duplicated = df[df["Instance"].duplicated(keep=False)]["Instance"].tolist()
    if duplicated:
        raise ValueError(
            f"{df_name} contiene valores duplicados en 'Instance': {duplicated}"
        )


def _build_ordered_columns(df: pd.DataFrame) -> list[str]:
    all_columns = df.columns.tolist()

    if "Instances" not in all_columns:
        raise ValueError("El dataframe final no contiene la columna 'Instances'.")

    feature_columns = sorted([col for col in all_columns if col.startswith("feature_")])
    algo_columns = sorted([col for col in all_columns if col.startswith("algo_")])

    remaining_columns = [
        col
        for col in all_columns
        if col not in ["Instances"] + feature_columns + algo_columns
    ]

    return ["Instances"] + feature_columns + algo_columns + remaining_columns