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


class SDPT3Wrapper:
    """
    Wrapper v2 for SDPT3 using MatlabRunner + universal logger.
    """

    SOLVER_NAME = "sdpt3"

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
            "Initializing SDPT3Wrapper v2",
            extra={
                "run_id": self.run_id,
                "project_root": self.project_root,
                "config_path": self.config_path,
            },
        )

        self.config = self._load_config(self.config_path)

        global_cfg = self.config.get("global_settings", {})
        solver_cfg = self.config.get("solvers", {}).get("sdpt3", {})

        self.target_tol = float(global_cfg.get("tolerance_gap", 1e-6))
        self.max_iterations = int(global_cfg.get("max_iterations", 2000))
        self.time_limit_seconds = float(global_cfg.get("time_limit_seconds", 3600))
        self.verbose = int(global_cfg.get("verbose", 0))

        self.steptol = float(solver_cfg.get("steptol", 1e-8))
        self.gam = float(solver_cfg.get("gam", 0))

        self.sdpt3_repo = os.path.join(self.project_root, "extern", "sdpt3")
        self.sdpt3_matlab_dir = os.path.join(self.project_root, "tools", "matlab", "sdpt3")
        self.logs_dir = os.path.join(self.project_root, "sandbox", "sdpt3_logs_v2")

        os.makedirs(self.logs_dir, exist_ok=True)

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Configuration loaded for SDPT3Wrapper v2",
            extra={
                "target_tol": self.target_tol,
                "max_iterations": self.max_iterations,
                "time_limit_seconds": self.time_limit_seconds,
                "verbose": self.verbose,
                "steptol": self.steptol,
                "gam": self.gam,
                "sdpt3_repo": self.sdpt3_repo,
                "sdpt3_matlab_dir": self.sdpt3_matlab_dir,
                "logs_dir": self.logs_dir,
            },
        )

        self.runner = runner or MatlabRunner(
            startup_paths=[
                self.sdpt3_repo,
                self.sdpt3_matlab_dir,
            ]
        )

        try:
            self._prepare_matlab_environment()
            log_event(
                "INFO",
                self.SOLVER_NAME,
                "MATLAB environment prepared successfully",
                extra={
                    "startup_paths": [
                        self.sdpt3_repo,
                        self.sdpt3_matlab_dir,
                    ]
                },
            )
        except Exception as exc:
            log_exception(
                self.SOLVER_NAME,
                "Failed to prepare MATLAB environment for SDPT3",
                exc,
                extra={
                    "sdpt3_repo": self.sdpt3_repo,
                    "sdpt3_matlab_dir": self.sdpt3_matlab_dir,
                },
            )
            raise

    def _load_config(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _prepare_matlab_environment(self) -> None:
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Adding paths to MATLAB environment",
            extra={
                "recursive_paths": [
                    self.sdpt3_repo,
                    self.sdpt3_matlab_dir,
                ]
            },
        )

        self.runner.add_path(self.sdpt3_repo, recursive=True)
        self.runner.add_path(self.sdpt3_matlab_dir, recursive=True)

        sqlp_exists = self.runner.eval("exist('sqlp','file')", nargout=1)
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Checking availability of sqlp",
            extra={"eval_result": sqlp_exists},
        )

        if not sqlp_exists["ok"] or int(sqlp_exists["result"]) == 0:
            raise RuntimeError("SDPT3 not available: MATLAB cannot find 'sqlp'.")

        helper_exists = self.runner.eval("exist('run_sdpt3_instance','file')", nargout=1)
        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Checking availability of run_sdpt3_instance",
            extra={"eval_result": helper_exists},
        )

        if not helper_exists["ok"] or int(helper_exists["result"]) == 0:
            raise RuntimeError(
                "'run_sdpt3_instance.m' not found in tools/matlab/sdpt3."
            )

    def _matlab_str(self, value: str) -> str:
        return value.replace("\\", "/").replace("'", "''")

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
        matlab_time: Optional[float],
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

        if all(not math.isnan(v) for v in [gap, pinf, dinf]):
            phi = max(gap, pinf, dinf)
            optimal = phi <= self.target_tol
        else:
            phi = float("nan")
            optimal = False

        status = str(raw.get("status", "FAILED")).upper()

        if optimal:
            status = "OPTIMAL"
        elif status not in {"OPTIMAL", "STOPPED", "TIME_LIMIT", "FAILED"}:
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
            "Normalized SDPT3 result",
            extra=normalized,
        )

        return normalized

    def solve(self, instance_path: str) -> Dict[str, Any]:
        instance_path = os.path.abspath(instance_path)
        if not os.path.isfile(instance_path):
            raise FileNotFoundError(f"Instance file not found: {instance_path}")

        instance_name = os.path.basename(instance_path)
        instance_path_matlab = self._matlab_str(instance_path)

        log_path = os.path.join(
            self.logs_dir,
            f"{os.path.splitext(instance_name)[0]}_sdpt3_v2.log"
        )
        log_path_matlab = self._matlab_str(log_path)

        cmd = f"""
result = run_sdpt3_instance( ...
    '{instance_path_matlab}', ...
    'target_tol', {self.target_tol}, ...
    'max_iterations', {self.max_iterations}, ...
    'time_limit_seconds', {self.time_limit_seconds}, ...
    'verbose', {self.verbose}, ...
    'steptol', {self.steptol}, ...
    'gam', {self.gam}, ...
    'log_path', '{log_path_matlab}' ...
);
"""

        log_event(
            "INFO",
            self.SOLVER_NAME,
            "Starting instance solve with SDPT3",
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
            "MATLAB command sent to SDPT3",
            extra={
                "instance": instance_name,
                "command": cmd.strip(),
            },
        )

        try:
            exec_res = self.runner.eval(cmd, nargout=0)

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "MATLAB execution response received",
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
                    "error": exec_res["error"],
                    "log_file": log_path,
                }

                log_event(
                    "ERROR",
                    self.SOLVER_NAME,
                    "Failed to execute MATLAB command for SDPT3",
                    extra=out,
                )
                return out

            fetch_res = self.runner.eval("result", nargout=1)

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Raw result fetched from MATLAB",
                extra={
                    "instance": instance_name,
                    "fetch_ok": fetch_res.get("ok"),
                    "fetch_error": fetch_res.get("error"),
                },
            )

            if not fetch_res["ok"]:
                out = {
                    "instance": instance_name,
                    "status": "FAILED",
                    "error": fetch_res["error"],
                    "log_file": log_path,
                }

                log_event(
                    "ERROR",
                    self.SOLVER_NAME,
                    "Could not retrieve 'result' from MATLAB workspace",
                    extra=out,
                )
                return out

            raw = fetch_res["result"]

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Raw result retrieved from MATLAB",
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
                    "error": f"Unexpected result format: {type(raw)}",
                    "log_file": log_path,
                }

                log_event(
                    "ERROR",
                    self.SOLVER_NAME,
                    "Unexpected result format returned by MATLAB",
                    extra=out,
                )
                return out

            out = self._normalize_result(raw, instance_name, exec_res.get("time"))
            out["log_file"] = log_path
            out["run_id"] = self.run_id

            log_event(
                "INFO",
                self.SOLVER_NAME,
                "Instance solved and processed successfully",
                extra=out,
            )

            return out

        except Exception as exc:
            log_exception(
                self.SOLVER_NAME,
                "Unhandled exception during SDPT3 solve()",
                exc,
                extra={
                    "instance": instance_name,
                    "instance_path": instance_path,
                    "matlab_log_path": log_path,
                    "command": cmd.strip(),
                },
            )
            return {
                "instance": instance_name,
                "status": "FAILED",
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
                    "Closing MatlabRunner for SDPT3Wrapper",
                    extra={"run_id": self.run_id},
                )
                self.runner.stop()
                log_event(
                    "INFO",
                    self.SOLVER_NAME,
                    "MatlabRunner closed successfully",
                    extra={"run_id": self.run_id},
                )
            except Exception as exc:
                log_exception(
                    self.SOLVER_NAME,
                    "Error closing MatlabRunner",
                    exc,
                    extra={"run_id": self.run_id},
                )
