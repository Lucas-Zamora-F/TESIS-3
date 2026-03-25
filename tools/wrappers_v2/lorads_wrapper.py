import json
import math
import os
import re
import subprocess
import threading
import time
from typing import Any, Dict, Optional

from tools.logging.universal_logger import (
    get_run_id,
    log_event,
    log_exception,
)
from tools.runners.cli_runner import CLIRunner


class LoRADSWrapper:
    """
    Wrapper v2 para LoRADS vía WSL.

    Cambios importantes respecto a la versión anterior:
    - crea el log del solver ANTES de lanzar el proceso;
    - usa subprocess directamente con stdin=DEVNULL para evitar bloqueos raros;
    - deja heartbeat en el log mientras la instancia sigue corriendo;
    - hace hard-kill robusto si se excede el timeout del wrapper;
    - mantiene el formato de salida normalizado usado por el tester.
    """

    SOLVER_NAME = "lorads"

    def __init__(
        self,
        config_path: str = "config/solver_config.json",
        project_root: Optional[str] = None,
        runner: Optional[CLIRunner] = None,
    ) -> None:
        self.project_root = os.path.abspath(
            project_root or os.path.join(os.path.dirname(__file__), "..", "..")
        )

        self.config_path = os.path.abspath(
            config_path
            if os.path.isabs(config_path)
            else os.path.join(self.project_root, config_path)
        )

        self.run_id = get_run_id()

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Inicializando LoRADSWrapper v2 (WSL)",
            extra={
                "run_id": self.run_id,
                "project_root": self.project_root,
                "config_path": self.config_path,
            },
        )

        self.config = self._load_config(self.config_path)

        global_cfg = self.config.get("global_settings", {})
        solver_cfg = self.config.get("solvers", {}).get("lorads", {})

        self.target_tol = float(global_cfg.get("tolerance_gap", 1e-6))
        self.max_iterations = int(global_cfg.get("max_iterations", 2000))
        self.time_limit_seconds = float(global_cfg.get("time_limit_seconds", 3600))
        self.verbose = int(global_cfg.get("verbose", 0))

        self.times_log_rank = float(solver_cfg.get("times_log_rank", 2.0))
        self.phase1_tol = float(solver_cfg.get("phase1_tol", 1e-3))
        self.init_rho = float(solver_cfg.get("init_rho", 0.0))
        self.rho_max = float(solver_cfg.get("rho_max", 5000.0))
        self.rho_freq = int(solver_cfg.get("rho_freq", 5))
        self.rho_factor = float(solver_cfg.get("rho_factor", 1.2))
        self.alm_rho_factor = float(solver_cfg.get("alm_rho_factor", 2.0))
        self.heuristic_factor = float(solver_cfg.get("heuristic_factor", 1.0))
        self.lbfgs_list_length = int(solver_cfg.get("lbfgs_list_length", 2))
        self.end_tau_tol = float(solver_cfg.get("end_tau_tol", 0.0))
        self.end_alm_sub_tol = float(solver_cfg.get("end_alm_sub_tol", 0.0))
        self.l2_rescaling = int(solver_cfg.get("l2_rescaling", 0))
        self.reopt_level = int(solver_cfg.get("reopt_level", 2))
        self.dyrank_level = int(solver_cfg.get("dyrank_level", 2))
        self.high_acc_mode = int(solver_cfg.get("high_acc_mode", 0))

        self.hard_kill_timeout_seconds = float(
            solver_cfg.get("hard_kill_timeout_seconds", self.time_limit_seconds + 30.0)
        )
        self.heartbeat_seconds = float(solver_cfg.get("heartbeat_seconds", 15.0))

        self.lorads_repo = os.path.join(self.project_root, "extern", "lorads")
        self.logs_dir = os.path.join(self.project_root, "sandbox", "lorads_logs_v2")
        os.makedirs(self.logs_dir, exist_ok=True)

        self.runner = runner or CLIRunner(working_dir=self.project_root)
        self.wsl_command = str(solver_cfg.get("wsl_command", "wsl"))
        self.executable_path = self._resolve_executable(solver_cfg)

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Configuración cargada para LoRADSWrapper v2 (WSL)",
            extra={
                "target_tol": self.target_tol,
                "max_iterations": self.max_iterations,
                "time_limit_seconds": self.time_limit_seconds,
                "hard_kill_timeout_seconds": self.hard_kill_timeout_seconds,
                "heartbeat_seconds": self.heartbeat_seconds,
                "times_log_rank": self.times_log_rank,
                "phase1_tol": self.phase1_tol,
                "init_rho": self.init_rho,
                "rho_max": self.rho_max,
                "rho_freq": self.rho_freq,
                "rho_factor": self.rho_factor,
                "alm_rho_factor": self.alm_rho_factor,
                "heuristic_factor": self.heuristic_factor,
                "lbfgs_list_length": self.lbfgs_list_length,
                "end_tau_tol": self.end_tau_tol,
                "end_alm_sub_tol": self.end_alm_sub_tol,
                "l2_rescaling": self.l2_rescaling,
                "reopt_level": self.reopt_level,
                "dyrank_level": self.dyrank_level,
                "high_acc_mode": self.high_acc_mode,
                "lorads_repo": self.lorads_repo,
                "logs_dir": self.logs_dir,
                "wsl_command": self.wsl_command,
                "executable_path": self.executable_path,
            },
        )

        if not self.executable_path:
            msg = (
                "No se encontró el ejecutable Linux de LoRADS para WSL. "
                "Configura solvers.lorads.executable_path con una ruta WSL, por ejemplo: "
                "/home/lucas_zamora/lorads_build/lorads_src/build/LoRADS_v_2_0_1-alpha"
            )
            log_event(
                "ERROR",
                self.SOLVER_NAME,
                "Ejecutable LoRADS WSL no encontrado",
                extra={
                    "searched_executable": self.executable_path,
                    "lorads_repo": self.lorads_repo,
                },
            )
            raise FileNotFoundError(msg)

    def _load_config(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró el archivo de configuración: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _windows_to_wsl_path(self, path: str) -> str:
        path = os.path.abspath(path)
        drive, rest = os.path.splitdrive(path)

        if not drive:
            return path.replace("\\", "/")

        drive_letter = drive[0].lower()
        rest = rest.replace("\\", "/")
        return f"/mnt/{drive_letter}{rest}"

    def _resolve_executable(self, solver_cfg: Dict[str, Any]) -> str:
        configured = solver_cfg.get("executable_path")
        if configured:
            if str(configured).startswith("/"):
                return str(configured)

            candidate = (
                configured
                if os.path.isabs(configured)
                else os.path.join(self.project_root, configured)
            )
            return self._windows_to_wsl_path(os.path.abspath(candidate))

        names = [
            "LoRADS_v_2_0_1-alpha",
            "LoRADS_v_2_0_1-alpha.exe",
            "LoRADS_v_1_0_0-alpha",
            "LoRADS_v_1_0_0-alpha.exe",
        ]

        candidate_dirs = [
            os.path.join(self.lorads_repo, "src", "build"),
            os.path.join(self.lorads_repo, "src", "build", "Release"),
            os.path.join(self.lorads_repo, "src", "build", "Debug"),
            os.path.join(self.lorads_repo, "build"),
            os.path.join(self.lorads_repo, "build", "Release"),
            os.path.join(self.lorads_repo, "build", "Debug"),
        ]

        for directory in candidate_dirs:
            for name in names:
                candidate = os.path.abspath(os.path.join(directory, name))
                if os.path.isfile(candidate):
                    return self._windows_to_wsl_path(candidate)

        return "/home/lucas_zamora/lorads_build/lorads_src/build/LoRADS_v_2_0_1-alpha"

    def _safe_float(self, x: Any, default=float("nan")) -> float:
        try:
            return float(x)
        except Exception:
            return default

    def _safe_int(self, x: Any, default=0) -> int:
        try:
            return int(x)
        except Exception:
            return default

    def _extract_float(self, pattern: str, text: str, default=float("nan")) -> float:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            return default
        try:
            return float(match.group(1))
        except Exception:
            return default

    def _extract_last_int(self, pattern: str, text: str, default=0) -> int:
        matches = re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not matches:
            return default
        try:
            return int(matches[-1])
        except Exception:
            return default

    def _command_pretty(self, command: list[str]) -> str:
        try:
            return subprocess.list2cmdline(command)
        except Exception:
            return " ".join(command)

    def _write_initial_solver_log(
        self,
        log_path: str,
        command_pretty: str,
        instance_name: str,
        instance_path: str,
        instance_wsl_path: str,
    ) -> None:
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write("=== LoRADS command ===\n")
            f.write(f"{command_pretty}\n\n")
            f.write("=== Metadata ===\n")
            f.write(f"instance: {instance_name}\n")
            f.write(f"instance_path: {instance_path}\n")
            f.write(f"instance_wsl_path: {instance_wsl_path}\n")
            f.write(f"run_id: {self.run_id}\n")
            f.write(f"target_tol: {self.target_tol}\n")
            f.write(f"max_iterations: {self.max_iterations}\n")
            f.write(f"time_limit_seconds: {self.time_limit_seconds}\n")
            f.write(f"hard_kill_timeout_seconds: {self.hard_kill_timeout_seconds}\n\n")
            f.write("=== Status ===\n")
            f.write("RUNNING...\n")

    def _write_final_solver_log(
        self,
        log_path: str,
        command_pretty: str,
        stdout: str,
        stderr: str,
        returncode: Optional[int],
        elapsed: Optional[float],
        timed_out: bool,
    ) -> None:
        with open(log_path, "w", encoding="utf-8", errors="replace") as f:
            f.write("=== LoRADS command ===\n")
            f.write(f"{command_pretty}\n\n")
            f.write("=== Metadata ===\n")
            f.write(f"returncode: {returncode}\n")
            f.write(f"elapsed: {elapsed}\n")
            f.write(f"timed_out: {timed_out}\n\n")
            f.write("=== STDOUT ===\n")
            f.write(stdout or "")
            f.write("\n\n=== STDERR ===\n")
            f.write(stderr or "")

    def _kill_process_tree(self, proc: subprocess.Popen) -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                proc.kill()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _run_process_with_timeout(
        self,
        command: list[str],
        timeout: float,
        cwd: str,
        log_path: str,
        instance_name: str,
    ) -> Dict[str, Any]:
        command_pretty = self._command_pretty(command)
        start = time.perf_counter()
        stop_heartbeat = threading.Event()

        def heartbeat_worker() -> None:
            next_log = time.monotonic() + self.heartbeat_seconds
            while not stop_heartbeat.wait(1.0):
                if time.monotonic() < next_log:
                    continue
                elapsed = time.perf_counter() - start
                msg = (
                    f"LoRADS sigue corriendo para {instance_name}. "
                    f"elapsed={elapsed:.1f}s"
                )
                log_event(
                    "INFO",
                    self.SOLVER_NAME,
                    msg,
                    extra={
                        "instance": instance_name,
                        "elapsed": elapsed,
                        "timeout": timeout,
                        "log_path": log_path,
                    },
                )
                try:
                    with open(log_path, "a", encoding="utf-8", errors="replace") as f:
                        f.write(f"[heartbeat] elapsed={elapsed:.1f}s\n")
                except Exception:
                    pass
                next_log = time.monotonic() + self.heartbeat_seconds

        heartbeat_thread = threading.Thread(
            target=heartbeat_worker,
            daemon=True,
            name=f"lorads_heartbeat_{instance_name}",
        )

        proc = None
        try:
            creationflags = 0
            popen_kwargs: Dict[str, Any] = {}
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            else:
                popen_kwargs["start_new_session"] = True

            proc = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                **popen_kwargs,
            )

            heartbeat_thread.start()

            try:
                stdout, stderr = proc.communicate(timeout=timeout)
                elapsed = time.perf_counter() - start
                return {
                    "ok": proc.returncode == 0,
                    "timed_out": False,
                    "returncode": proc.returncode,
                    "stdout": stdout or "",
                    "stderr": stderr or "",
                    "error": None,
                    "time": elapsed,
                    "command": command,
                    "command_pretty": command_pretty,
                    "cwd": cwd,
                }
            except subprocess.TimeoutExpired:
                self._kill_process_tree(proc)
                try:
                    stdout, stderr = proc.communicate(timeout=10)
                except Exception:
                    stdout = ""
                    stderr = ""
                elapsed = time.perf_counter() - start
                return {
                    "ok": False,
                    "timed_out": True,
                    "returncode": proc.returncode,
                    "stdout": stdout or "",
                    "stderr": stderr or "",
                    "error": f"TimeoutExpired: el proceso excedió {timeout} segundos.",
                    "time": elapsed,
                    "command": command,
                    "command_pretty": command_pretty,
                    "cwd": cwd,
                }

        except Exception as exc:
            elapsed = time.perf_counter() - start
            return {
                "ok": False,
                "timed_out": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "error": f"{type(exc).__name__}: {exc}",
                "time": elapsed,
                "command": command,
                "command_pretty": command_pretty,
                "cwd": cwd,
            }
        finally:
            stop_heartbeat.set()
            if heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=1.5)

    def _parse_output(
        self,
        text: str,
        instance_name: str,
        exec_res: Dict[str, Any],
    ) -> Dict[str, Any]:
        obj_val = self._extract_float(
            r"Primal Objective:\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )
        dual_obj = self._extract_float(
            r"Dual Objective:\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )
        pinfeas = self._extract_float(
            r"Constraint Violation\(1\)\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )
        dinfeas = self._extract_float(
            r"Dual Infeasibility\(1\)\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )
        gap = self._extract_float(
            r"Primal Dual Gap\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )
        pinf = self._extract_float(
            r"Constraint Violation\(Inf\)\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )
        dinf = self._extract_float(
            r"Dual Infeasibility\(Inf\)\s*:\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
            text,
        )

        runtime = self._extract_float(
            r"all_time:\s*([+-]?\d+(?:\.\d+)?)",
            text,
            default=self._safe_float(exec_res.get("time")),
        )
        if math.isnan(runtime):
            runtime = self._safe_float(exec_res.get("time"))

        iter_candidates = [
            self._extract_last_int(r"ADMM Iter:(\d+)", text, default=0),
            self._extract_last_int(r"ALM OuterIter:(\d+)", text, default=0),
            self._extract_last_int(r"\bIter:(\d+)", text, default=0),
            self._extract_last_int(r"OuterIter:(\d+)", text, default=0),
        ]
        iterations = max(iter_candidates)

        phi = float("nan")
        optimal = False
        if all(not math.isnan(v) for v in [gap, pinfeas, dinfeas]):
            phi = max(gap, pinfeas, dinfeas)
            optimal = phi <= self.target_tol

        low_text = text.lower()
        timed_out = bool(exec_res.get("timed_out"))

        if optimal:
            status = "OPTIMAL"
        elif timed_out or "time limit" in low_text:
            status = "TIME_LIMIT"
        elif "maximum number of iterations" in low_text:
            status = "STOPPED"
        elif "end program" in low_text:
            status = "STOPPED"
        elif exec_res.get("returncode") == 0:
            status = "STOPPED"
        else:
            status = "FAILED"

        numerr = 1 if "numerical error" in low_text else 0

        normalized = {
            "instance": instance_name,
            "status": status,
            "obj_val": obj_val,
            "dual_obj": dual_obj,
            "gap": gap,
            "pinfeas": pinfeas,
            "dinfeas": dinfeas,
            "phi": phi,
            "optimal": optimal,
            "iterations": iterations,
            "runtime": runtime,
            "numerr": numerr,
            "pinf": pinf,
            "dinf": dinf,
            "feasratio": float("nan"),
        }

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Resultado normalizado de LoRADS",
            extra=normalized,
        )

        return normalized

    def _build_command(self, instance_path: str) -> list[str]:
        instance_wsl = self._windows_to_wsl_path(instance_path)

        return [
            self.wsl_command,
            self.executable_path,
            instance_wsl,
            "--timesLogRank", str(self.times_log_rank),
            "--phase1Tol", str(self.phase1_tol),
            "--phase2Tol", str(self.target_tol),
            "--initRho", str(self.init_rho),
            "--rhoMax", str(self.rho_max),
            "--rhoFreq", str(self.rho_freq),
            "--rhoFactor", str(self.rho_factor),
            "--ALMRhoFactor", str(self.alm_rho_factor),
            "--heuristicFactor", str(self.heuristic_factor),
            "--maxALMIter", str(self.max_iterations),
            "--maxADMMIter", str(self.max_iterations),
            "--timeSecLimit", str(self.time_limit_seconds),
            "--lbfgsListLength", str(self.lbfgs_list_length),
            "--endTauTol", str(self.end_tau_tol),
            "--endALMSubTol", str(self.end_alm_sub_tol),
            "--l2Rescaling", str(self.l2_rescaling),
            "--reoptLevel", str(self.reopt_level),
            "--dyrankLevel", str(self.dyrank_level),
            "--highAccMode", str(self.high_acc_mode),
        ]

    def solve(self, instance_path: str) -> Dict[str, Any]:
        instance_path = os.path.abspath(instance_path)
        if not os.path.isfile(instance_path):
            raise FileNotFoundError(f"No existe la instancia: {instance_path}")

        instance_name = os.path.basename(instance_path)
        log_path = os.path.join(
            self.logs_dir,
            f"{os.path.splitext(instance_name)[0]}_lorads_v2.log",
        )

        instance_wsl_path = self._windows_to_wsl_path(instance_path)
        command = self._build_command(instance_path)
        command_pretty = self._command_pretty(command)

        self._write_initial_solver_log(
            log_path=log_path,
            command_pretty=command_pretty,
            instance_name=instance_name,
            instance_path=instance_path,
            instance_wsl_path=instance_wsl_path,
        )

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Iniciando resolución de instancia con LoRADS vía WSL",
            extra={
                "instance": instance_name,
                "instance_path": instance_path,
                "instance_wsl_path": instance_wsl_path,
                "log_path": log_path,
                "target_tol": self.target_tol,
                "max_iterations": self.max_iterations,
                "time_limit_seconds": self.time_limit_seconds,
                "hard_kill_timeout_seconds": self.hard_kill_timeout_seconds,
                "command": command,
            },
        )

        try:
            exec_res = self._run_process_with_timeout(
                command=command,
                timeout=self.hard_kill_timeout_seconds,
                cwd=self.project_root,
                log_path=log_path,
                instance_name=instance_name,
            )

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Respuesta de ejecución CLI recibida para LoRADS vía WSL",
                extra={
                    "instance": instance_name,
                    "exec_ok": exec_res.get("ok"),
                    "exec_time": exec_res.get("time"),
                    "exec_error": exec_res.get("error"),
                    "returncode": exec_res.get("returncode"),
                    "timed_out": exec_res.get("timed_out"),
                    "command_pretty": exec_res.get("command_pretty"),
                },
            )

            stdout = exec_res.get("stdout", "") or ""
            stderr = exec_res.get("stderr", "") or ""
            merged_text = stdout + ("\n" + stderr if stderr else "")

            self._write_final_solver_log(
                log_path=log_path,
                command_pretty=exec_res.get("command_pretty", command_pretty),
                stdout=stdout,
                stderr=stderr,
                returncode=exec_res.get("returncode"),
                elapsed=exec_res.get("time"),
                timed_out=bool(exec_res.get("timed_out")),
            )

            if exec_res.get("timed_out"):
                out = self._parse_output(merged_text, instance_name, exec_res)
                out["status"] = "TIME_LIMIT"
                out["optimal"] = False
                out["error"] = exec_res.get("error")
                out["log_file"] = log_path
                out["run_id"] = self.run_id

                log_event(
                    "WARNING",
                    self.SOLVER_NAME,
                    "LoRADS terminó por hard timeout del wrapper",
                    extra=out,
                )
                return out

            if not merged_text.strip():
                out = {
                    "instance": instance_name,
                    "status": "FAILED",
                    "obj_val": float("nan"),
                    "dual_obj": float("nan"),
                    "gap": float("nan"),
                    "pinfeas": float("nan"),
                    "dinfeas": float("nan"),
                    "phi": float("nan"),
                    "optimal": False,
                    "iterations": 0,
                    "runtime": self._safe_float(exec_res.get("time")),
                    "numerr": 0,
                    "pinf": float("nan"),
                    "dinf": float("nan"),
                    "feasratio": float("nan"),
                    "error": exec_res.get("error") or "LoRADS no produjo salida.",
                    "log_file": log_path,
                    "run_id": self.run_id,
                }

                log_event(
                    "ERROR",
                    self.SOLVER_NAME,
                    "LoRADS no produjo salida utilizable",
                    extra=out,
                )
                return out

            out = self._parse_output(merged_text, instance_name, exec_res)
            out["log_file"] = log_path
            out["run_id"] = self.run_id

            if not exec_res.get("ok") and out["status"] == "FAILED":
                out["error"] = (
                    exec_res.get("error")
                    or f"Return code: {exec_res.get('returncode')}"
                )

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Instancia resuelta y procesada correctamente con LoRADS",
                extra=out,
            )

            return out

        except Exception as exc:
            log_exception(
                self.SOLVER_NAME,
                "Excepción no controlada durante solve() de LoRADS",
                exc,
                extra={
                    "instance": instance_name,
                    "instance_path": instance_path,
                    "instance_wsl_path": instance_wsl_path,
                    "log_path": log_path,
                    "executable_path": self.executable_path,
                },
            )
            return {
                "instance": instance_name,
                "status": "FAILED",
                "obj_val": float("nan"),
                "dual_obj": float("nan"),
                "gap": float("nan"),
                "pinfeas": float("nan"),
                "dinfeas": float("nan"),
                "phi": float("nan"),
                "optimal": False,
                "iterations": 0,
                "runtime": float("nan"),
                "numerr": 0,
                "pinf": float("nan"),
                "dinf": float("nan"),
                "feasratio": float("nan"),
                "error": f"{type(exc).__name__}: {exc}",
                "log_file": log_path,
                "run_id": self.run_id,
            }

    def close(self) -> None:
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Cierre de LoRADSWrapper completado",
            extra={"run_id": self.run_id},
        )