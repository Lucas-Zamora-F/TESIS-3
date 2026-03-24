import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path


class LoRaDSWrapper:
    """
    Wrapper real para LoRADS sin modificar extern/lorads.

    Estrategia:
    - Lee config centralizada.
    - Busca los fuentes C reales en extern/lorads/src/src_semi.
    - Genera una carpeta temporal de build en sandbox/lorads_shadow_build.
    - Escribe un CMakeLists.txt temporal allí.
    - Compila un ejecutable shadow.
    - Ejecuta el binario sobre la instancia .dat-s.
    - Parsea stdout y devuelve resultados homogéneos.
    """

    def __init__(self, config_path="metadata/solver_config.json"):
        self.config_path = os.path.abspath(config_path)
        self.config = self._load_config(self.config_path)

        global_params = self.config.get("global_settings", {})
        self.max_iter = int(global_params.get("max_iterations", 2000))
        self.tol = float(global_params.get("tolerance_gap", 1e-6))
        self.time_limit = float(global_params.get("time_limit_seconds", 3600))
        self.verbose = int(global_params.get("verbose", 0))

        lorads_params = self.config.get("solvers", {}).get("lorads", {})
        self.times_log_rank = float(lorads_params.get("times_log_rank", 2.0))
        self.phase1_tol = float(lorads_params.get("phase1_tol", 1e-3))
        self.init_rho = lorads_params.get("init_rho", 1.0)
        self.rho_max = float(lorads_params.get("rho_max", 5000.0))
        self.rho_freq = int(lorads_params.get("rho_freq", 5))
        self.rho_factor = float(lorads_params.get("rho_factor", 1.2))
        self.heuristic_factor = float(lorads_params.get("heuristic_factor", 1.0))
        self.hard_kill_timeout = float(
            lorads_params.get("hard_kill_timeout_seconds", self.time_limit + 30)
        )

        self.project_root = self._infer_project_root()
        self.extern_root = os.path.join(self.project_root, "extern", "lorads")
        self.src_root = os.path.join(self.extern_root, "src", "src_semi")
        self.shadow_root = os.path.join(self.project_root, "sandbox", "lorads_shadow_build")
        self.logs_dir = os.path.join(self.project_root, "sandbox", "lorads_logs")

        os.makedirs(self.logs_dir, exist_ok=True)

    def _load_config(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _infer_project_root(self):
        """
        Asume que el wrapper vive en tools/wrappers/lorads_wrapper.py
        """
        here = Path(__file__).resolve()
        return str(here.parents[2])

    def _safe_float(self, value, default=float("nan")):
        try:
            return float(value)
        except Exception:
            return default

    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    def _collect_source_files(self):
        if not os.path.isdir(self.src_root):
            raise RuntimeError(f"No existe src_root: {self.src_root}")

        sources = []
        for root, _, files in os.walk(self.src_root):
            for name in files:
                if name.lower().endswith(".c"):
                    sources.append(os.path.join(root, name))

        sources = sorted(sources)

        if not sources:
            raise RuntimeError(
                f"No se encontraron fuentes .c en {self.src_root}"
            )

        return sources

    def _write_shadow_cmakelists(self, sources):
        os.makedirs(self.shadow_root, exist_ok=True)

        cmake_path = os.path.join(self.shadow_root, "CMakeLists.txt")
        exe_name = "lorads_shadow"

        source_lines = []
        for src in sources:
            norm = Path(src).as_posix()
            source_lines.append(f'    "{norm}"')

        cmake_txt = f"""cmake_minimum_required(VERSION 3.16)
project({exe_name} C)

set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable({exe_name}
{chr(10).join(source_lines)}
)

target_include_directories({exe_name} PRIVATE
    "{Path(self.src_root).as_posix()}"
    "{Path(os.path.join(self.src_root, 'data')).as_posix()}"
    "{Path(os.path.join(self.src_root, 'io')).as_posix()}"
    "{Path(os.path.join(self.src_root, 'linalg')).as_posix()}"
    "{Path(os.path.join(self.src_root, 'lorads_alg')).as_posix()}"
)

if(MSVC)
    target_compile_definitions({exe_name} PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()
"""

        with open(cmake_path, "w", encoding="utf-8") as f:
            f.write(cmake_txt)

        return cmake_path

    def _find_existing_shadow_executable(self):
        candidates = [
            os.path.join(self.shadow_root, "build", "Release", "lorads_shadow.exe"),
            os.path.join(self.shadow_root, "build", "lorads_shadow.exe"),
            os.path.join(self.shadow_root, "build", "Debug", "lorads_shadow.exe"),
            os.path.join(self.shadow_root, "build", "RelWithDebInfo", "lorads_shadow.exe"),
            os.path.join(self.shadow_root, "build", "lorads_shadow"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def _build_shadow_executable(self, force_rebuild=False):
        existing = self._find_existing_shadow_executable()
        if existing and not force_rebuild:
            return existing

        sources = self._collect_source_files()
        self._write_shadow_cmakelists(sources)

        build_dir = os.path.join(self.shadow_root, "build")
        os.makedirs(build_dir, exist_ok=True)

        configure_cmd = [
            "cmake",
            "-S", self.shadow_root,
            "-B", build_dir,
            "-G", "Visual Studio 17 2022",
            "-A", "x64",
        ]

        build_cmd = [
            "cmake",
            "--build", build_dir,
            "--config", "Release",
        ]

        configure = subprocess.run(
            configure_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if configure.returncode != 0:
            raise RuntimeError(
                "Falló configuración CMake shadow.\n"
                f"STDOUT:\n{configure.stdout}\n\nSTDERR:\n{configure.stderr}"
            )

        build = subprocess.run(
            build_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if build.returncode != 0:
            raise RuntimeError(
                "Falló compilación CMake shadow.\n"
                f"STDOUT:\n{build.stdout}\n\nSTDERR:\n{build.stderr}"
            )

        exe = self._find_existing_shadow_executable()
        if not exe:
            raise RuntimeError(
                "La compilación terminó, pero no se encontró el ejecutable shadow."
            )

        return exe

    def _build_command(self, exe_path, instance_path):
        cmd = [
            exe_path,
            Path(instance_path).as_posix(),
            "--timesLogRank", str(self.times_log_rank),
            "--phase1Tol", str(self.phase1_tol),
            "--initRho", str(self.init_rho),
            "--rhoMax", str(self.rho_max),
            "--rhoFreq", str(self.rho_freq),
            "--rhoFactor", str(self.rho_factor),
            "--heuristicFactor", str(self.heuristic_factor),
            "--maxIter", str(self.max_iter),
            "--timeSecLimit", str(self.time_limit),
        ]
        return cmd

    def _extract_last_iteration_metrics(self, stdout_text):
        pattern = re.compile(
            r"Iter:\s*(?P<iter>\d+).*?"
            r"objVal:(?P<obj>[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)\s+"
            r"dualObj:(?P<dobj>[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)\s+"
            r"ConstrVio\(1\):(?P<pinf>[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)\s+"
            r"ConstrVio\(Inf\):(?P<pinf_inf>[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)\s+"
            r"PDGap:(?P<gap>[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)"
            r".*?Time:(?P<time>[+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(stdout_text))
        if not matches:
            return None

        m = matches[-1]
        return {
            "iterations": self._safe_int(m.group("iter")),
            "obj_val": self._safe_float(m.group("obj")),
            "dual_obj": self._safe_float(m.group("dobj")),
            "gap": self._safe_float(m.group("gap")),
            "pinfeas": self._safe_float(m.group("pinf")),
            "pinfeas_inf": self._safe_float(m.group("pinf_inf")),
            "runtime": self._safe_float(m.group("time")),
        }

    def _parse_stdout(self, stdout_text):
        result = {
            "status": "FAILED",
            "objective": float("nan"),
            "dual_objective": float("nan"),
            "gap": float("nan"),
            "pinf": float("nan"),
            "dinf": float("nan"),
            "phi": float("nan"),
            "runtime": float("nan"),
            "iterations": 0,
            "optimal": False,
        }

        primal_obj_match = re.search(
            r"Primal Objective:\s*:\s*([+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)",
            stdout_text,
        )
        dual_obj_match = re.search(
            r"Dual Objective:\s*:\s*([+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)",
            stdout_text,
        )
        pinf_match = re.search(
            r"Constraint Violation\(1\)\s*:\s*([+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)",
            stdout_text,
        )
        dinf_match = re.search(
            r"Dual Infeasibility\(1\)\s*:\s*([+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)",
            stdout_text,
        )
        gap_match = re.search(
            r"Primal Dual Gap\s*:\s*([+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)",
            stdout_text,
        )
        time_match = re.search(
            r"Solving .*? in ([+\-]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?) seconds",
            stdout_text,
        )
        term_match = re.search(
            r"End Program due to reaching `([^`]+)`",
            stdout_text,
        )

        last_iter = self._extract_last_iteration_metrics(stdout_text)

        if primal_obj_match:
            result["objective"] = self._safe_float(primal_obj_match.group(1))
        elif last_iter:
            result["objective"] = last_iter["obj_val"]

        if dual_obj_match:
            result["dual_objective"] = self._safe_float(dual_obj_match.group(1))
        elif last_iter:
            result["dual_objective"] = last_iter["dual_obj"]

        if pinf_match:
            result["pinf"] = self._safe_float(pinf_match.group(1))
        elif last_iter:
            result["pinf"] = last_iter["pinfeas"]

        if dinf_match:
            result["dinf"] = self._safe_float(dinf_match.group(1))

        if gap_match:
            result["gap"] = self._safe_float(gap_match.group(1))
        elif last_iter:
            result["gap"] = last_iter["gap"]

        if time_match:
            result["runtime"] = self._safe_float(time_match.group(1))
        elif last_iter:
            result["runtime"] = last_iter["runtime"]

        if last_iter:
            result["iterations"] = last_iter["iterations"]

        if all(not math.isnan(v) for v in [result["gap"], result["pinf"], result["dinf"]]):
            result["phi"] = max(result["gap"], result["pinf"], result["dinf"])
            result["optimal"] = result["phi"] <= self.tol

        if result["optimal"]:
            result["status"] = "OPTIMAL"
        elif term_match:
            term_text = term_match.group(1).lower()
            if "time" in term_text:
                result["status"] = "TIME_LIMIT"
            else:
                result["status"] = "STOPPED"
        elif last_iter:
            result["status"] = "PARTIAL"

        return result

    def solve(self, instance_path, force_rebuild=False):
        instance_path = os.path.abspath(instance_path)
        if not os.path.isfile(instance_path):
            raise FileNotFoundError(f"No existe la instancia: {instance_path}")

        exe_path = self._build_shadow_executable(force_rebuild=force_rebuild)

        cmd = self._build_command(exe_path, instance_path)
        log_file = os.path.join(
            self.logs_dir,
            f"{Path(instance_path).stem}_lorads.log"
        )

        start_wall = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.hard_kill_timeout,
        )

        stdout_text = start_wall.stdout or ""
        stderr_text = start_wall.stderr or ""

        with open(log_file, "w", encoding="utf-8") as f:
            f.write("COMMAND:\n")
            f.write(" ".join(cmd) + "\n\n")
            f.write("STDOUT:\n")
            f.write(stdout_text)
            f.write("\n\nSTDERR:\n")
            f.write(stderr_text)

        parsed = self._parse_stdout(stdout_text)
        parsed.update(
            {
                "instance": os.path.basename(instance_path),
                "dimension": None,
                "rank_used": None,
                "returncode": start_wall.returncode,
                "log_file": log_file,
                "executable": exe_path,
            }
        )

        if start_wall.returncode != 0 and parsed["status"] == "OPTIMAL":
            parsed["status"] = "PROCESS_ERROR"

        return parsed