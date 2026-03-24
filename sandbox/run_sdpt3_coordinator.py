from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path


def find_matlab_executable() -> str:
    """
    Busca el ejecutable de MATLAB.
    Primero intenta con PATH. Si no está, prueba ubicaciones comunes en Windows.
    """
    matlab = shutil.which("matlab")
    if matlab:
        return matlab

    common_paths = [
        r"C:\Program Files\MATLAB\R2025b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2024b\bin\matlab.exe",
        r"C:\Program Files\MATLAB\R2024a\bin\matlab.exe",
    ]

    for path in common_paths:
        if Path(path).is_file():
            return path

    raise FileNotFoundError(
        "No se encontró MATLAB. Agrega matlab.exe al PATH o ajusta "
        "las rutas en find_matlab_executable()."
    )


def matlab_path_string(path: Path) -> str:
    """
    Convierte Path a string con / para MATLAB.
    """
    return path.resolve().as_posix()


def build_matlab_command(repo_root: Path, config_path: Path) -> str:
    """
    Construye el comando MATLAB que:
    - cambia al root del repo
    - agrega tools/matlab/sdpt3 al path
    - agrega extern/sdpt3 al path
    - ejecuta run_sdpt3_benchmark(config_path)
    """
    matlab_tools = repo_root / "tools" / "matlab" / "sdpt3"
    sdpt3_repo = repo_root / "extern" / "sdpt3"

    repo_root_m = matlab_path_string(repo_root)
    matlab_tools_m = matlab_path_string(matlab_tools)
    sdpt3_repo_m = matlab_path_string(sdpt3_repo)
    config_path_m = matlab_path_string(config_path)

    cmd = (
        f"cd('{repo_root_m}'); "
        f"addpath(genpath('{matlab_tools_m}')); "
        f"addpath(genpath('{sdpt3_repo_m}')); "
        f"fprintf('MATLAB coordinator started\\n'); "
        f"fprintf('Repo root: {repo_root_m}\\n'); "
        f"fprintf('MATLAB tools: {matlab_tools_m}\\n'); "
        f"fprintf('SDPT3 path: {sdpt3_repo_m}\\n'); "
        f"fprintf('Config: {config_path_m}\\n'); "
        f"run_sdpt3_benchmark('{config_path_m}');"
    )
    return cmd


def validate_repo_structure(repo_root: Path, config_path: Path) -> None:
    """
    Valida que existan las carpetas/archivos críticos.
    """
    expected_paths = [
        repo_root / "tools" / "matlab" / "sdpt3",
        repo_root / "extern" / "sdpt3",
        config_path,
    ]

    missing = [str(p) for p in expected_paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Faltan rutas necesarias:\n- " + "\n- ".join(missing)
        )


def run_matlab_benchmark(repo_root: Path, config_path: Path) -> int:
    """
    Lanza MATLAB en modo batch.
    """
    matlab_exe = find_matlab_executable()
    matlab_cmd = build_matlab_command(repo_root, config_path)

    print("=" * 60)
    print("SDPT3 PYTHON COORDINATOR")
    print("=" * 60)
    print(f"Repo root : {repo_root}")
    print(f"Config    : {config_path}")
    print(f"MATLAB    : {matlab_exe}")
    print("=" * 60)

    process = subprocess.run(
        [matlab_exe, "-batch", matlab_cmd],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
    )

    print("\n" + "=" * 60)
    print("MATLAB STDOUT")
    print("=" * 60)
    print(process.stdout if process.stdout else "[sin salida stdout]")

    if process.stderr:
        print("\n" + "=" * 60)
        print("MATLAB STDERR")
        print("=" * 60)
        print(process.stderr)

    return process.returncode


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    config_path = repo_root / "config" / "benchmark_config.json"

    try:
        validate_repo_structure(repo_root, config_path)
        return_code = run_matlab_benchmark(repo_root, config_path)

        if return_code == 0:
            print("\nBenchmark finalizado correctamente.")
        else:
            print(f"\nBenchmark terminó con código de salida {return_code}.")
            sys.exit(return_code)

    except Exception as exc:
        print("\nERROR EN EL COORDINADOR PYTHON:")
        print(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()