from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


RUN_DIR = Path(r"matilda_out\build\run_build_20260421_123714")


def main() -> None:
    coordinates_path = RUN_DIR / "coordinates.csv"
    bounds_path = RUN_DIR / "bounds.csv"
    bounds_prunned_path = RUN_DIR / "bounds_prunned.csv"
    metadata_path = RUN_DIR / "metadata.csv"
    output_path = RUN_DIR / "instance_space_with_bounds.png"

    if not coordinates_path.exists():
        raise FileNotFoundError(f"Missing file: {coordinates_path}")
    if not bounds_path.exists():
        raise FileNotFoundError(f"Missing file: {bounds_path}")
    if not bounds_prunned_path.exists():
        raise FileNotFoundError(f"Missing file: {bounds_prunned_path}")
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing file: {metadata_path}")

    coordinates_df = pd.read_csv(coordinates_path)
    bounds_df = pd.read_csv(bounds_path)
    bounds_prunned_df = pd.read_csv(bounds_prunned_path)
    metadata_df = pd.read_csv(metadata_path)

    # Standardize names for merge
    coordinates_df = coordinates_df.rename(columns={"Row": "instances"})
    metadata_df.columns = [col.lower() for col in metadata_df.columns]

    if "instances" not in metadata_df.columns:
        raise ValueError("metadata.csv must contain an 'instances' column.")
    if "source" not in metadata_df.columns:
        raise ValueError("metadata.csv must contain a 'source' column.")

    plot_df = coordinates_df.merge(
        metadata_df[["instances", "source"]],
        on="instances",
        how="left",
    )

    fig, ax = plt.subplots(figsize=(12, 8))

    # Scatter by source
    for source_name, group in plot_df.groupby("source", dropna=False):
        label = str(source_name) if pd.notna(source_name) else "unknown"
        ax.scatter(
            group["z_1"],
            group["z_2"],
            s=28,
            label=label,
        )

    # Full bounds
    ax.plot(
        bounds_df["z_1"],
        bounds_df["z_2"],
        linewidth=2.0,
        linestyle="-",
        label="bounds",
    )

    # Pruned bounds
    ax.plot(
        bounds_prunned_df["z_1"],
        bounds_prunned_df["z_2"],
        linewidth=2.5,
        linestyle="--",
        label="bounds_prunned",
    )

    ax.set_title("Instance Space")
    ax.set_xlabel("z_1")
    ax.set_ylabel("z_2")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()

    fig.savefig(output_path, dpi=300)
    print("=" * 80)
    print("INSTANCE SPACE PLOT GENERATED")
    print("=" * 80)
    print(f"[OK] Output image: {output_path.resolve()}")

    plt.show()


if __name__ == "__main__":
    main()