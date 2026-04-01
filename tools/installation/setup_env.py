#!/usr/bin/env python3
"""
tools/installation/setup_env.py

Prepara el entorno general del repositorio.

Responsabilidades:
- Verificar estructura base del repo.
- Sincronizar y descargar todos los submódulos declarados en .gitmodules.
- Verificar e instalar dependencias Python necesarias.
- Iniciar MATLAB Engine.
- Verificar productos MATLAB requeridos por el repositorio.
- Agregar al path de MATLAB las carpetas relevantes del proyecto.
- Ejecutar instaladores de solvers MATLAB soportados por el repo.
- Verificar que el stack MATLAB/solvers quede realmente operativo.

Este script NO:
- lee solver_config.json
- decide qué solver está activo
- configura parámetros de corrida
- ejecuta experimentos

Su único objetivo es dejar el entorno listo para correr el repositorio en general.
"""

from __future__ import annotations

import configparser
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


# =============================================================================
# Configuración base
# =============================================================================

PYTHON_DEPENDENCIES: Dict[str, str] = {
    "pandas": "pandas",
    "matlabengine": "matlab.engine",
}

# Productos MATLAB que el repo declara como parte del entorno requerido hoy.
# Si más adelante limpias esta lista en el proyecto, ajústala aquí.
REQUIRED_MATLAB_PRODUCTS: List[str] = [
    "MATLAB",
    "Statistics and Machine Learning Toolbox",
    "Optimization Toolbox",
    "Signal Processing Toolbox",
    "Communications Toolbox",
]

# Paths MATLAB relevantes para el código actual del repositorio.
MATLAB_REPO_PATHS: List[Path] = [
    Path("tools"),
    Path("tools/matlab"),
    Path("tools/matlab/sdpt3"),
    Path("tools/matlab/sedumi"),
    Path("tools/runners"),
    Path("tools/wrappers_v2"),
    Path("extern/sdpt3"),
    Path("extern/sedumi"),
]

# Verificaciones críticas del stack MATLAB/solvers soportado hoy por el repo.
MATLAB_FUNCTION_CHECKS: List[Tuple[str, str]] = [
    ("SDPT3 entrypoint", "sqlp"),
    ("SDPT3 parameters", "sqlparameters"),
    ("SDPT3 reader", "read_sdpa"),
    ("SDPT3 mex", "mexsvec"),
    ("SeDuMi entrypoint", "sedumi"),
    ("SeDuMi reader", "fromsdpa"),
    ("SeDuMi cone helper", "eigK"),
    ("Repo helper", "run_sdpt3_instance"),
    ("Repo helper", "run_sedumi_instance"),
]


# =============================================================================
# Utilidades de consola
# =============================================================================

def print_header(title: str) -> None:
    line = "=" * 88
    print(f"\n{line}\n{title}\n{line}")


def print_info(message: str) -> None:
    print(f"[INFO] {message}")


def print_ok(message: str) -> None:
    print(f"[ OK ] {message}")


def print_warn(message: str) -> None:
    print(f"[WARN] {message}")


def print_fail(message: str) -> None:
    print(f"[FAIL] {message}")


def run_command(
    cmd: Sequence[str],
    *,
    cwd: Optional[Path] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    print_info("Ejecutando: " + " ".join(cmd))
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd else None,
        text=True,
        check=check,
    )


# =============================================================================
# Repo / estructura
# =============================================================================

def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_repo_layout(repo_root: Path) -> None:
    required_paths = [
        repo_root / ".gitmodules",
        repo_root / "tools",
        repo_root / "config",
        repo_root / "tools" / "installation",
    ]
    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise RuntimeError(
            "La estructura del repositorio no parece válida. Faltan estas rutas:\n- "
            + "\n- ".join(missing)
        )


def read_gitmodules_paths(repo_root: Path) -> List[Path]:
    gitmodules_path = repo_root / ".gitmodules"
    if not gitmodules_path.exists():
        return []

    parser = configparser.ConfigParser()
    parser.read(gitmodules_path, encoding="utf-8")

    submodule_paths: List[Path] = []
    for section in parser.sections():
        if parser.has_option(section, "path"):
            raw_path = parser.get(section, "path").strip()
            if raw_path:
                submodule_paths.append(Path(raw_path))

    return submodule_paths


# =============================================================================
# Git / submódulos
# =============================================================================

def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("No se encontró 'git' en PATH. Instálalo antes de continuar.")


def sync_and_update_submodules(repo_root: Path) -> List[Path]:
    print_header("1. Submódulos git")
    ensure_git_available()

    submodule_paths = read_gitmodules_paths(repo_root)
    if not submodule_paths:
        print_warn("No se encontraron submódulos en .gitmodules.")
        return []

    run_command(["git", "submodule", "sync", "--recursive"], cwd=repo_root)
    run_command(["git", "submodule", "update", "--init", "--recursive"], cwd=repo_root)

    missing = [str(repo_root / rel_path) for rel_path in submodule_paths if not (repo_root / rel_path).exists()]
    if missing:
        raise RuntimeError(
            "Después de actualizar submódulos, aún faltan estas rutas:\n- "
            + "\n- ".join(missing)
        )

    for rel_path in submodule_paths:
        print_ok(f"Submódulo presente: {rel_path}")

    return submodule_paths


# =============================================================================
# Python
# =============================================================================

def module_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def install_python_package(package_name: str) -> None:
    run_command([sys.executable, "-m", "pip", "install", package_name])


def ensure_python_dependencies() -> None:
    print_header("2. Dependencias Python")

    missing_packages = [
        package_name
        for package_name, module_name in PYTHON_DEPENDENCIES.items()
        if not module_exists(module_name)
    ]

    if not missing_packages:
        for package_name in PYTHON_DEPENDENCIES:
            print_ok(f"Disponible: {package_name}")
        return

    for package_name in missing_packages:
        print_warn(f"Falta {package_name}. Intentando instalar...")
        install_python_package(package_name)

    still_missing = [
        package_name
        for package_name, module_name in PYTHON_DEPENDENCIES.items()
        if not module_exists(module_name)
    ]
    if still_missing:
        raise RuntimeError(
            "No se pudieron instalar estas dependencias Python:\n- "
            + "\n- ".join(still_missing)
        )

    for package_name in PYTHON_DEPENDENCIES:
        print_ok(f"Disponible: {package_name}")


# =============================================================================
# MATLAB helpers
# =============================================================================

def import_matlab_engine():
    try:
        import matlab.engine  # type: ignore
        return matlab.engine
    except Exception as exc:
        raise RuntimeError(
            "No fue posible importar matlab.engine. "
            "Verifica que MATLAB esté instalado y que el paquete 'matlabengine' "
            "sea compatible con tu versión de Python."
        ) from exc


def matlab_exist(eng, name: str, kind: str = "file") -> int:
    return int(eng.exist(name, kind))


def matlab_which(eng, name: str) -> str:
    try:
        result = eng.which(name, nargout=1)
        return str(result)
    except Exception:
        return ""


def get_installed_matlab_products(eng) -> List[str]:
    values = eng.eval("{ver().Name}", nargout=1)
    return [str(value) for value in values]


def ensure_required_matlab_products(eng) -> None:
    print_header("3. Productos de MATLAB")

    installed_products = get_installed_matlab_products(eng)
    for product in installed_products:
        print(f" - {product}")

    missing = [product for product in REQUIRED_MATLAB_PRODUCTS if product not in installed_products]
    if missing:
        raise RuntimeError(
            "Faltan productos oficiales de MATLAB requeridos por el repositorio:\n- "
            + "\n- ".join(missing)
            + "\n\nInstálalos desde MATLAB/MathWorks y vuelve a ejecutar este script."
        )

    print_ok("Productos de MATLAB verificados.")


def reset_and_add_repo_paths(eng, repo_root: Path) -> None:
    print_header("4. Paths del repositorio en MATLAB")

    eng.restoredefaultpath(nargout=0)
    eng.rehash(nargout=0)

    for rel_path in MATLAB_REPO_PATHS:
        abs_path = repo_root / rel_path
        if abs_path.exists():
            matlab_path = abs_path.as_posix().replace("'", "''")
            eng.eval(f"addpath(genpath('{matlab_path}'));", nargout=0)
            print_ok(f"Path agregado: {rel_path}")
        else:
            print_warn(f"Path no existe y se omite: {rel_path}")

    eng.rehash(nargout=0)
    print_ok("Paths del repositorio agregados a MATLAB.")


def configure_mex_compilers(eng) -> None:
    print_header("5. Configuración MEX")

    try:
        eng.eval("mex -setup C", nargout=0)
        print_ok("Compilador MEX C configurado.")
    except Exception as exc:
        print_warn(f"No se pudo configurar MEX C automáticamente: {exc}")

    try:
        eng.eval("mex -setup C++", nargout=0)
        print_ok("Compilador MEX C++ configurado.")
    except Exception as exc:
        print_warn(f"No se pudo configurar MEX C++ automáticamente: {exc}")


# =============================================================================
# Preparación de solvers MATLAB soportados por el repo
# =============================================================================

def run_matlab_installer_if_available(
    eng,
    working_dir: Path,
    script_name: str,
    *,
    allow_rebuild: bool = False,
) -> None:
    if not working_dir.exists():
        print_warn(f"No existe la carpeta {working_dir}. Se omite {script_name}.")
        return

    old_dir = eng.pwd(nargout=1)
    try:
        eng.cd(working_dir.as_posix(), nargout=0)

        if matlab_exist(eng, script_name, "file") == 0:
            raise RuntimeError(f"MATLAB no encuentra '{script_name}' dentro de {working_dir}")

        try:
            eng.eval(script_name, nargout=0)
            print_ok(f"{script_name} ejecutado correctamente.")
        except Exception as exc:
            if allow_rebuild:
                print_warn(f"{script_name} falló. Intentando rebuild...")
                eng.eval(f"{script_name} -rebuild", nargout=0)
                print_ok(f"{script_name} -rebuild ejecutado correctamente.")
            else:
                raise RuntimeError(f"Falló {script_name}: {exc}") from exc
    finally:
        eng.cd(old_dir, nargout=0)


def prepare_supported_solvers(eng, repo_root: Path) -> None:
    print_header("6. Preparación de solvers soportados")

    sdpt3_dir = repo_root / "extern" / "sdpt3"
    sedumi_dir = repo_root / "extern" / "sedumi"

    run_matlab_installer_if_available(
        eng,
        sdpt3_dir,
        "install_sdpt3",
        allow_rebuild=True,
    )
    run_matlab_installer_if_available(
        eng,
        sedumi_dir,
        "install_sedumi",
        allow_rebuild=False,
    )

    # Algunos instaladores alteran el path de MATLAB.
    reset_and_add_repo_paths(eng, repo_root)


# =============================================================================
# Verificaciones finales
# =============================================================================

def verify_matlab_solver_stack(eng) -> None:
    print_header("7. Verificación final MATLAB / solvers")

    failures: List[str] = []

    for label, func_name in MATLAB_FUNCTION_CHECKS:
        exists = matlab_exist(eng, func_name, "file")
        if exists:
            location = matlab_which(eng, func_name)
            print_ok(f"{label}: {func_name} -> {location}")
        else:
            print_fail(f"{label}: MATLAB no encuentra '{func_name}'")
            failures.append(f"{label}: {func_name}")

    if failures:
        raise RuntimeError(
            "El setup terminó, pero siguen faltando funciones críticas:\n- "
            + "\n- ".join(failures)
            + "\n\nEl entorno no quedó listo para correr el repositorio."
        )

    print_ok("Verificación MATLAB / solvers superada.")


def smoke_test_repo_helpers(repo_root: Path, eng) -> None:
    print_header("8. Smoke test de helpers del repo")

    required_helpers = [
        repo_root / "tools" / "matlab" / "sdpt3" / "run_sdpt3_instance.m",
        repo_root / "tools" / "matlab" / "sedumi" / "run_sedumi_instance.m",
    ]

    missing_files = [str(path) for path in required_helpers if not path.exists()]
    if missing_files:
        raise RuntimeError(
            "Faltan helpers MATLAB esperados del repositorio:\n- "
            + "\n- ".join(missing_files)
        )

    if matlab_exist(eng, "run_sdpt3_instance", "file") == 0:
        raise RuntimeError("MATLAB no encuentra run_sdpt3_instance después del setup.")
    if matlab_exist(eng, "run_sedumi_instance", "file") == 0:
        raise RuntimeError("MATLAB no encuentra run_sedumi_instance después del setup.")

    print_ok("Helpers MATLAB del repo visibles y listos.")


def summarize(repo_root: Path, submodule_paths: List[Path]) -> None:
    print_header("9. Resumen final")
    print_ok(f"Raíz del repo: {repo_root}")

    if submodule_paths:
        print_ok("Submódulos preparados:")
        for rel_path in submodule_paths:
            print(f"     - {rel_path}")
    else:
        print_warn("No había submódulos declarados en .gitmodules.")

    print_ok("Dependencias Python: OK")
    print_ok("Productos MATLAB: OK")
    print_ok("Paths MATLAB del repo: OK")
    print_ok("SDPT3: OK")
    print_ok("SeDuMi: OK")
    print_ok("Entorno general del repositorio listo.")


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    repo_root = repo_root_from_script()

    print_header("SETUP DEL ENTORNO DEL REPOSITORIO")
    print_info(f"Raíz detectada: {repo_root}")

    ensure_repo_layout(repo_root)
    submodule_paths = sync_and_update_submodules(repo_root)
    ensure_python_dependencies()

    matlab_engine = import_matlab_engine()

    print_header("Iniciando MATLAB Engine")
    eng = matlab_engine.start_matlab()
    try:
        ensure_required_matlab_products(eng)
        reset_and_add_repo_paths(eng, repo_root)
        configure_mex_compilers(eng)
        prepare_supported_solvers(eng, repo_root)
        verify_matlab_solver_stack(eng)
        smoke_test_repo_helpers(repo_root, eng)
    finally:
        try:
            eng.quit()
        except Exception:
            pass

    summarize(repo_root, submodule_paths)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print_header("SETUP FALLÓ")
        print(str(exc))
        raise