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
    Ejecuta SeDuMi sobre instancias .dat-s.

    Criterio interno del solver:
        pars.eps = target_tol

    Criterio externo homogéneo:
        phi = max(gap, pinfeas, dinfeas) <= target_tol
    """
    settings = load_settings("sedumi", config_path)

    target_tol = settings["tolerance_gap"]
    max_iterations = settings["max_iterations"]
    verbose = settings["verbose"]

    # Opciones específicas de SeDuMi
    bigeps = settings.get("bigeps", 1e-3)
    stepdif = settings.get("stepdif", 2)
    beta = settings.get("beta", 0.5)
    theta = settings.get("theta", 0.25)
    alg = settings.get("alg", 2)

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
        sedumi_path = os.path.abspath(os.path.join(project_root, "extern", "sedumi"))

        print(f"wrapper_dir = {wrapper_dir}")
        print(f"project_root = {project_root}")
        print(f"sedumi_path = {sedumi_path}")

        if os.path.exists(sedumi_path):
            eng.addpath(eng.genpath(sedumi_path), nargout=0)
        else:
            raise RuntimeError(f"SeDuMi no encontrado en: {sedumi_path}")

        results = []

        for file_name in files_to_run:
            full_path = os.path.abspath(
                os.path.join(instance_folder, file_name)
            ).replace("\\", "/")

            print(f"Resolviendo instancia: {file_name}")

            matlab_cmd = f"""
            try
                clear res;
                [At, b, c, K] = fromsdpa('{full_path}');

                pars = struct();
                pars.eps = {target_tol};
                pars.bigeps = {bigeps};
                pars.maxiter = {max_iterations};
                pars.stepdif = {stepdif};
                pars.beta = {beta};
                pars.theta = {theta};
                pars.alg = {alg};

                if {verbose} == 0
                    pars.fid = 0;
                else
                    pars.fid = 1;
                end

                t_start = tic;
                [x, y, info] = sedumi(At, b, c, K, pars);
                t_elapsed = toc(t_start);

                % Objetivos primal y dual
                pobj = full(c' * x);
                dobj = full(b' * y);

                % Gap relativo homogéneo
                gap = abs(pobj - dobj) / (1 + abs(pobj) + abs(dobj));

                % Residuo primal: A*x - b, pero At = A'
                pinfeas = norm(At' * x - b) / (1 + norm(b));

                % Slack dual: s = c - A'*y, pero At = A'
                s = c - At * y;
                lam = eigK(s, K);

                if isempty(lam)
                    cone_violation = 0;
                else
                    cone_violation = max(0, -min(real(lam)));
                end

                dinfeas = cone_violation / (1 + norm(c));

                phi = max([gap, pinfeas, dinfeas]);

                if isfield(info, 'numerr')
                    numerr = info.numerr;
                else
                    numerr = NaN;
                end

                if isfield(info, 'pinf')
                    pinf_flag = info.pinf;
                else
                    pinf_flag = NaN;
                end

                if isfield(info, 'dinf')
                    dinf_flag = info.dinf;
                else
                    dinf_flag = NaN;
                end

                if isfield(info, 'feasratio')
                    feasratio = info.feasratio;
                else
                    feasratio = NaN;
                end

                if isfield(info, 'iter')
                    iterations = info.iter;
                else
                    iterations = NaN;
                end

                if phi <= {target_tol}
                    status_code = 0;
                elseif pinf_flag == 1
                    status_code = 1;
                elseif dinf_flag == 1
                    status_code = 2;
                elseif numerr == 1
                    status_code = 3;
                elseif numerr == 2
                    status_code = 4;
                else
                    status_code = 5;
                end

                res.status = status_code;
                res.obj_val = pobj;
                res.runtime = t_elapsed;
                res.gap = gap;
                res.pinfeas = pinfeas;
                res.dinfeas = dinfeas;
                res.iterations = iterations;
                res.phi = phi;
                res.is_optimal = double(phi <= {target_tol});

                % Diagnóstico nativo SeDuMi
                res.pobj = pobj;
                res.dobj = dobj;
                res.numerr = numerr;
                res.pinf_flag = pinf_flag;
                res.dinf_flag = dinf_flag;
                res.feasratio = feasratio;

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
                res.pobj = NaN;
                res.dobj = NaN;
                res.numerr = NaN;
                res.pinf_flag = NaN;
                res.dinf_flag = NaN;
                res.feasratio = NaN;
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
                    "pobj": res["pobj"],
                    "dobj": res["dobj"],
                    "numerr": res["numerr"],
                    "pinf_flag": res["pinf_flag"],
                    "dinf_flag": res["dinf_flag"],
                    "feasratio": res["feasratio"],
                }
            )

        return results

    finally:
        eng.quit()