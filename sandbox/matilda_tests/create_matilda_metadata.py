from __future__ import annotations

import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent

INSTANCES_DIR = PROJECT_ROOT / "data" / "instances" / "sdplib"

OUTPUT_MATILDA_CSV = SCRIPT_DIR / "matilda_metadata.csv"
OUTPUT_DIAGNOSTIC_CSV = SCRIPT_DIR / "matilda_metadata_diagnostic.csv"


if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from tools.sdp_feature_extractor import extract_features_for_directory
from tools.sedumi_wrapper import solve_sedumi_batch
from tools.sdpt3_wrapper import solve_sdpt3_batch


def natural_sort_key(path: Path):
    import re
    parts = re.split(r"(\d+)", path.stem.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def run_sedumi(instance_paths):
    return solve_sedumi_batch(instance_paths)


def run_sdpt3(instance_paths):
    return solve_sdpt3_batch(instance_paths)


def build_invalid_reasons(row: pd.Series, has_error_column: bool) -> str:

    motivos = []

    if has_error_column and pd.notna(row.get("error")):
        motivos.append(f"feature_error={row.get('error')}")

    if pd.isna(row.get("feature_size")):
        motivos.append("feature_size=NaN")

    if pd.isna(row.get("feature_sparsity")):
        motivos.append("feature_sparsity=NaN")

    if pd.isna(row.get("feature_scaling")):
        motivos.append("feature_scaling=NaN")

    if pd.isna(row.get("algo_sedumi")):
        motivos.append("algo_sedumi=NaN")

    if pd.isna(row.get("algo_sdpt3")):
        motivos.append("algo_sdpt3=NaN")

    return "; ".join(motivos)


def main() -> None:

    if not INSTANCES_DIR.exists():
        raise FileNotFoundError(f"No se encontró la carpeta de instancias: {INSTANCES_DIR}")

    instance_paths = sorted(INSTANCES_DIR.glob("*.dat-s"), key=natural_sort_key)

    if not instance_paths:
        raise FileNotFoundError(f"No se encontraron archivos *.dat-s en: {INSTANCES_DIR}")

    selected_instances = {p.stem for p in instance_paths}

    print("========================================")
    print(" CREANDO MATILDA METADATA")
    print("========================================")
    print(f"Instancias encontradas: {len(instance_paths)}")
    print(f"Carpeta: {INSTANCES_DIR}")
    print()

    # ========================================
    # 1. FEATURES
    # ========================================

    print("1) Extrayendo features...")

    feature_rows = extract_features_for_directory(INSTANCES_DIR)
    df_features = pd.DataFrame(feature_rows)

    if not df_features.empty and "instance" in df_features.columns:
        df_features = df_features[df_features["instance"].isin(selected_instances)].copy()

    if "error" in df_features.columns:
        feature_errors = df_features["error"].notna().sum()
    else:
        feature_errors = 0

    print(f"   Features extraídas: {len(df_features)}")
    print(f"   Errores en features: {feature_errors}")
    print()

    # ========================================
    # 2. SOLVERS EN PARALELO
    # ========================================

    print("2) Corriendo SeDuMi y SDPT3 en paralelo...")

    with ProcessPoolExecutor(max_workers=2) as executor:

        future_sedumi = executor.submit(run_sedumi, instance_paths)
        future_sdpt3 = executor.submit(run_sdpt3, instance_paths)

        sedumi_rows = future_sedumi.result()
        sdpt3_rows = future_sdpt3.result()

    df_sedumi = pd.DataFrame(sedumi_rows)
    df_sdpt3 = pd.DataFrame(sdpt3_rows)

    if not df_sedumi.empty:

        df_sedumi = df_sedumi.rename(
            columns={
                "success": "sedumi_success",
                "status": "sedumi_status",
                "read_time_sec": "sedumi_read_time_sec",
                "solve_time_sec": "algo_sedumi",
                "iter": "sedumi_iter",
                "numerr": "sedumi_numerr",
                "pinf": "sedumi_pinf",
                "dinf": "sedumi_dinf",
                "feasratio": "sedumi_feasratio",
                "r0": "sedumi_r0",
                "gap": "sedumi_gap",
            }
        )

    if not df_sdpt3.empty:

        df_sdpt3 = df_sdpt3.rename(
            columns={
                "success": "sdpt3_success",
                "status": "sdpt3_status",
                "read_time_sec": "sdpt3_read_time_sec",
                "solve_time_sec": "algo_sdpt3",
                "iter": "sdpt3_iter",
                "termcode": "sdpt3_termcode",
                "gap": "sdpt3_gap",
            }
        )

    print(f"   Resultados SeDuMi: {len(df_sedumi)}")
    print(f"   Resultados SDPT3: {len(df_sdpt3)}")
    print()

    # ========================================
    # 3. MERGE
    # ========================================

    print("3) Uniendo resultados...")

    df = df_features.merge(df_sedumi, on="instance", how="left")
    df = df.merge(df_sdpt3, on="instance", how="left")

    numeric_cols = [
        "feature_size",
        "feature_sparsity",
        "feature_scaling",
        "algo_sedumi",
        "algo_sdpt3",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ========================================
    # 4. FILTRO DE VALIDEZ
    # ========================================

    print("4) Filtrando corridas válidas...")

    has_error_column = "error" in df.columns

    if has_error_column:
        error_mask = df["error"].isna()
    else:
        error_mask = pd.Series(True, index=df.index)

    valid_mask = (
        error_mask
        & df["feature_size"].notna()
        & df["feature_sparsity"].notna()
        & df["feature_scaling"].notna()
        & df["algo_sedumi"].notna()
        & df["algo_sdpt3"].notna()
    )

    df["is_valid"] = valid_mask

    df["invalid_reasons"] = df.apply(
        lambda row: "" if row["is_valid"] else build_invalid_reasons(row, has_error_column),
        axis=1,
    )

    df_valid = df.loc[df["is_valid"]].copy()
    df_invalid = df.loc[~df["is_valid"]].copy()

    print(f"   Instancias totales: {len(df)}")
    print(f"   Instancias válidas: {len(df_valid)}")
    print(f"   Instancias no válidas: {len(df_invalid)}")
    print()

    if not df_invalid.empty:

        print("   Detalle de instancias no válidas:")

        for _, row in df_invalid.iterrows():
            print(f"      - {row['instance']}: {row['invalid_reasons']}")

        print()

    # ========================================
    # 5. CSV PARA MATILDA
    # ========================================

    print("5) Exportando CSV...")

    matilda_columns = [
        "instance",
        "feature_size",
        "feature_sparsity",
        "feature_scaling",
        "algo_sedumi",
        "algo_sdpt3",
    ]

    matilda_columns = [col for col in matilda_columns if col in df_valid.columns]

    df_matilda = df_valid[matilda_columns].copy()
    df_matilda = df_matilda.rename(columns={"instance": "instances"})

    df_matilda.to_csv(OUTPUT_MATILDA_CSV, index=False)

    diagnostic_columns = [
        "instance",
        "is_valid",
        "invalid_reasons",
        "family",
        "m",
        "n_blocks",
        "feature_size",
        "feature_sparsity",
        "feature_scaling",
        "feature_nnz",
        "feature_max_block_size",
        "feature_min_block_size",
        "feature_sum_block_size",
        "algo_sedumi",
        "algo_sdpt3",
        "sedumi_success",
        "sedumi_status",
        "sedumi_gap",
        "sedumi_iter",
        "sedumi_numerr",
        "sedumi_pinf",
        "sedumi_dinf",
        "sedumi_feasratio",
        "sedumi_r0",
        "sdpt3_success",
        "sdpt3_status",
        "sdpt3_gap",
        "sdpt3_iter",
        "sdpt3_termcode",
    ]

    if has_error_column:
        diagnostic_columns.append("error")

    diagnostic_columns = [col for col in diagnostic_columns if col in df.columns]

    df_diagnostic = df[diagnostic_columns].copy()
    df_diagnostic.to_csv(OUTPUT_DIAGNOSTIC_CSV, index=False)

    print("========================================")
    print(" METADATA CREADO CORRECTAMENTE")
    print("========================================")

    print(f"CSV MATILDA: {OUTPUT_MATILDA_CSV}")
    print(f"Filas MATILDA: {len(df_matilda)}")

    print(f"CSV DIAGNÓSTICO: {OUTPUT_DIAGNOSTIC_CSV}")
    print(f"Filas DIAGNÓSTICO: {len(df_diagnostic)}")


if __name__ == "__main__":
    main()