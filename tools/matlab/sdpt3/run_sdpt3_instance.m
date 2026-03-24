function result = run_sdpt3_instance(instance_path, varargin)
%RUN_SDPT3_INSTANCE Ejecuta una instancia .dat-s con SDPT3 y devuelve struct.
%
% result fields esperados:
%   status, obj_val, gap, pinfeas, dinfeas, runtime, iterations,
%   numerr, pinf, dinf, feasratio

    p = inputParser;
    addParameter(p, 'target_tol', 1e-6);
    addParameter(p, 'max_iterations', 2000);
    addParameter(p, 'time_limit_seconds', 3600);
    addParameter(p, 'verbose', 0);
    addParameter(p, 'steptol', 1e-8);
    addParameter(p, 'gam', 0);
    addParameter(p, 'log_path', '');
    parse(p, varargin{:});

    opts = p.Results;

    result = struct();
    result.status = 'FAILED';
    result.obj_val = NaN;
    result.gap = NaN;
    result.pinfeas = NaN;
    result.dinfeas = NaN;
    result.runtime = NaN;
    result.iterations = 0;
    result.numerr = 0;
    result.pinf = NaN;
    result.dinf = NaN;
    result.feasratio = NaN;

    t0 = tic;

    try
        if ~isempty(opts.log_path)
            diary(opts.log_path);
        end

        if opts.verbose > 0
            fprintf('Leyendo instancia: %s\n', instance_path);
        end

        % Ajusta esto si tu repo usa read_sdpa / fromsdpa / otro lector.
        [blk, At, C, b] = read_sdpa(instance_path);

        OPTIONS = sqlparameters;
        OPTIONS.maxit = opts.max_iterations;
        OPTIONS.steptol = opts.steptol;
        OPTIONS.gam = opts.gam;
        OPTIONS.printlevel = opts.verbose;

        [obj, X, y, Z, info, runhist] = sqlp(blk, At, C, b, OPTIONS);

        runtime = toc(t0);

        obj_val = NaN;
        if ~isempty(obj)
            obj_val = obj(1);
        end

        gap = NaN;
        pinfeas = NaN;
        dinfeas = NaN;
        iterations = 0;
        numerr = 0;
        pinf = NaN;
        dinf = NaN;
        feasratio = NaN;

        if exist('runhist', 'var') && ~isempty(runhist)
            if isfield(runhist, 'gap')
                gap = runhist.gap(end);
            end
            if isfield(runhist, 'pinfeas')
                pinfeas = runhist.pinfeas(end);
            end
            if isfield(runhist, 'dinfeas')
                dinfeas = runhist.dinfeas(end);
            end
            if isfield(runhist, 'pinf')
                pinf = runhist.pinf(end);
            end
            if isfield(runhist, 'dinf')
                dinf = runhist.dinf(end);
            end
            if isfield(runhist, 'feasratio')
                feasratio = runhist.feasratio(end);
            end
            if isfield(runhist, 'iter')
                iterations = runhist.iter;
            elseif isfield(runhist, 'iters')
                iterations = runhist.iters;
            end
        end

        if exist('info', 'var') && ~isempty(info)
            if isfield(info, 'termcode')
                numerr = info.termcode;
            elseif isfield(info, 'numerr')
                numerr = info.numerr;
            end
        end

        phi = max([gap, pinfeas, dinfeas]);

        if isfinite(phi) && phi <= opts.target_tol
            status = 'OPTIMAL';
        else
            status = 'STOPPED';
        end

        if runtime > opts.time_limit_seconds
            status = 'TIME_LIMIT';
        end

        result.status = status;
        result.obj_val = obj_val;
        result.gap = gap;
        result.pinfeas = pinfeas;
        result.dinfeas = dinfeas;
        result.runtime = runtime;
        result.iterations = iterations;
        result.numerr = numerr;
        result.pinf = pinf;
        result.dinf = dinf;
        result.feasratio = feasratio;

    catch ME
        runtime = toc(t0);
        result.status = 'FAILED';
        result.runtime = runtime;
        fprintf(2, 'Error en run_sdpt3_instance: %s\n', ME.message);
    end

    if ~isempty(opts.log_path)
        diary off;
    end
end