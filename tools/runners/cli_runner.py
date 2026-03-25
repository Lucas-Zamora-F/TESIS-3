import os
import shlex
import shutil
import subprocess
import time
from typing import Any, Dict, Optional, Sequence, Union


CommandPart = Union[str, os.PathLike]


class CLIRunner:
    """
    Runner reutilizable para ejecutar binarios / comandos CLI desde Python.

    No hace parsing del solver.
    Solo ejecuta, captura salida, timeout, returncode y tiempo.
    """

    def __init__(
        self,
        working_dir: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> None:
        self.working_dir = (
            os.path.abspath(working_dir) if working_dir is not None else None
        )
        self.env = dict(env) if env is not None else os.environ.copy()

        if self.working_dir is not None and not os.path.isdir(self.working_dir):
            raise NotADirectoryError(
                f"No existe el directorio de trabajo: {self.working_dir}"
            )

    def _normalize_command(
        self,
        command: Union[str, Sequence[CommandPart]],
    ) -> list[str]:
        if isinstance(command, str):
            return shlex.split(command)
        return [os.fspath(part) for part in command]

    def _resolve_executable(self, executable: str) -> Optional[str]:
        if os.path.isabs(executable) or os.path.dirname(executable):
            abs_exec = os.path.abspath(executable)
            if os.path.isfile(abs_exec):
                return abs_exec
            return None
        return shutil.which(executable)

    def executable_exists(self, executable: str) -> bool:
        return self._resolve_executable(executable) is not None

    def run(
        self,
        command: Union[str, Sequence[CommandPart]],
        timeout: Optional[float] = None,
        cwd: Optional[str] = None,
        env_overrides: Optional[Dict[str, str]] = None,
        capture_output: bool = True,
        text: bool = True,
        check_executable: bool = True,
    ) -> Dict[str, Any]:
        cmd = self._normalize_command(command)
        if not cmd:
            raise ValueError("El comando no puede estar vacío.")

        run_cwd = os.path.abspath(cwd) if cwd is not None else self.working_dir
        if run_cwd is not None and not os.path.isdir(run_cwd):
            raise NotADirectoryError(f"No existe el directorio de trabajo: {run_cwd}")

        if check_executable:
            resolved_exec = self._resolve_executable(cmd[0])
            if resolved_exec is None:
                return {
                    "ok": False,
                    "timed_out": False,
                    "returncode": None,
                    "stdout": "",
                    "stderr": "",
                    "error": f"No se encontró el ejecutable: {cmd[0]}",
                    "time": 0.0,
                    "command": cmd,
                    "command_pretty": subprocess.list2cmdline(cmd),
                    "cwd": run_cwd,
                }
            cmd[0] = resolved_exec

        final_env = self.env.copy()
        if env_overrides:
            final_env.update(env_overrides)

        start = time.perf_counter()

        try:
            completed = subprocess.run(
                cmd,
                cwd=run_cwd,
                env=final_env,
                timeout=timeout,
                capture_output=capture_output,
                text=text,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            elapsed = time.perf_counter() - start

            return {
                "ok": completed.returncode == 0,
                "timed_out": False,
                "returncode": completed.returncode,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
                "error": None,
                "time": elapsed,
                "command": cmd,
                "command_pretty": subprocess.list2cmdline(cmd),
                "cwd": run_cwd,
            }

        except subprocess.TimeoutExpired as exc:
            elapsed = time.perf_counter() - start
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return {
                "ok": False,
                "timed_out": True,
                "returncode": None,
                "stdout": stdout,
                "stderr": stderr,
                "error": f"TimeoutExpired: el proceso excedió {timeout} segundos.",
                "time": elapsed,
                "command": cmd,
                "command_pretty": subprocess.list2cmdline(cmd),
                "cwd": run_cwd,
            }

        except Exception as exc:
            elapsed = time.perf_counter() - start
            return {
                "ok": False,
                "timed_out": False,
                "returncode": None,
                "stdout": "",
                "stderr": "",
                "error": str(exc),
                "time": elapsed,
                "command": cmd,
                "command_pretty": subprocess.list2cmdline(cmd),
                "cwd": run_cwd,
            }