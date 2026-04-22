# SDISG — SDP Instance Space Generator

> A modular research framework for benchmarking Semidefinite Programming (SDP) solvers using the **Instance Space Analysis** methodology. Includes a desktop GUI, a full metadata pipeline, and evolutionary instance generation.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![MATLAB](https://img.shields.io/badge/MATLAB-R2022a%2B-orange?logo=mathworks&logoColor=white)
![PySide6](https://img.shields.io/badge/GUI-PySide6%20%28Qt6%29-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Research%20%2F%20Thesis-blueviolet)

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
4. [Repository Structure](#4-repository-structure)
5. [Architecture](#5-architecture)
6. [Configuration](#6-configuration)
7. [Metadata Pipeline](#7-metadata-pipeline)
8. [Feature Extraction](#8-feature-extraction)
9. [Solvers](#9-solvers)
10. [Instance Space Analysis](#10-instance-space-analysis)
11. [Genetic Algorithm](#11-genetic-algorithm)
12. [Desktop Application (SDISG)](#12-desktop-application-sdisg)
13. [CLI Reference](#13-cli-reference)
14. [Instance Formats](#14-instance-formats)
15. [Outputs](#15-outputs)

---

## 1. Overview

**SDISG** is the core experimental infrastructure for a thesis on algorithmic selection in Semidefinite Programming. It implements the full **Instance Space Analysis (ISA)** pipeline over a collection of SDP instances:

```
SDP Instances (.mat / .dat-s)
         │
         ▼
 ┌───────────────────────────────────────────────────┐
 │             Metadata Pipeline                     │
 │                                                   │
 │  1. Source table    → instance provenance         │
 │  2. Features table  → 96 structural features      │
 │  3. Solver runtimes → SDPT3 & SeDuMi benchmarks   │
 │  4. Metadata table  → unified MATILDA-ready CSV   │
 └───────────────────────────────────────────────────┘
         │
         ▼
   metadata.csv  ──────────────────────────────────────┐
         │                                             │
         ▼                                             ▼
 ┌───────────────────┐                  ┌──────────────────────────┐
 │  ISA / MATILDA    │                  │  Genetic Algorithm       │
 │  (MATLAB)         │                  │  (fill empty space)      │
 └───────────────────┘                  └──────────────────────────┘
         │
         ▼
  2D Instance Space — footprints, selection models, visualizations
```

The system can be operated through the **SDISG desktop application** or entirely via the **command line**.

---

## 2. System Requirements

### Python

| Package | Purpose |
|---------|---------|
| `python >= 3.10` | Runtime |
| `matlabengine` | MATLAB Engine API for Python |
| `pandas` | Data manipulation |
| `numpy` | Numerical computation |
| `scipy` | Sparse matrices, linear algebra |
| `matplotlib` | Plotting and visualization |
| `PySide6` | Desktop GUI (Qt6) |
| `python-dotenv` | Environment variables |
| `tqdm` | Progress bars |

### MATLAB

- **Version**: R2022a or newer
- **Toolboxes**: Statistics and Machine Learning · Optimization · Signal Processing · Communications
- **Compiler**: MinGW-w64 (Windows) or GCC (Linux/macOS)

### External Submodules

The solvers and ISA framework are included as Git submodules:

| Submodule | Description |
|-----------|-------------|
| `extern/InstanceSpace/` | MATILDA ISA framework (andremun/InstanceSpace) |
| `extern/sdpt3/` | SDPT3 interior-point SDP solver |
| `extern/sedumi/` | SeDuMi conic programming solver |

---

## 3. Installation

```bash
# 1. Clone with submodules
git clone --recurse-submodules https://github.com/<your-username>/TESIS-3.git
cd TESIS-3

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Initialize submodules (if cloned without --recurse-submodules)
git submodule update --init --recursive

# 4. Verify the environment
python tools/installation/check_environment.py
```

> **Note:** The MATLAB Engine API must be installed separately. Follow the [MathWorks instructions](https://www.mathworks.com/help/matlab/matlab_external/install-the-matlab-engine-for-python.html) for your MATLAB version.

---

## 4. Repository Structure

```
TESIS-3/
│
├── app/                            # Desktop application (SDISG)
│   ├── launcher/
│   │   └── main.py                 # ← GUI entry point
│   ├── backend/
│   │   └── services/
│   │       └── config_service.py   # JSON config loader (singleton)
│   └── frontend/
│       ├── assets/icons/           # Application icons
│       ├── components/             # Reusable UI widgets
│       └── pages/                  # 7 main application pages
│
├── config/                         # All system configuration (JSON)
│   ├── metadata_orchestrator_config.json
│   ├── instances_config.json
│   ├── features_config.json
│   ├── solver_registry.json
│   ├── solver_config.json
│   ├── instance_space_config.json
│   ├── genetic_config.json
│   └── app_ui_config.json
│
├── data/                           # SDP instance collections
│   ├── sdplib/                     # SDPLIB benchmark instances
│   ├── DIMACS/                     # Converted from DIMACS graphs
│   └── genetic/                    # Generated by genetic algorithm
│
├── extern/                         # Git submodules (read-only)
│   ├── InstanceSpace/              # MATILDA ISA framework
│   ├── sdpt3/                      # SDPT3 solver
│   └── sedumi/                     # SeDuMi solver
│
├── tools/                          # Core system logic
│   ├── features/                   # Feature extractors (4 modules)
│   ├── isa/                        # ISA pipeline and orchestration
│   │   └── build_metadata/         # Pipeline step scripts
│   ├── wrappers_v2/                # Solver wrapper interfaces
│   ├── runners/                    # MATLAB engine manager
│   ├── genetic_algorithms/         # Evolutionary instance generation
│   ├── DIMACS/                     # DIMACS-to-SDP conversion
│   ├── matlab/                     # MATLAB helper scripts
│   ├── logging/                    # Universal logger
│   └── installation/               # Environment checker
│
├── ISA metadata/                   # Pipeline outputs
│   ├── metadata.csv                # Final unified table
│   └── intermediates/              # Intermediate CSVs per step
│
├── matilda_out/                    # ISA analysis outputs
│   ├── build/                      # ISA model, coordinates, footprints
│   └── explore/                    # Exploration results, empty space targets
│
├── logs/                           # Execution logs
├── sandbox/                        # Temporary MATLAB output (safe to delete)
├── examples/                       # Reference runs
├── requirements.txt
└── SDISG.spec                      # PyInstaller specification
```

---

## 5. Architecture

The system has two operation modes that share the same processing core:

```
┌──────────────────────────────────────────────────────────────────────┐
│                         SDISG Desktop App                            │
│  Home → Parameters → Metadata → Build → Explore → Genetic           │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ calls
┌──────────────────────────────────▼───────────────────────────────────┐
│                          CLI / Python Scripts                        │
│  orchestrate_isa_metadata.py  ·  run_build_is.py  ·  fill_empty_space│
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ uses
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
  ┌─────────────┐         ┌──────────────────┐      ┌──────────────────┐
  │  Feature    │         │  Solver Wrappers │      │  ISA / MATILDA   │
  │  Extractors │         │  (MATLAB Engine) │      │  (extern/)       │
  └─────────────┘         └──────────────────┘      └──────────────────┘
```

The orchestrator ([`tools/isa/build_metadata/orchestrate_isa_metadata.py`](tools/isa/build_metadata/orchestrate_isa_metadata.py)) controls every pipeline step according to `config/metadata_orchestrator_config.json`. Each step can independently be set to `build`, `csv` (load from file), or `disabled`.

---

## 6. Configuration

All parameters are in JSON files under `config/`. Nothing is hardcoded.

### `metadata_orchestrator_config.json`

Controls each pipeline step mode:

```json
{
  "instances": { "mode": "enabled" },
  "pipeline": {
    "source_table":         { "mode": "build" },
    "features_table":       { "mode": "build" },
    "solver_runtime_table": { "mode": "csv"   },
    "metadata_table":       { "mode": "build" }
  },
  "output": {
    "save_metadata": true,
    "metadata_path": "ISA metadata/metadata.csv"
  }
}
```

| Mode | Behavior |
|------|----------|
| `"build"` | Recompute the step from scratch |
| `"csv"` | Load the result from an existing CSV |
| `"disabled"` | Skip the step entirely |

| Instance mode | Behavior |
|---------------|----------|
| `"enabled"` | Use the list in `instances_config.json` |
| `"all"` | Auto-discover every `.mat` file under `data/` |

### `solver_config.json`

```json
{
  "solvers": {
    "sdpt3":  { "tolerance_gap": 1e-5, "max_iterations": 10000, "time_limit": 360 },
    "sedumi": { "tolerance_gap": 1e-5, "max_iterations": 10000, "time_limit": 360 }
  }
}
```

### `features_config.json`

Enables or disables individual features by group:

```json
{
  "size":      { "m": true, "n": true, "num_blocks": true, ... },
  "structure": { "sdp_blocks": true, "block_entropy": true, ... },
  "sparsity":  { "density_C": true, "nnz_ratio_A": true, ... },
  "scaling":   { "norm_C": true, "condition_number": true, ... }
}
```

---

## 7. Metadata Pipeline

The pipeline has four independent steps:

```
Step 1           Step 2              Step 3                Step 4
─────────        ──────────────      ──────────────────    ─────────────────
Source table  →  Features table  →  Solver runtime table → Metadata table
(provenance)     (96 features)       (SDPT3, SeDuMi)        (final merge)
     ↓                ↓                    ↓                      ↓
source_table     features_table      solver_runtime_table    metadata.csv
    .csv              .csv                 .csv
```

All intermediate CSVs are saved to `ISA metadata/intermediates/`.

### Step 1 — Source Table

Records the origin of each instance: `SDPLIB`, `DIMACS`, or `genetic`.

### Step 2 — Features Table

Runs four feature extractors on each instance `.mat` file. See [Feature Extraction](#8-feature-extraction).

### Step 3 — Solver Runtime Table

Executes each enabled solver on each instance via MATLAB Engine API. Columns produced: `algo_sdpt3`, `algo_sedumi` (runtime in seconds; `NaN` on failure).

A single MATLAB session is started and reused for all instances, minimizing overhead.

### Step 4 — Metadata Table

Inner-joins the three tables on the `Instance` column. Standardizes column naming for MATILDA compatibility.

---

## 8. Feature Extraction

The system extracts up to **96 features** grouped in four modules under `tools/features/`:

| Group | Module | Count | Description |
|-------|--------|-------|-------------|
| **Size** | `size_features.py` | ~15 | Problem dimensions: m (constraints), n (variable size), block counts, block size stats |
| **Structure** | `structure_features.py` | ~25 | SDP vs LP block counts, block dominance, size entropy, type distribution |
| **Sparsity** | `sparsity_features.py` | ~26 | NNZ counts in C and Aᵢ, density ratios, empty constraint detection |
| **Scaling** | `scaling_features.py` | ~30 | Frobenius/L1/L2 norms, dynamic ranges, cross-matrix ratios |

Features can be individually enabled or disabled via `config/features_config.json`.

Both `.mat` (MATLAB binary) and `.dat-s` (SDPA text) formats are supported via the auto-detecting `instance_reader.py`.

---

## 9. Solvers

### Integrated Solvers

| Solver | Type | Wrapper |
|--------|------|---------|
| **SDPT3** | Interior-point (SDP/SOCP/LP) | `tools/wrappers_v2/sdpt3_wrapper.py` |
| **SeDuMi** | Self-Dual Minimization (conic) | `tools/wrappers_v2/sedumi_wrapper.py` |

Both solvers are executed through **MATLAB Engine API for Python**. A shared MATLAB session managed by `tools/runners/matlab_runner.py` is started once per pipeline run.

### Adding a New Solver

1. Create `tools/wrappers_v2/<solver>_wrapper.py` implementing the base solver interface.
2. Add the MATLAB execution script to `tools/matlab/<solver>/`.
3. Register the solver in `config/solver_registry.json`:
   ```json
   {
     "name": "mysolver",
     "enabled": true,
     "wrapper": "tools/wrappers_v2/mysolver_wrapper.py",
     "class": "MySolverWrapper"
   }
   ```
4. Add parameters in `config/solver_config.json` under `"solvers"`.

---

## 10. Instance Space Analysis

### Build the Instance Space

```bash
python tools/isa/run_build_is.py
```

Reads `metadata.csv` and `config/instance_space_config.json`, calls MATILDA from `extern/InstanceSpace` via MATLAB, and writes results to `matilda_out/build/`:

- `coordinates.csv` — (z₁, z₂) projection per instance
- `outline.csv` — convex hull boundary
- Per-algorithm footprint plots and selection models

### Explore the Instance Space

```bash
python tools/isa/run_explore_is.py
```

Projects the metadata using the built ISA model. Outputs to `matilda_out/explore/`:

- `coordinates.csv` — 2D positions
- `outline.csv` — hull boundary
- `empty_space_targets.csv` — centroids of sparsely populated regions

### Identify Empty Regions

```bash
python tools/isa/analyze_explore_empty_space.py
```

Builds a regular grid over the convex hull and identifies points far from all existing instances. Outputs target coordinates for the genetic algorithm.

---

## 11. Genetic Algorithm

The genetic algorithm generates new SDP instances that populate empty regions of the instance space.

### Workflow

```
Identify empty regions  →  Define target (z₁, z₂)  →  Evolve candidate SDP instance
         ↓
Evaluate fitness (Euclidean distance in projected space)
         ↓
Validate SDP structure  →  Save .mat  →  Re-run pipeline
```

### Commands

```bash
# Fill a single empty region (reads target from empty_space_targets.csv)
python tools/genetic_algorithms/fill_empty_space.py

# Fill multiple empty regions in batch
python tools/genetic_algorithms/fill_empty_space_multiple.py

# Generate an instance at a specific (z1, z2) coordinate
python tools/genetic_algorithms/fill_point_target.py
```

### Configuration (`config/genetic_config.json`)

| Parameter | Description |
|-----------|-------------|
| `generation_tolerance` | Max distance from target accepted as success |

Generated instances are saved to `data/genetic/` and `matilda_out/genetic/fill_empty_space/`.

---

## 12. Desktop Application (SDISG)

### Launch

```bash
python app/launcher/main.py
```

### Pages

| Page | Function |
|------|----------|
| **Home** | Navigation hub |
| **Configuration** | Live JSON editor for all config files |
| **Parameters** | Form-based solver and feature configuration |
| **Metadata** | Execute the metadata pipeline with real-time output |
| **Build** | Run MATILDA/ISA and generate footprints |
| **Explore** | Interactive 2D scatter plot of the instance space; click to set generation targets |
| **Genetic** | Configure and run the genetic algorithm |

### Build Standalone Executable

```bash
pyinstaller SDISG.spec
```

The executable is generated at `dist/SDISG/SDISG.exe`. It bundles all config files, assets, and Python tools — no Python installation required on the target machine.

---

## 13. CLI Reference

| Script | Purpose |
|--------|---------|
| `tools/isa/build_metadata/orchestrate_isa_metadata.py` | Run the full metadata pipeline |
| `tools/isa/build_metadata/build_features_table.py` | Extract features only |
| `tools/isa/build_metadata/build_solver_runtime_table.py` | Benchmark solvers only |
| `tools/isa/build_metadata/build_source_table.py` | Record instance provenance |
| `tools/isa/build_metadata/build_isa_metadata_table.py` | Merge tables only |
| `tools/isa/run_build_is.py` | Run ISA/MATILDA analysis |
| `tools/isa/run_explore_is.py` | Explore the instance space |
| `tools/isa/analyze_explore_empty_space.py` | Identify empty regions |
| `tools/genetic_algorithms/fill_empty_space.py` | Generate instance for one region |
| `tools/genetic_algorithms/fill_empty_space_multiple.py` | Batch generation |
| `tools/genetic_algorithms/fill_point_target.py` | Generate instance at exact coordinate |
| `tools/DIMACS/build_sdp_instances.py` | Convert DIMACS graphs to SDP `.mat` |
| `tools/DIMACS/audit_dimacs_instances.py` | Validate a DIMACS instance collection |
| `tools/installation/check_environment.py` | Verify MATLAB, Python, paths |

---

## 14. Instance Formats

### MATLAB binary (`.mat`) — primary format

```matlab
blk   % cell array: {type, dimension} for each block
At    % constraint matrices (sparse, one cell per block)
C     % cost matrix
b     % RHS vector (m × 1)
```

This is the standard SDPT3/SeDuMi format. SDPLIB instances come pre-packaged in this format.

### SDPA text (`.dat-s`)

```
m              % number of constraints
n_blocks       % number of blocks
{s1 s2 ...}    % block sizes (positive = SDP, negative = LP/diagonal)
b1 b2 ... bm   % RHS vector
<data rows>    % matno, blkno, i, j, value
```

Both formats are auto-detected by `tools/features/instance_reader.py`.

### DIMACS conversion

DIMACS graph instances (`.clq`, `.col`, etc.) are converted to SDP `.mat` via:

```bash
python tools/DIMACS/build_sdp_instances.py
```

Supported families: **BISECT** (graph bisection), **FAP** (frequency assignment), **TORUS** (grid graphs).

---

## 15. Outputs

| Path | Content |
|------|---------|
| `ISA metadata/metadata.csv` | Final table: instance + 96 features + solver runtimes |
| `ISA metadata/intermediates/source_table.csv` | Instance provenance (SDPLIB / DIMACS / genetic) |
| `ISA metadata/intermediates/features_table.csv` | Features only |
| `ISA metadata/intermediates/solver_runtime_table.csv` | Solver runtimes only |
| `matilda_out/build/` | ISA model, (z₁, z₂) coordinates, footprint plots, selection models |
| `matilda_out/explore/` | Exploration coordinates, hull outline, empty space targets |
| `matilda_out/genetic/` | Generated instances + before/after ISA visualizations |
| `data/genetic/` | Final generated `.mat` instances |
| `logs/benchmark_audit.log` | Full execution log with run IDs |
| `sandbox/` | Temporary MATLAB logs — safe to delete |

### `metadata.csv` column structure

```
Instances, Source, feature_m, feature_n, feature_num_blocks, ...(96 features)..., algo_sdpt3, algo_sedumi
arch0.dat-s, SDPLIB, 174, 11, 2, ..., 1.2773, 0.9838
```

---

## License

See [LICENSE](LICENSE).
