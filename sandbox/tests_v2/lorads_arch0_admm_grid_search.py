#!/usr/bin/env python3
"""
Grid search de LoRADS sobre arch0.dat-s usando solamente modo ALM+ADMM.

Objetivo:
- Probar muchas combinaciones de parámetros de LoRADS sobre arch0.
- Mantener ADMM activado en todas las corridas (maxADMMIter > 0).
- Guardar logs crudos, resultados parseados, CSV/JSON consolidados y un reporte final.
- Identificar la mejor configuración según estabilidad + calidad numérica.

Uso:
    python sandbox/tests_v2/lorads_arch0_admm_grid_search.py

Opcionalmente puedes pasar la ruta WSL del ejecutable de LoRADS:
    python sandbox/tests_v2/lorads_arch0_admm_grid_search.py \
        /home/lucas_zamora/lorads_build/lorads_src/build/LoRADS_v_2_0_1-alpha
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ============================================================
# Configuración base
# ============================================================
EXPECTED_OPT_OBJ = 5.66517e-01
INSTANCE_REL_PATH = Path("data/instances/sdplib/arch0.dat-s")
DEFAULT_WSL_EXE = "/home/lucas_zamora/lorads_build/lorads_src/build/LoRADS_v_2_0_1-alpha"
DEFAULT_TIME_LIMIT = 180.0
DEFAULT_HARD_TIMEOUT = 210.0


# ============================================================
# Utilidades de paths
# ============================================================
def project_root_from_script(script_path: Path) -> Path:
    """Asume que el script vive dentro del repo; si no, usa cwd."""
    cwd = Path.cwd().resolve()
    script_parts = script_path.resolve().parts
    cwd_parts = cwd.parts
    # Si el script está dentro del cwd, usar cwd.
    if len(script_parts) >= len(cwd_parts) and script_parts[: len(cwd_parts)] == cwd_parts:
        return cwd
    return cwd


def windows_to_wsl_path(path: Path) -> str:
    abs_path = str(path.resolve())
    if abs_path.startswith("/mnt/"):
        return abs_path
    drive, rest = os.path.splitdrive(abs_path)
    if not drive:
        return abs_path.replace("\\", "/")
    drive_letter = drive[0].lower()
    rest = rest.replace("\\", "/")
    return f"/mnt/{drive_letter}{rest}"


# ============================================================
# Dataclasses
# ============================================================
@dataclass
class RunConfig:
    times_log_rank: float
    phase1_tol: float
    phase2_tol: float
    init_rho: float
    rho_max: float
    rho_freq: int
    rho_factor: float
    alm_rho_factor: float
    heuristic_factor: float
    lbfgs_list_length: int
    end_tau_tol: float
    end_alm_sub_tol: float
    l2_rescaling: int
    reopt_level: int
    dyrank_level: int
    high_acc_mode: int
    max_alm_iter: int
    max_admm_iter: int
    time_limit_seconds: float


@dataclass
class RunResult:
    run_id: str
    status: str
    returncode: Optional[int]
    timed_out: bool
    runtime: float
    iterations: int
    obj_val: float
    dual_obj: float
    gap: float
    pinfeas: float
    dinfeas: float
    phi: float
    pinf: float
    dinf: float
    numerical_error: int
    abs_obj_error: float
    abs_obj_error_signed: float
    used_summary_metrics: int
    log_file: str
    raw_stdout_file: str
    raw_stderr_file: str
    command: str
    config: Dict[str, Any]


# ============================================================
# Parseo
# ============================================================
def safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        return float(x)
    except Exception:
        return default


FLOAT_RE = r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"


def extract_float(pattern: str, text: str, default: float = float("nan")) -> float:
    m = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not m:
        return default
    return safe_float(m.group(1), default)


def extract_last_int(pattern: str, text: str, default: int = 0) -> int:
    matches = re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not matches:
        return default
    try:
        return int(matches[-1])
    except Exception:
        return default


@dataclass
class Candidate:
    source: str
    phase: str
    iteration: int
    obj_val: float
    dual_obj: float
    gap: float
    pinfeas: float
    dinfeas: float
    pinf: float
    dinf: float
    phi: float



def is_finite(x: float) -> bool:
    return not math.isnan(x) and not math.isinf(x)



def candidate_score(gap: float, pinfeas: float, dinfeas: float) -> float:
    vals = [v for v in (gap, pinfeas, dinfeas) if is_finite(v)]
    if not vals:
        return float("inf")
    return max(vals)



def choose_better(a: Optional[Candidate], b: Optional[Candidate]) -> Optional[Candidate]:
    if a is None:
        return b
    if b is None:
        return a
    if b.phi < a.phi:
        return b
    if b.phi > a.phi:
        return a
    if b.gap < a.gap:
        return b
    if b.gap > a.gap:
        return a
    a_diff = abs(a.obj_val - a.dual_obj) if is_finite(a.obj_val) and is_finite(a.dual_obj) else float("inf")
    b_diff = abs(b.obj_val - b.dual_obj) if is_finite(b.obj_val) and is_finite(b.dual_obj) else float("inf")
    if b_diff < a_diff:
        return b
    return a



def parse_iter_candidates(text: str) -> Optional[Candidate]:
    best: Optional[Candidate] = None
    line_pattern = re.compile(
        rf"(?P<kind>ALM\s+OuterIter|ADMM\s+Iter)\s*:\s*(?P<iter>\d+)"
        rf".*?pObj\s*:\s*(?P<pobj>{FLOAT_RE})"
        rf".*?dObj\s*:\s*(?P<dobj>{FLOAT_RE})"
        rf".*?pInfea\(1\)\s*:\s*(?P<pinf1>{FLOAT_RE})"
        rf".*?pInfea\(Inf\)\s*:\s*(?P<pinfinf>{FLOAT_RE})"
        rf"(?:.*?dInfea\(1\)\s*:\s*(?P<dinf1>{FLOAT_RE}))?"
        rf"(?:.*?dInfea\(Inf\)\s*:\s*(?P<dinfinf>{FLOAT_RE}))?"
        rf".*?pdGap\s*:\s*(?P<gap>{FLOAT_RE})",
        flags=re.IGNORECASE,
    )

    for m in line_pattern.finditer(text):
        phase = "ALM" if "outeriter" in m.group("kind").lower() else "ADMM"
        pinfeas = safe_float(m.group("pinf1"))
        dinfeas = safe_float(m.group("dinf1"))
        gap = safe_float(m.group("gap"))
        cand = Candidate(
            source="iter",
            phase=phase,
            iteration=int(m.group("iter")),
            obj_val=safe_float(m.group("pobj")),
            dual_obj=safe_float(m.group("dobj")),
            gap=gap,
            pinfeas=pinfeas,
            dinfeas=dinfeas,
            pinf=safe_float(m.group("pinfinf")),
            dinf=safe_float(m.group("dinfinf")),
            phi=candidate_score(gap, pinfeas, dinfeas),
        )
        if not is_finite(cand.obj_val) or abs(cand.obj_val) > 1e100:
            continue
        best = choose_better(best, cand)
    return best



def parse_final_summary_candidate(text: str) -> Optional[Candidate]:
    obj_val = extract_float(rf"Primal Objective:\s*:\s*{FLOAT_RE}", text)
    dual_obj = extract_float(rf"Dual Objective:\s*:\s*{FLOAT_RE}", text)
    pinfeas = extract_float(rf"Constraint Violation\(1\)\s*:\s*{FLOAT_RE}", text)
    dinfeas = extract_float(rf"Dual Infeasibility\(1\)\s*:\s*{FLOAT_RE}", text)
    gap = extract_float(rf"Primal Dual Gap\s*:\s*{FLOAT_RE}", text)
    pinf = extract_float(rf"Constraint Violation\(Inf\)\s*:\s*{FLOAT_RE}", text)
    dinf = extract_float(rf"Dual Infeasibility\(Inf\)\s*:\s*{FLOAT_RE}", text)
    if not is_finite(obj_val) or abs(obj_val) > 1e100:
        return None
    return Candidate(
        source="summary",
        phase="FINAL",
        iteration=0,
        obj_val=obj_val,
        dual_obj=dual_obj,
        gap=gap,
        pinfeas=pinfeas,
        dinfeas=dinfeas,
        pinf=pinf,
        dinf=dinf,
        phi=candidate_score(gap, pinfeas, dinfeas),
    )



def classify_status(text: str, returncode: Optional[int], timed_out: bool, phi: float, tol: float, numerical_error: int) -> str:
    low = text.lower()
    if timed_out or "time limit" in low:
        return "TIME_LIMIT"
    if is_finite(phi) and phi <= tol:
        return "OPTIMAL"
    if numerical_error:
        return "NUMERICAL_ERROR"
    if "maximum number of iterations" in low or "end program" in low:
        return "STOPPED"
    if returncode == 0:
        return "STOPPED"
    return "FAILED"


# ============================================================
# Construcción de comandos
# ============================================================
def build_command(exe_wsl: str, instance_wsl: str, cfg: RunConfig) -> List[str]:
    return [
        "wsl",
        exe_wsl,
        instance_wsl,
        "--timesLogRank", str(cfg.times_log_rank),
        "--phase1Tol", str(cfg.phase1_tol),
        "--phase2Tol", str(cfg.phase2_tol),
        "--initRho", str(cfg.init_rho),
        "--rhoMax", str(cfg.rho_max),
        "--rhoFreq", str(cfg.rho_freq),
        "--rhoFactor", str(cfg.rho_factor),
        "--ALMRhoFactor", str(cfg.alm_rho_factor),
        "--heuristicFactor", str(cfg.heuristic_factor),
        "--maxALMIter", str(cfg.max_alm_iter),
        "--maxADMMIter", str(cfg.max_admm_iter),
        "--timeSecLimit", str(cfg.time_limit_seconds),
        "--lbfgsListLength", str(cfg.lbfgs_list_length),
        "--endTauTol", str(cfg.end_tau_tol),
        "--endALMSubTol", str(cfg.end_alm_sub_tol),
        "--l2Rescaling", str(cfg.l2_rescaling),
        "--reoptLevel", str(cfg.reopt_level),
        "--dyrankLevel", str(cfg.dyrank_level),
        "--highAccMode", str(cfg.high_acc_mode),
    ]


# ============================================================
# Ejecución
# ============================================================
def run_command(command: List[str], cwd: Path, timeout: float) -> Tuple[str, str, Optional[int], bool, float]:
    start = time.perf_counter()
    proc = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            proc.kill()
        except Exception:
            pass
        stdout, stderr = proc.communicate()
    elapsed = time.perf_counter() - start
    return stdout or "", stderr or "", proc.returncode, timed_out, elapsed


# ============================================================
# Grilla de búsqueda: SOLO ALM+ADMM
# ============================================================
def build_grid() -> List[RunConfig]:
    grid: Dict[str, Iterable[Any]] = {
        "times_log_rank": [1.2, 1.5, 2.0],
        "phase1_tol": [1e-3],
        "phase2_tol": [1e-5, 5e-6],
        "init_rho": [0.0],
        "rho_max": [1000.0],
        "rho_freq": [5, 10],
        "rho_factor": [1.05, 1.1],
        "alm_rho_factor": [1.2, 1.5],
        "heuristic_factor": [1.0],
        "lbfgs_list_length": [2],
        "end_tau_tol": [0.0],
        "end_alm_sub_tol": [0.0],
        "l2_rescaling": [0, 1],
        "reopt_level": [0],
        "dyrank_level": [1, 2],
        "high_acc_mode": [0, 1],
        "max_alm_iter": [10000],
        "max_admm_iter": [5, 20, 100],
        "time_limit_seconds": [DEFAULT_TIME_LIMIT],
    }

    keys = list(grid.keys())
    values = [list(grid[k]) for k in keys]
    configs: List[RunConfig] = []
    for combo in itertools.product(*values):
        data = dict(zip(keys, combo))
        # ADMM obligatorio
        if int(data["max_admm_iter"]) <= 0:
            continue
        configs.append(RunConfig(**data))
    return configs


# ============================================================
# Ranking
# ============================================================
def rank_key(row: RunResult) -> Tuple[Any, ...]:
    status_order = {
        "OPTIMAL": 0,
        "STOPPED": 1,
        "NUMERICAL_ERROR": 2,
        "TIME_LIMIT": 3,
        "FAILED": 4,
    }
    return (
        status_order.get(row.status, 99),
        1 if not is_finite(row.phi) else 0,
        row.phi if is_finite(row.phi) else float("inf"),
        row.numerical_error,
        row.abs_obj_error,
        row.runtime,
    )


# ============================================================
# Main
# ============================================================
def main() -> int:
    script_path = Path(__file__).resolve()
    project_root = project_root_from_script(script_path)
    instance_path = (project_root / INSTANCE_REL_PATH).resolve()
    if not instance_path.exists():
        print(f"No se encontró la instancia: {instance_path}")
        return 1

    exe_wsl = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_WSL_EXE
    instance_wsl = windows_to_wsl_path(instance_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = project_root / "sandbox" / "lorads_grid_search_arch0_admm" / f"run_{timestamp}"
    raw_logs_dir = out_dir / "raw_logs"
    configs_dir = out_dir / "configs"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_logs_dir.mkdir(parents=True, exist_ok=True)
    configs_dir.mkdir(parents=True, exist_ok=True)

    configs = build_grid()
    summary_log = out_dir / "summary.log"

    with open(summary_log, "w", encoding="utf-8") as slog:
        slog.write("LORADS ARCH0 GRID SEARCH - SOLO ALM+ADMM\n")
        slog.write(f"project_root: {project_root}\n")
        slog.write(f"instance: {instance_path}\n")
        slog.write(f"instance_wsl: {instance_wsl}\n")
        slog.write(f"executable_wsl: {exe_wsl}\n")
        slog.write(f"configs: {len(configs)}\n\n")

    print("=" * 60)
    print("LORADS ARCH0 GRID SEARCH - SOLO ALM+ADMM")
    print("=" * 60)
    print(f"Instancia: {instance_path}")
    print(f"Ejecutable WSL: {exe_wsl}")
    print(f"Configuraciones a probar: {len(configs)}")
    print(f"Output: {out_dir}")
    print()

    results: List[RunResult] = []

    for idx, cfg in enumerate(configs, start=1):
        run_id = f"run_{idx:04d}"
        cfg_json_path = configs_dir / f"{run_id}.json"
        with open(cfg_json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2)

        command = build_command(exe_wsl, instance_wsl, cfg)
        command_pretty = subprocess.list2cmdline(command)

        print(f"[{idx}/{len(configs)}] {run_id} | maxADMMIter={cfg.max_admm_iter} | phase2Tol={cfg.phase2_tol} | timesLogRank={cfg.times_log_rank} | rhoFactor={cfg.rho_factor} | highAccMode={cfg.high_acc_mode}")

        stdout, stderr, returncode, timed_out, elapsed = run_command(
            command, project_root, DEFAULT_HARD_TIMEOUT
        )

        stdout_path = raw_logs_dir / f"{run_id}_stdout.log"
        stderr_path = raw_logs_dir / f"{run_id}_stderr.log"
        with open(stdout_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(stdout)
        with open(stderr_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(stderr)

        merged = stdout + ("\n" + stderr if stderr else "")
        iter_best = parse_iter_candidates(merged)
        summary_best = parse_final_summary_candidate(merged)
        chosen = choose_better(iter_best, summary_best)

        if chosen is None:
            obj_val = dual_obj = gap = pinfeas = dinfeas = phi = pinf = dinf = float("nan")
            used_summary_metrics = 0
        else:
            obj_val = chosen.obj_val
            dual_obj = chosen.dual_obj
            gap = chosen.gap
            pinfeas = chosen.pinfeas
            dinfeas = chosen.dinfeas
            phi = chosen.phi
            pinf = chosen.pinf
            dinf = chosen.dinf
            used_summary_metrics = 1 if chosen.source == "summary" else 0

        numerical_error = 1 if "numerical error" in merged.lower() else 0
        runtime = extract_float(rf"all_time:\s*{FLOAT_RE}", merged, elapsed)
        iterations = max(
            extract_last_int(r"ALM OuterIter:(\d+)", merged, 0),
            extract_last_int(r"ADMM Iter:(\d+)", merged, 0),
        )
        status = classify_status(merged, returncode, timed_out, phi, cfg.phase2_tol, numerical_error)

        abs_obj_error = abs(abs(obj_val) - EXPECTED_OPT_OBJ) if is_finite(obj_val) else float("inf")
        abs_obj_error_signed = abs(obj_val - EXPECTED_OPT_OBJ) if is_finite(obj_val) else float("inf")

        result = RunResult(
            run_id=run_id,
            status=status,
            returncode=returncode,
            timed_out=timed_out,
            runtime=runtime,
            iterations=iterations,
            obj_val=obj_val,
            dual_obj=dual_obj,
            gap=gap,
            pinfeas=pinfeas,
            dinfeas=dinfeas,
            phi=phi,
            pinf=pinf,
            dinf=dinf,
            numerical_error=numerical_error,
            abs_obj_error=abs_obj_error,
            abs_obj_error_signed=abs_obj_error_signed,
            used_summary_metrics=used_summary_metrics,
            log_file=str(stdout_path),
            raw_stdout_file=str(stdout_path),
            raw_stderr_file=str(stderr_path),
            command=command_pretty,
            config=asdict(cfg),
        )
        results.append(result)

        with open(summary_log, "a", encoding="utf-8") as slog:
            slog.write(f"[{idx}/{len(configs)}] {run_id}\n")
            slog.write(f"status={status} returncode={returncode} timed_out={timed_out} numerical_error={numerical_error}\n")
            slog.write(f"obj={obj_val:.12e} gap={gap:.12e} pinf1={pinfeas:.12e} dinf1={dinfeas:.12e} phi={phi:.12e}\n")
            slog.write(f"abs_obj_error={abs_obj_error:.12e} runtime={runtime:.6f}\n")
            slog.write(f"command={command_pretty}\n\n")

    results_sorted = sorted(results, key=rank_key)

    csv_path = out_dir / "results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "status", "returncode", "timed_out", "runtime", "iterations",
            "obj_val", "dual_obj", "gap", "pinfeas", "dinfeas", "phi", "pinf", "dinf",
            "numerical_error", "abs_obj_error", "abs_obj_error_signed", "used_summary_metrics",
            "log_file", "raw_stdout_file", "raw_stderr_file", "command", "config_json"
        ])
        for row in results_sorted:
            writer.writerow([
                row.run_id, row.status, row.returncode, row.timed_out, row.runtime, row.iterations,
                row.obj_val, row.dual_obj, row.gap, row.pinfeas, row.dinfeas, row.phi, row.pinf, row.dinf,
                row.numerical_error, row.abs_obj_error, row.abs_obj_error_signed, row.used_summary_metrics,
                row.log_file, row.raw_stdout_file, row.raw_stderr_file, row.command,
                json.dumps(row.config, ensure_ascii=False)
            ])

    json_path = out_dir / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results_sorted], f, indent=2)

    best = results_sorted[0] if results_sorted else None
    report_path = out_dir / "report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("LORADS GRID SEARCH ARCH0 - SOLO ALM+ADMM\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"expected_opt_obj = {EXPECTED_OPT_OBJ:.12e}\n")
        f.write(f"n_configs = {len(configs)}\n\n")

        status_counts: Dict[str, int] = {}
        for r in results_sorted:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        f.write("Status counts:\n")
        for k in sorted(status_counts):
            f.write(f"  - {k}: {status_counts[k]}\n")
        f.write("\n")

        if best is not None:
            f.write("BEST CONFIG\n")
            f.write("-" * 60 + "\n")
            f.write(f"run_id: {best.run_id}\n")
            f.write(f"status: {best.status}\n")
            f.write(f"runtime: {best.runtime:.6f}\n")
            f.write(f"iterations: {best.iterations}\n")
            f.write(f"obj_val: {best.obj_val:.12e}\n")
            f.write(f"dual_obj: {best.dual_obj:.12e}\n")
            f.write(f"gap: {best.gap:.12e}\n")
            f.write(f"pinfeas: {best.pinfeas:.12e}\n")
            f.write(f"dinfeas: {best.dinfeas:.12e}\n")
            f.write(f"phi: {best.phi:.12e}\n")
            f.write(f"abs_obj_error(|obj|): {best.abs_obj_error:.12e}\n")
            f.write(f"numerical_error: {best.numerical_error}\n")
            f.write(f"log_file: {best.log_file}\n")
            f.write(f"command: {best.command}\n")
            f.write("config:\n")
            f.write(json.dumps(best.config, indent=2))
            f.write("\n\n")

        f.write("TOP 20\n")
        f.write("-" * 60 + "\n")
        for r in results_sorted[:20]:
            f.write(
                f"{r.run_id} | {r.status:16s} | phi={r.phi:.6e} | "
                f"obj={r.obj_val:.6e} | abs(|obj|-opt)={r.abs_obj_error:.6e} | "
                f"numerr={r.numerical_error} | time={r.runtime:.3f}\n"
            )

    manifest = {
        "project_root": str(project_root),
        "instance_path": str(instance_path),
        "instance_wsl": instance_wsl,
        "executable_wsl": exe_wsl,
        "expected_opt_obj": EXPECTED_OPT_OBJ,
        "n_configs": len(configs),
        "csv": str(csv_path),
        "json": str(json_path),
        "report": str(report_path),
        "summary_log": str(summary_log),
        "best_run_id": best.run_id if best else None,
    }
    with open(out_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print()
    print("=" * 60)
    print("FINISHED")
    print("=" * 60)
    print(f"CSV:    {csv_path}")
    print(f"JSON:   {json_path}")
    print(f"REPORT: {report_path}")
    if best is not None:
        print()
        print("BEST CONFIG")
        print(f"run_id      : {best.run_id}")
        print(f"status      : {best.status}")
        print(f"phi         : {best.phi:.12e}")
        print(f"obj_val     : {best.obj_val:.12e}")
        print(f"abs(|obj|-opt): {best.abs_obj_error:.12e}")
        print(f"numerr      : {best.numerical_error}")
        print(f"log         : {best.log_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
