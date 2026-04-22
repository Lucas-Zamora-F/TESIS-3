import os
import time
from typing import Any, Dict, Iterable, List, Optional

import matlab.engine


class MatlabRunner:
    """
    Reusable runner for executing MATLAB code from Python.

    Responsibilities:
    - start and stop the MATLAB Engine
    - add paths to the MATLAB environment
    - execute MATLAB commands
    - invoke MATLAB functions
    - capture errors and measure elapsed time

    Does not parse solver results; that belongs in each wrapper.
    """

    def __init__(
        self,
        startup_paths: Optional[Iterable[str]] = None,
        start_engine_immediately: bool = True,
    ) -> None:
        self.startup_paths: List[str] = list(startup_paths or [])
        self.eng = None

        if start_engine_immediately:
            self.start()

    def start(self) -> None:
        """Start the MATLAB Engine if it is not already running."""
        if self.eng is not None:
            return

        self.eng = matlab.engine.start_matlab()

        if self.startup_paths:
            self.add_paths(self.startup_paths)

    def stop(self) -> None:
        """Stop the MATLAB Engine if it is active."""
        if self.eng is not None:
            try:
                self.eng.quit()
            finally:
                self.eng = None

    def __enter__(self) -> "MatlabRunner":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def _ensure_started(self) -> None:
        if self.eng is None:
            self.start()

    def add_path(self, path: str, recursive: bool = False) -> None:
        """
        Add a path to the MATLAB environment.

        Parameters
        ----------
        path : str
            Directory to add.
        recursive : bool
            If True, uses genpath(path) to include all subdirectories.
        """
        self._ensure_started()

        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise NotADirectoryError(f"Directory does not exist: {abs_path}")

        matlab_path = abs_path.replace("\\", "/")

        if recursive:
            self.eng.addpath(self.eng.genpath(matlab_path), nargout=0)
        else:
            self.eng.addpath(matlab_path, nargout=0)

    def add_paths(self, paths: Iterable[str], recursive: bool = False) -> None:
        """Add multiple paths to the MATLAB environment."""
        for path in paths:
            self.add_path(path, recursive=recursive)

    def eval(
        self,
        command: str,
        nargout: int = 0,
        measure_time: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a MATLAB command via eval.

        Returns
        -------
        dict
            {
                "ok": bool,
                "result": Any,
                "error": str | None,
                "time": float
            }
        """
        self._ensure_started()

        start = time.perf_counter()
        try:
            result = self.eng.eval(command, nargout=nargout)
            elapsed = time.perf_counter() - start if measure_time else None
            return {
                "ok": True,
                "result": result,
                "error": None,
                "time": elapsed,
            }
        except Exception as exc:
            elapsed = time.perf_counter() - start if measure_time else None
            return {
                "ok": False,
                "result": None,
                "error": str(exc),
                "time": elapsed,
            }

    def feval(
        self,
        func_name: str,
        *args: Any,
        nargout: int = 1,
        measure_time: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a MATLAB function by name.

        Example
        -------
        runner.feval("my_function", arg1, arg2, nargout=2)

        Returns
        -------
        dict
            {
                "ok": bool,
                "result": Any,
                "error": str | None,
                "time": float
            }
        """
        self._ensure_started()

        start = time.perf_counter()
        try:
            result = self.eng.feval(func_name, *args, nargout=nargout)
            elapsed = time.perf_counter() - start if measure_time else None
            return {
                "ok": True,
                "result": result,
                "error": None,
                "time": elapsed,
            }
        except Exception as exc:
            elapsed = time.perf_counter() - start if measure_time else None
            return {
                "ok": False,
                "result": None,
                "error": str(exc),
                "time": elapsed,
            }

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in the MATLAB base workspace."""
        self._ensure_started()
        self.eng.workspace[name] = value

    def get_variable(self, name: str) -> Any:
        """Retrieve a variable from the MATLAB base workspace."""
        self._ensure_started()
        return self.eng.workspace[name]

    def exists(self, name: str, kind: str = "file") -> int:
        """
        Call exist(...) in MATLAB.

        Common kind values: "file", "var", "dir".
        """
        self._ensure_started()
        return int(self.eng.exist(name, kind))

    def pwd(self) -> str:
        self._ensure_started()
        return str(self.eng.pwd())

    def cd(self, path: str) -> None:
        self._ensure_started()
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise NotADirectoryError(f"Directory does not exist: {abs_path}")
        self.eng.cd(abs_path.replace("\\", "/"), nargout=0)