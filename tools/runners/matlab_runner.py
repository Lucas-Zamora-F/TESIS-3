import os
import time
from typing import Any, Dict, Iterable, List, Optional

import matlab.engine


class MatlabRunner:
    """
    Runner reutilizable para ejecutar código MATLAB desde Python.

    Responsabilidades:
    - iniciar y cerrar MATLAB Engine
    - agregar paths al entorno MATLAB
    - ejecutar comandos MATLAB
    - invocar funciones MATLAB
    - capturar errores y medir tiempos

    No hace parsing de resultados del solver.
    Eso debe vivir en cada wrapper.
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
        """
        Inicia MATLAB Engine si no está iniciado.
        """
        if self.eng is not None:
            return

        self.eng = matlab.engine.start_matlab()

        if self.startup_paths:
            self.add_paths(self.startup_paths)

    def stop(self) -> None:
        """
        Cierra MATLAB Engine si está activo.
        """
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
        Agrega un path a MATLAB.

        Parameters
        ----------
        path : str
            Ruta a agregar.
        recursive : bool
            Si True, usa genpath(path).
        """
        self._ensure_started()

        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            raise NotADirectoryError(f"No existe el directorio MATLAB path: {abs_path}")

        matlab_path = abs_path.replace("\\", "/")

        if recursive:
            self.eng.addpath(self.eng.genpath(matlab_path), nargout=0)
        else:
            self.eng.addpath(matlab_path, nargout=0)

    def add_paths(self, paths: Iterable[str], recursive: bool = False) -> None:
        """
        Agrega múltiples paths a MATLAB.
        """
        for path in paths:
            self.add_path(path, recursive=recursive)

    def eval(
        self,
        command: str,
        nargout: int = 0,
        measure_time: bool = True,
    ) -> Dict[str, Any]:
        """
        Ejecuta un comando MATLAB vía eval.

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
        Ejecuta una función MATLAB por nombre.

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
        """
        Define una variable en el workspace base de MATLAB.
        """
        self._ensure_started()
        self.eng.workspace[name] = value

    def get_variable(self, name: str) -> Any:
        """
        Recupera una variable del workspace base de MATLAB.
        """
        self._ensure_started()
        return self.eng.workspace[name]

    def exists(self, name: str, kind: str = "file") -> int:
        """
        Consulta exist(...) en MATLAB.

        kind típicos:
        - "file"
        - "var"
        - "dir"
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
            raise NotADirectoryError(f"No existe el directorio MATLAB cwd: {abs_path}")
        self.eng.cd(abs_path.replace("\\", "/"), nargout=0)