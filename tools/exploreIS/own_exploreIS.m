function out = own_exploreIS(rootdir)
% =========================================================================================
% OWN EXPLOREIS
% =========================================================================================
% A custom exploration routine that is intentionally more tolerant than the official
% InstanceSpace exploreIS.m.
%
% Expected inside rootdir:
%   - model.mat
%   - metadata_test.csv   (preferred)
%   - metadata.csv        (fallback)
%
% Outputs:
%   - projected_instances.csv
%   - feature_alignment.csv
%   - projection_summary.txt
%   - projection_scatter.png
%   - projection_by_source.png          (if source column exists)
%   - projection_by_best_algorithm.png  (if algo_* columns exist)
%
% This script does NOT assume the exact internal contract of the official exploreIS.m.
% Instead, it:
%   1) loads model.mat
%   2) loads test metadata
%   3) aligns features by name
%   4) tries to obtain a 2D projection from the model
%   5) falls back to PCA if needed
%
% =========================================================================================

    start_time = tic;

    fprintf('=================================================================================\n');
    fprintf('OWN EXPLOREIS\n');
    fprintf('=================================================================================\n');
    fprintf('[INFO] Root directory: %s\n', rootdir);

    if ~isfolder(rootdir)
        error('The provided rootdir does not exist: %s', rootdir);
    end

    model_file = fullfile(rootdir, 'model.mat');
    metadata_test_file = fullfile(rootdir, 'metadata_test.csv');
    metadata_train_file = fullfile(rootdir, 'metadata.csv');

    if ~isfile(model_file)
        error('model.mat not found in: %s', rootdir);
    end

    if isfile(metadata_test_file)
        metadata_file = metadata_test_file;
        fprintf('[INFO] Using metadata file: metadata_test.csv\n');
    elseif isfile(metadata_train_file)
        metadata_file = metadata_train_file;
        fprintf('[WARN] metadata_test.csv not found. Falling back to metadata.csv\n');
    else
        error('Neither metadata_test.csv nor metadata.csv exists in: %s', rootdir);
    end

    fprintf('[INFO] Loading model.mat...\n');
    loaded = load(model_file);
    model = i_extract_model_struct(loaded);

    fprintf('[INFO] Loading metadata table...\n');
    T = readtable(metadata_file);

    varnames = T.Properties.VariableNames;
    is_instance = strcmpi(varnames, 'instances');
    is_source   = strcmpi(varnames, 'source');
    is_feature  = startsWith(lower(varnames), 'feature_');
    is_algo     = startsWith(lower(varnames), 'algo_');

    if ~any(is_instance)
        error('The metadata file must contain an ''instances'' column.');
    end

    instance_labels = T{:, is_instance};
    if isnumeric(instance_labels)
        instance_labels = cellstr(string(instance_labels));
    elseif isstring(instance_labels)
        instance_labels = cellstr(instance_labels);
    elseif iscell(instance_labels)
        instance_labels = cellfun(@char, instance_labels, 'UniformOutput', false);
    end

    if any(is_source)
        source_values = T{:, is_source};
        if ~iscategorical(source_values)
            source_values = categorical(source_values);
        end
    else
        source_values = [];
    end

    X_table = T(:, is_feature);
    X_raw = table2array(X_table);

    if any(is_algo)
        Y_table = T(:, is_algo);
        Y_raw = table2array(Y_table);
        algo_varnames = Y_table.Properties.VariableNames;
    else
        Y_raw = [];
        algo_varnames = {};
    end

    fprintf('[INFO] Instances loaded: %d\n', size(X_raw, 1));
    fprintf('[INFO] Feature columns found: %d\n', size(X_raw, 2));
    fprintf('[INFO] Algorithm columns found: %d\n', size(Y_raw, 2));

    model_feature_labels = i_get_model_feature_labels(model);
    model_algo_labels = i_get_model_algo_labels(model);

    [X_aligned, alignment_table, aligned_feature_names] = i_align_features(X_table, model_feature_labels);

    fprintf('[INFO] Aligned features used for projection: %d\n', size(X_aligned, 2));

    [X_clean, fill_values] = i_fill_missing_by_column_median(X_aligned);

    [Z, projection_method, projection_details] = i_project_to_2d(model, X_clean);

    best_algo = [];
    best_algo_name = [];

    if ~isempty(Y_raw)
        [best_algo, best_algo_name] = i_compute_best_algorithm(Y_raw, algo_varnames);
    end

    out = struct();
    out.rootdir = rootdir;
    out.model_file = model_file;
    out.metadata_file = metadata_file;
    out.instances = instance_labels;
    out.source = source_values;
    out.X_raw = X_raw;
    out.X_aligned = X_aligned;
    out.X_clean = X_clean;
    out.fill_values = fill_values;
    out.alignment = alignment_table;
    out.aligned_feature_names = aligned_feature_names;
    out.Y_raw = Y_raw;
    out.best_algo = best_algo;
    out.best_algo_name = best_algo_name;
    out.model_feature_labels = model_feature_labels;
    out.model_algo_labels = model_algo_labels;
    out.Z = Z;
    out.projection_method = projection_method;
    out.projection_details = projection_details;

    fprintf('[INFO] Writing outputs...\n');
    i_write_outputs(rootdir, out);

    fprintf('[OK] own_exploreIS finished successfully in %.2f seconds.\n', toc(start_time));
end

% =========================================================================================
% HELPERS
% =========================================================================================

function model = i_extract_model_struct(loaded)
    if isstruct(loaded) && isscalar(loaded)
        loaded_fields = fieldnames(loaded);

        if numel(loaded_fields) == 1 && isstruct(loaded.(loaded_fields{1}))
            model = loaded.(loaded_fields{1});
            return;
        end

        model = loaded;
    else
        error('Unexpected content in model.mat.');
    end
end

function labels = i_get_model_feature_labels(model)
    labels = {};

    if isfield(model, 'data') && isfield(model.data, 'featlabels')
        labels = model.data.featlabels;
    elseif isfield(model, 'featlabels')
        labels = model.featlabels;
    elseif isfield(model, 'feature_labels')
        labels = model.feature_labels;
    end

    labels = i_normalize_label_cell(labels, 'feature_');
end

function labels = i_get_model_algo_labels(model)
    labels = {};

    if isfield(model, 'data') && isfield(model.data, 'algolabels')
        labels = model.data.algolabels;
    elseif isfield(model, 'algolabels')
        labels = model.algolabels;
    elseif isfield(model, 'algo_labels')
        labels = model.algo_labels;
    end

    labels = i_normalize_label_cell(labels, 'algo_');
end

function labels = i_normalize_label_cell(labels, required_prefix)
    if isempty(labels)
        labels = {};
        return;
    end

    if isstring(labels)
        labels = cellstr(labels);
    elseif ischar(labels)
        labels = {labels};
    end

    labels = labels(:)';
    for i = 1:numel(labels)
        labels{i} = char(string(labels{i}));
        if ~startsWith(lower(labels{i}), lower(required_prefix))
            labels{i} = [required_prefix labels{i}];
        end
    end
end

function [X_aligned, alignment_table, aligned_feature_names] = i_align_features(X_table, model_feature_labels)
    input_feature_names = X_table.Properties.VariableNames;
    n_instances = height(X_table);

    if isempty(model_feature_labels)
        % If the model does not expose feature labels, use all input features as-is.
        X_aligned = table2array(X_table);
        aligned_feature_names = input_feature_names(:);

        alignment_table = table( ...
            aligned_feature_names, ...
            aligned_feature_names, ...
            repmat("used_as_input_order", numel(aligned_feature_names), 1), ...
            'VariableNames', {'model_feature', 'input_feature', 'status'} ...
        );
        return;
    end

    model_feature_labels = model_feature_labels(:);
    n_model_features = numel(model_feature_labels);

    X_aligned = NaN(n_instances, n_model_features);
    input_feature_names_lower = lower(string(input_feature_names));

    matched_input = strings(n_model_features, 1);
    status = strings(n_model_features, 1);

    for i = 1:n_model_features
        target = string(model_feature_labels{i});
        idx = find(input_feature_names_lower == lower(target), 1);

        if ~isempty(idx)
            X_aligned(:, i) = X_table{:, idx};
            matched_input(i) = string(input_feature_names{idx});
            status(i) = "matched";
        else
            matched_input(i) = "";
            status(i) = "missing_in_input";
        end
    end

    aligned_feature_names = cellstr(model_feature_labels);

    alignment_table = table( ...
        string(model_feature_labels), ...
        matched_input, ...
        status, ...
        'VariableNames', {'model_feature', 'input_feature', 'status'} ...
    );
end

function [X_filled, fill_values] = i_fill_missing_by_column_median(X)
    X_filled = X;
    n_cols = size(X, 2);
    fill_values = NaN(1, n_cols);

    for j = 1:n_cols
        col = X(:, j);
        valid = col(~isnan(col));

        if isempty(valid)
            fill_val = 0;
        else
            fill_val = median(valid);
        end

        col(isnan(col)) = fill_val;
        X_filled(:, j) = col;
        fill_values(j) = fill_val;
    end
end

function [Z, method, details] = i_project_to_2d(model, X)
    Z = [];
    method = "";
    details = struct();

    % Option 1: explicit projection matrix in pilot.A
    if isfield(model, 'pilot') && isfield(model.pilot, 'A')
        A = model.pilot.A;
        if isnumeric(A) && size(A, 1) == size(X, 2)
            if size(A, 2) >= 2
                Z = X * A(:, 1:2);
                method = "model.pilot.A";
                details.matrix_size = size(A);
                return;
            end
        end
    end

    % Option 2: generic A at top level
    if isfield(model, 'A')
        A = model.A;
        if isnumeric(A) && size(A, 1) == size(X, 2)
            if size(A, 2) >= 2
                Z = X * A(:, 1:2);
                method = "model.A";
                details.matrix_size = size(A);
                return;
            end
        end
    end

    % Option 3: coeff from PCA-like object
    if isfield(model, 'pca') && isfield(model.pca, 'coeff')
        coeff = model.pca.coeff;
        if isnumeric(coeff) && size(coeff, 1) == size(X, 2) && size(coeff, 2) >= 2
            Z = X * coeff(:, 1:2);
            method = "model.pca.coeff";
            details.matrix_size = size(coeff);
            return;
        end
    end

    % Option 4: fallback PCA from current data
    [coeff, score] = pca(X, 'Algorithm', 'svd');
    if size(score, 2) >= 2
        Z = score(:, 1:2);
    elseif size(score, 2) == 1
        Z = [score(:, 1), zeros(size(score, 1), 1)];
    else
        Z = zeros(size(X, 1), 2);
    end

    method = "fallback_pca";
    details.matrix_size = size(coeff);
end

function [best_idx, best_name] = i_compute_best_algorithm(Y, algo_varnames)
    % Assumes algo_* = cost / runtime => lower is better.
    [~, best_idx] = min(Y, [], 2, 'omitnan');
    best_name = strings(size(best_idx));

    for i = 1:numel(best_idx)
        idx = best_idx(i);
        if isnan(idx) || idx < 1 || idx > numel(algo_varnames)
            best_name(i) = "unknown";
        else
            best_name(i) = string(algo_varnames{idx});
        end
    end
end

function i_write_outputs(rootdir, out)
    projected_table = table();
    projected_table.instances = string(out.instances(:));
    projected_table.z1 = out.Z(:, 1);
    projected_table.z2 = out.Z(:, 2);

    if ~isempty(out.source)
        projected_table.source = string(out.source(:));
    end

    if ~isempty(out.best_algo_name)
        projected_table.best_algorithm = out.best_algo_name(:);
    end

    writetable(projected_table, fullfile(rootdir, 'projected_instances.csv'));
    writetable(out.alignment, fullfile(rootdir, 'feature_alignment.csv'));

    summary_path = fullfile(rootdir, 'projection_summary.txt');
    fid = fopen(summary_path, 'w');
    fprintf(fid, 'OWN EXPLOREIS SUMMARY\n');
    fprintf(fid, '=====================\n');
    fprintf(fid, 'Projection method: %s\n', out.projection_method);
    fprintf(fid, 'Instances: %d\n', numel(out.instances));
    fprintf(fid, 'Input features: %d\n', size(out.X_raw, 2));
    fprintf(fid, 'Aligned features: %d\n', size(out.X_aligned, 2));
    fprintf(fid, 'Algorithms: %d\n', size(out.Y_raw, 2));
    fclose(fid);

    i_plot_basic_projection(rootdir, out);
    i_plot_by_source(rootdir, out);
    i_plot_by_best_algorithm(rootdir, out);
end

function i_plot_basic_projection(rootdir, out)
    fig = figure('Visible', 'off');
    scatter(out.Z(:,1), out.Z(:,2), 36, 'filled');
    xlabel('z1');
    ylabel('z2');
    title(sprintf('Projection (%s)', out.projection_method), 'Interpreter', 'none');
    grid on;
    saveas(fig, fullfile(rootdir, 'projection_scatter.png'));
    close(fig);
end

function i_plot_by_source(rootdir, out)
    if isempty(out.source)
        return;
    end

    fig = figure('Visible', 'off');
    gscatter(out.Z(:,1), out.Z(:,2), out.source);
    xlabel('z1');
    ylabel('z2');
    title('Projection by source', 'Interpreter', 'none');
    grid on;
    saveas(fig, fullfile(rootdir, 'projection_by_source.png'));
    close(fig);
end

function i_plot_by_best_algorithm(rootdir, out)
    if isempty(out.best_algo_name)
        return;
    end

    fig = figure('Visible', 'off');
    gscatter(out.Z(:,1), out.Z(:,2), categorical(out.best_algo_name));
    xlabel('z1');
    ylabel('z2');
    title('Projection by best algorithm', 'Interpreter', 'none');
    grid on;
    saveas(fig, fullfile(rootdir, 'projection_by_best_algorithm.png'));
    close(fig);
end