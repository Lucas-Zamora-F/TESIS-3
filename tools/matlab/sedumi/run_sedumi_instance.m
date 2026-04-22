function result = run_sedumi_instance(instance_path, varargin)
%RUN_SEDUMI_INSTANCE Solve a .dat-s or .mat instance with SeDuMi.
%
% - Reads with fromsdpa
% - Solves with sedumi
% - Manually computes pobj, dobj, gap, pinfeas, dinfeas, phi

    p = inputParser;
    addParameter(p, 'target_tol', 1e-6);
    addParameter(p, 'max_iterations', 2000);
    addParameter(p, 'time_limit_seconds', 3600);
    addParameter(p, 'verbose', 0);
    addParameter(p, 'bigeps', 1e-3);
    addParameter(p, 'stepdif', 2);
    addParameter(p, 'beta', 0.5);
    addParameter(p, 'theta', 0.25);
    addParameter(p, 'alg', 2);
    addParameter(p, 'log_path', '');
    parse(p, varargin{:});

    opts = p.Results;

    result = struct();
    result.status = 'FAILED';
    result.obj_val = NaN;
    result.runtime = NaN;
    result.gap = NaN;
    result.pinfeas = NaN;
    result.dinfeas = NaN;
    result.iterations = 0;
    result.phi = NaN;
    result.is_optimal = 0;
    result.pobj = NaN;
    result.dobj = NaN;
    result.numerr = NaN;
    result.pinf = NaN;
    result.dinf = NaN;
    result.feasratio = NaN;

    t_start = tic;

    try
        if ~isempty(opts.log_path)
            diary(opts.log_path);
        end

        [~, ~, ext] = fileparts(instance_path);
        if strcmpi(ext, '.mat')
            data = load(instance_path);

            if isfield(data, 'At')
                At = data.At;
            elseif isfield(data, 'A')
                A = data.A;
                if size(A, 1) == length(data.b)
                    At = A';
                else
                    At = A;
                end
            else
                error('MAT file must contain A or At.');
            end

            if isfield(data, 'c')
                c = data.c;
            elseif isfield(data, 'C')
                c = data.C;
            else
                error('MAT file must contain c or C.');
            end

            b = data.b;
            K = data.K;

            if size(b, 1) == 1
                b = b';
            end
            if size(c, 1) == 1
                c = c';
            end
            if numel(c) == 1 && size(At, 1) > 1
                c = c * ones(size(At, 1), 1);
            end
        else
            [At, b, c, K] = fromsdpa(instance_path);
        end

        pars = struct();
        pars.eps = opts.target_tol;
        pars.bigeps = opts.bigeps;
        pars.maxiter = opts.max_iterations;
        pars.stepdif = opts.stepdif;
        pars.beta = opts.beta;
        pars.theta = opts.theta;
        pars.alg = opts.alg;

        if opts.verbose == 0
            pars.fid = 0;
        else
            pars.fid = 1;
        end

        [x, y, info] = sedumi(At, b, c, K, pars);
        t_elapsed = toc(t_start);

        % Primal and dual objectives
        pobj = full(c' * x);
        dobj = full(b' * y);

        % Homogeneous relative gap
        gap = abs(pobj - dobj) / (1 + abs(pobj) + abs(dobj));

        % Primal residual: A*x - b, where At = A'
        pinfeas = norm(At' * x - b) / (1 + norm(b));

        % Dual slack: s = c - A'*y, where At = A'
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
        elseif isfield(info, 'numiter')
            iterations = info.numiter;
        else
            iterations = NaN;
        end

        if t_elapsed > opts.time_limit_seconds
            status = 'TIME_LIMIT';
        elseif phi <= opts.target_tol
            status = 'OPTIMAL';
        else
            status = 'STOPPED';
        end

        result.status = status;
        result.obj_val = pobj;
        result.runtime = t_elapsed;
        result.gap = gap;
        result.pinfeas = pinfeas;
        result.dinfeas = dinfeas;
        result.iterations = iterations;
        result.phi = phi;
        result.is_optimal = double(phi <= opts.target_tol);
        result.pobj = pobj;
        result.dobj = dobj;
        result.numerr = numerr;
        result.pinf = pinf_flag;
        result.dinf = dinf_flag;
        result.feasratio = feasratio;

    catch ME
        result.status = 'FAILED';
        result.runtime = toc(t_start);
        fprintf(2, 'Error in run_sedumi_instance: %s\n', ME.message);
    end

    if ~isempty(opts.log_path)
        diary off;
    end
end
