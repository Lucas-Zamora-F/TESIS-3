import json
import os
import matlab.engine


def load_settings(solver_name, config_path):
    """
    Carga la configuración global y la combina con la específica del solver.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"No se encontró el archivo de configuración en: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    settings = data["global_settings"].copy()

    if solver_name in data.get("solvers", {}):
        settings.update(data["solvers"][solver_name])

    return settings


def run_benchmark(instance_folder, config_path, filter_list=None):
    """
    Ejecuta SDPT3 sobre instancias .dat-s.

    Criterio interno de parada del solver:
        options.gaptol = target_tol

    Criterio externo homogéneo para declarar "óptimo":
        phi = max(relgap, pinfeas, dinfeas) <= target_tol
    """
    settings = load_settings("sdpt3", config_path)
    target_tol = settings["tolerance_gap"]
    max_iterations = settings["max_iterations"]
    verbose = settings["verbose"]
    steptol = settings.get("steptol", 1e-8)
    gam = settings.get("gam", 0)

    if not os.path.isdir(instance_folder):
        raise NotADirectoryError(
            f"La carpeta de instancias no existe: {instance_folder}"
        )

    all_files = [f for f in os.listdir(instance_folder) if f.endswith(".dat-s")]
    files_to_run = [f for f in all_files if f in filter_list] if filter_list else all_files

    if not files_to_run:
        print("No se encontraron instancias para procesar.")
        return []

    print(f"Iniciando MATLAB engine para {len(files_to_run)} instancias.")
    eng = matlab.engine.start_matlab()

    try:
        wrapper_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(wrapper_dir, "..", ".."))
        sdpt3_path = os.path.abspath(os.path.join(project_root, "extern", "sdpt3"))

        print(f"wrapper_dir = {wrapper_dir}")
        print(f"project_root = {project_root}")
        print(f"sdpt3_path = {sdpt3_path}")

        if os.path.exists(sdpt3_path):
            eng.addpath(eng.genpath(sdpt3_path), nargout=0)
        else:
            raise RuntimeError(f"SDPT3 no encontrado en: {sdpt3_path}")

        results = []

        for file_name in files_to_run:
            full_path = os.path.abspath(
                os.path.join(instance_folder, file_name)
            ).replace("\\", "/")

            print(f"Resolviendo instancia: {file_name}")

            matlab_cmd = f"""
            try
                clear res;
                [blk, At, C, b] = read_sdpa('{full_path}');

                options = sqlparameters;

                % Criterio real de convergencia
                options.gaptol = {target_tol};

                % Protección numérica separada del criterio de optimalidad
                options.steptol = {steptol};

                % Configuración general del benchmark
                options.maxit = {max_iterations};
                options.printlevel = {verbose};
                options.gam = {gam};

                t_start = tic;
                [obj, X, y, Z, iter_info] = sqlp(blk, At, C, b, options);
                t_elapsed = toc(t_start);

                phi = max([iter_info.relgap, iter_info.pinfeas, iter_info.dinfeas]);

                res.status = iter_info.termcode;
                res.obj_val = iter_info.obj(1);
                res.runtime = t_elapsed;
                res.gap = iter_info.relgap;
                res.pinfeas = iter_info.pinfeas;
                res.dinfeas = iter_info.dinfeas;
                res.iterations = iter_info.iter;
                res.phi = phi;
                res.is_optimal = double(phi <= {target_tol});

            catch ME
                res.status = -1;
                res.obj_val = NaN;
                res.runtime = 0;
                res.gap = NaN;
                res.pinfeas = NaN;
                res.dinfeas = NaN;
                res.iterations = 0;
                res.phi = NaN;
                res.is_optimal = 0;
                fprintf('Error en %s: %s\\n', '{file_name}', ME.message);
            end
            """

            eng.eval(matlab_cmd, nargout=0)
            res = eng.workspace["res"]

            results.append(
                {
                    "instance": file_name,
                    "status": res["status"],
                    "obj_val": res["obj_val"],
                    "runtime": res["runtime"],
                    "gap": res["gap"],
                    "pinfeas": res["pinfeas"],
                    "dinfeas": res["dinfeas"],
                    "iterations": res["iterations"],
                    "phi": res["phi"],
                    "is_optimal": res["is_optimal"],
                }
            )

        return results

    finally:
        eng.quit()