import json
import math
import os
from typing import Any, Dict, Optional

from tools.runners.matlab_runner import MatlabRunner
from tools.logging.universal_logger import (
    get_run_id,
    log_event,
    log_exception,
)


class SeDuMiWrapper:
    """
    Wrapper v2 para SeDuMi usando MatlabRunner, pero con la lógica
    numérica del wrapper antiguo + logger universal.

    Requiere:
    - tools/runners/matlab_runner.py
    - tools/matlab/sedumi/run_sedumi_instance.m
    - extern/sedumi disponible
    """

    SOLVER_NAME = "sedumi"

    def __init__(
        self,
        config_path: str = "config/solver_config.json",
        project_root: Optional[str] = None,
        runner: Optional[MatlabRunner] = None,
    ) -> None:
        self.project_root = os.path.abspath(
            project_root or os.path.join(os.path.dirname(__file__), "..", "..")
        )

        self.config_path = os.path.abspath(
            config_path if os.path.isabs(config_path)
            else os.path.join(self.project_root, config_path)
        )

        self.run_id = get_run_id()

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Inicializando SeDuMiWrapper v2",
            extra={
                "run_id": self.run_id,
                "project_root": self.project_root,
                "config_path": self.config_path,
            },
        )

        self.config = self._load_config(self.config_path)

        global_cfg = self.config.get("global_settings", {})
        solver_cfg = self.config.get("solvers", {}).get("sedumi", {})

        self.target_tol = float(global_cfg.get("tolerance_gap", 1e-6))
        self.max_iterations = int(global_cfg.get("max_iterations", 2000))
        self.time_limit_seconds = float(global_cfg.get("time_limit_seconds", 3600))
        self.verbose = int(global_cfg.get("verbose", 0))

        self.bigeps = float(solver_cfg.get("bigeps", 1e-3))
        self.stepdif = float(solver_cfg.get("stepdif", 2))
        self.beta = float(solver_cfg.get("beta", 0.5))
        self.theta = float(solver_cfg.get("theta", 0.25))
        self.alg = int(solver_cfg.get("alg", 2))

        self.sedumi_repo = os.path.join(self.project_root, "extern", "sedumi")
        self.sedumi_matlab_dir = os.path.join(self.project_root, "tools", "matlab", "sedumi")
        self.logs_dir = os.path.join(self.project_root, "sandbox", "sedumi_logs_v2")

        os.makedirs(self.logs_dir, exist_ok=True)

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Configuración cargada para SeDuMiWrapper v2",
            extra={
                "target_tol": self.target_tol,
                "max_iterations": self.max_iterations,
                "time_limit_seconds": self.time_limit_seconds,
                "verbose": self.verbose,
                "bigeps": self.bigeps,
                "stepdif": self.stepdif,
                "beta": self.beta,
                "theta": self.theta,
                "alg": self.alg,
                "sedumi_repo": self.sedumi_repo,
                "sedumi_matlab_dir": self.sedumi_matlab_dir,
                "logs_dir": self.logs_dir,
            },
        )

        self.runner = runner or MatlabRunner(
            startup_paths=[
                self.sedumi_repo,
                self.sedumi_matlab_dir,
            ]
        )

        try:
            self._prepare_matlab_environment()
            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Entorno MATLAB preparado correctamente para SeDuMi",
                extra={
                    "startup_paths": [
                        self.sedumi_repo,
                        self.sedumi_matlab_dir,
                    ]
                },
            )
        except Exception as exc:
            log_exception(
                self.SOLVER_NAME,
                "Fallo preparando entorno MATLAB para SeDuMi",
                exc,
                extra={
                    "sedumi_repo": self.sedumi_repo,
                    "sedumi_matlab_dir": self.sedumi_matlab_dir,
                },
            )
            raise

    def _load_config(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró el archivo de configuración: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _prepare_matlab_environment(self) -> None:
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Agregando paths al entorno MATLAB para SeDuMi",
            extra={
                "recursive_paths": [
                    self.sedumi_repo,
                    self.sedumi_matlab_dir,
                ]
            },
        )

        self.runner.add_path(self.sedumi_repo, recursive=True)
        self.runner.add_path(self.sedumi_matlab_dir, recursive=True)

        sedumi_exists = self.runner.eval("exist('sedumi','file')", nargout=1)
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Verificación de disponibilidad de sedumi",
            extra={"eval_result": sedumi_exists},
        )
        if not sedumi_exists["ok"] or int(sedumi_exists["result"]) == 0:
            raise RuntimeError("SeDuMi no disponible: MATLAB no encuentra 'sedumi'.")

        fromsdpa_exists = self.runner.eval("exist('fromsdpa','file')", nargout=1)
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Verificación de disponibilidad de fromsdpa",
            extra={"eval_result": fromsdpa_exists},
        )
        if not fromsdpa_exists["ok"] or int(fromsdpa_exists["result"]) == 0:
            raise RuntimeError("MATLAB no encuentra 'fromsdpa' para leer instancias .dat-s.")

        eigk_exists = self.runner.eval("exist('eigK','file')", nargout=1)
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Verificación de disponibilidad de eigK",
            extra={"eval_result": eigk_exists},
        )
        if not eigk_exists["ok"] or int(eigk_exists["result"]) == 0:
            raise RuntimeError("MATLAB no encuentra 'eigK', necesario para el cálculo de dinfeas.")

        helper_exists = self.runner.eval("exist('run_sedumi_instance','file')", nargout=1)
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Verificación de disponibilidad de run_sedumi_instance",
            extra={"eval_result": helper_exists},
        )
        if not helper_exists["ok"] or int(helper_exists["result"]) == 0:
            raise RuntimeError(
                "No se encontró 'run_sedumi_instance.m' en tools/matlab/sedumi."
            )

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

    def _normalize_result(
        self,
        raw: Dict[str, Any],
        instance_name: str,
        matlab_time: Optional[float]
    ) -> Dict[str, Any]:
        obj_val = self._safe_float(raw.get("obj_val"))
        gap = self._safe_float(raw.get("gap"))
        pinf = self._safe_float(raw.get("pinfeas"))
        dinf = self._safe_float(raw.get("dinfeas"))
        runtime = self._safe_float(raw.get("runtime"), default=matlab_time or float("nan"))
        iterations = self._safe_int(raw.get("iterations"))
        numerr = self._safe_int(raw.get("numerr"))
        pinf_aux = self._safe_float(raw.get("pinf"))
        dinf_aux = self._safe_float(raw.get("dinf"))
        feasratio = self._safe_float(raw.get("feasratio"))

        phi = self._safe_float(raw.get("phi"))
        optimal = False

        if not math.isnan(phi):
            optimal = phi <= self.target_tol
        elif all(not math.isnan(v) for v in [gap, pinf, dinf]):
            phi = max(gap, pinf, dinf)
            optimal = phi <= self.target_tol

        raw_status = str(raw.get("status", "FAILED")).upper()

        if optimal:
            status = "OPTIMAL"
        elif raw_status in {"TIME_LIMIT", "FAILED"}:
            status = raw_status
        else:
            status = "STOPPED"

        normalized = {
            "instance": instance_name,
            "status": status,
            "obj_val": obj_val,
            "gap": gap,
            "pinfeas": pinf,
            "dinfeas": dinf,
            "phi": phi,
            "optimal": optimal,
            "iterations": iterations,
            "runtime": runtime,
            "numerr": numerr,
            "pinf": pinf_aux,
            "dinf": dinf_aux,
            "feasratio": feasratio,
        }

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Resultado normalizado de SeDuMi",
            extra=normalized,
        )

        return normalized

    def solve(self, instance_path: str) -> Dict[str, Any]:
        instance_path = os.path.abspath(instance_path)
        if not os.path.isfile(instance_path):
            raise FileNotFoundError(f"No existe la instancia: {instance_path}")

        instance_name = os.path.basename(instance_path)
        log_path = os.path.join(
            self.logs_dir,
            f"{os.path.splitext(instance_name)[0]}_sedumi_v2.log"
        )

        matlab_instance_path = instance_path.replace("\\", "/")
        matlab_log_path = log_path.replace("\\", "/")

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Iniciando resolución de instancia con SeDuMi",
            extra={
                "instance": instance_name,
                "instance_path": instance_path,
                "matlab_log_path": log_path,
                "target_tol": self.target_tol,
                "max_iterations": self.max_iterations,
                "time_limit_seconds": self.time_limit_seconds,
            },
        )

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Argumentos enviados a run_sedumi_instance",
            extra={
                "instance": instance_name,
                "function": "run_sedumi_instance",
                "args": {
                    "instance_path": matlab_instance_path,
                    "target_tol": float(self.target_tol),
                    "max_iterations": float(self.max_iterations),
                    "time_limit_seconds": float(self.time_limit_seconds),
                    "verbose": float(self.verbose),
                    "bigeps": float(self.bigeps),
                    "stepdif": float(self.stepdif),
                    "beta": float(self.beta),
                    "theta": float(self.theta),
                    "alg": float(self.alg),
                    "log_path": matlab_log_path,
                },
            },
        )

        try:
            exec_res = self.runner.feval(
                "run_sedumi_instance",
                matlab_instance_path,
                "target_tol", float(self.target_tol),
                "max_iterations", float(self.max_iterations),
                "time_limit_seconds", float(self.time_limit_seconds),
                "verbose", float(self.verbose),
                "bigeps", float(self.bigeps),
                "stepdif", float(self.stepdif),
                "beta", float(self.beta),
                "theta", float(self.theta),
                "alg", float(self.alg),
                "log_path", matlab_log_path,
                nargout=1,
            )

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Respuesta de ejecución MATLAB recibida para SeDuMi",
                extra={
                    "instance": instance_name,
                    "exec_ok": exec_res.get("ok"),
                    "exec_time": exec_res.get("time"),
                    "exec_error": exec_res.get("error"),
                },
            )

            if not exec_res["ok"]:
                out = {
                    "instance": instance_name,
                    "status": "FAILED",
                    "obj_val": float("nan"),
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
                    "error": exec_res["error"],
                    "log_file": log_path,
                    "run_id": self.run_id,
                }

                log_event(
                    "ERROR",
                    self.SOLVER_NAME,
                    "Fallo al ejecutar run_sedumi_instance",
                    extra=out,
                )
                return out

            raw = exec_res["result"]

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Resultado bruto recuperado desde SeDuMi",
                extra={
                    "instance": instance_name,
                    "raw_type": str(type(raw)),
                    "raw_preview": raw if isinstance(raw, dict) else str(raw),
                },
            )

            if not isinstance(raw, dict):
                out = {
                    "instance": instance_name,
                    "status": "FAILED",
                    "obj_val": float("nan"),
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
                    "error": f"Formato MATLAB inesperado: {type(raw)}",
                    "log_file": log_path,
                    "run_id": self.run_id,
                }

                log_event(
                    "ERROR",
                    self.SOLVER_NAME,
                    "Formato inesperado del resultado devuelto por SeDuMi",
                    extra=out,
                )
                return out

            out = self._normalize_result(raw, instance_name, exec_res.get("time"))
            out["log_file"] = log_path
            out["run_id"] = self.run_id

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Instancia resuelta y procesada correctamente con SeDuMi",
                extra=out,
            )

            return out

        except Exception as exc:
            log_exception(
                self.SOLVER_NAME,
                "Excepción no controlada durante solve() de SeDuMi",
                exc,
                extra={
                    "instance": instance_name,
                    "instance_path": instance_path,
                    "matlab_log_path": log_path,
                },
            )
            return {
                "instance": instance_name,
                "status": "FAILED",
                "obj_val": float("nan"),
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
        if self.runner is not None:
            try:
                log_event(
                    "INFO",
                    self.SOLVER_NAME,
                    "Cerrando MatlabRunner de SeDuMiWrapper",
                    extra={"run_id": self.run_id},
                )
                self.runner.stop()
                log_event(
                    "INFO",
                    self.SOLVER_NAME,
                    "MatlabRunner cerrado correctamente para SeDuMi",
                    extra={"run_id": self.run_id},
                )
            except Exception as exc:
                log_exception(
                    self.SOLVER_NAME,
                    "Error al cerrar MatlabRunner de SeDuMi",
                    exc,
                    extra={"run_id": self.run_id},
                )