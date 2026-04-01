from __future__ import annotations

from pathlib import Path

import matlab.engine


def find_repo_root(start: Path) -> Path:
    """
    Busca la raiz del repositorio subiendo directorios hasta encontrar
    una carpeta que contenga 'extern' y 'sandbox'.
    """
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "extern").exists() and (candidate / "sandbox").exists():
            return candidate
    raise FileNotFoundError(
        "No se pudo detectar la raiz del repositorio desde la ubicacion actual."
    )


def main() -> None:
    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path)

    instance_space_path = repo_root / "extern" / "InstanceSpace87fe24e"
    example_path = instance_space_path / "example.m"
    trial_path = instance_space_path / "trial"

    if not instance_space_path.exists():
        raise FileNotFoundError(
            f"No se encontro extern/InstanceSpace87fe24e en: {instance_space_path}"
        )

    if not example_path.exists():
        raise FileNotFoundError(
            f"No se encontro example.m en: {example_path}"
        )

    if not trial_path.exists():
        raise FileNotFoundError(
            f"No se encontro la carpeta trial en: {trial_path}"
        )

    matlab_instance_space_path = str(instance_space_path.resolve()).replace("\\", "/")

    print("=" * 80)
    print("INSTANCESPACE87FE24E EXAMPLE TESTER")
    print("=" * 80)
    print(f"[INFO] Repo root              : {repo_root}")
    print(f"[INFO] InstanceSpace path     : {instance_space_path}")
    print(f"[INFO] Example path           : {example_path}")
    print(f"[INFO] Trial path             : {trial_path}")
    print()

    print("[INFO] Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        print(f"[INFO] Cambiando directorio a: {matlab_instance_space_path}")
        eng.cd(matlab_instance_space_path, nargout=0)

        print("[INFO] Ejecutando example.m ...")
        eng.eval("example", nargout=0)

        print()
        print("=" * 80)
        print("EXAMPLE TERMINO CORRECTAMENTE")
        print("=" * 80)
        print(f"[INFO] Revisa los resultados en: {trial_path}")

    except Exception as e:
        print()
        print("=" * 80)
        print("ERROR AL EJECUTAR EL EXAMPLE DE INSTANCESPACE87FE24E")
        print("=" * 80)
        print(e)
        raise

    finally:
        eng.quit()
        print("[INFO] Motor de MATLAB cerrado.")


if __name__ == "__main__":
    main()