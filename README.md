# TESIS-3

Framework modular para ejecutar, evaluar y comparar solvers de **programación semidefinida (SDP)** sobre instancias estándar, con un flujo coordinado desde Python y soporte para integración con MATLAB.

---

## 1. Objetivo del repositorio

Este proyecto busca construir una base de experimentación ordenada para benchmarking de solvers SDP. La idea principal es que cada solver pueda ejecutarse bajo una interfaz homogénea, de modo que:

- todas las instancias se resuelvan desde una misma estructura de proyecto,
- la configuración esté centralizada,
- los resultados finales queden normalizados,
- y la ejecución sea reproducible y trazable.

---

## 2. Estructura actual del repositorio

```
TESIS-3/
├── config/
│   └── solver_config.json
│
├── data/
│   └── instances/
│       └── sdplib/
│
├── extern/
│   ├── InstanceSpace/
│   ├── sdpt3/
│   └── sedumi/
│
├── tools/
│   ├── installation/
│   ├── logging/
│   ├── matlab/
│   ├── runners/
│   └── wrappers_v2/
│
├── requirements.txt
└── README.md
```

---

## 3. Descripción de cada componente

### 3.1 `config/`

Aquí se encuentra `solver_config.json`, que define:

- parámetros globales de ejecución,
- configuración específica por solver,
- separación entre ajustes comunes y ajustes particulares.

Actualmente incluye:

- `global_settings`
  - `tolerance_gap`
  - `max_iterations`
  - `time_limit_seconds`
  - `verbose`

- `solvers.sdpt3`
- `solvers.sedumi`

Esta organización permite modificar el comportamiento del framework sin alterar directamente el código de los wrappers.

---

### 3.2 `data/instances/sdplib/`

Contiene las instancias SDP en formato `.dat-s`, utilizadas como input para todos los solvers.

---

### 3.3 `extern/`

Agrupa dependencias externas necesarias para ejecutar los solvers.

Repositorios utilizados:

- InstanceSpace
- SeDuMi
- SDPT3

Para agregar estos submódulos:

```bash
git submodule add https://github.com/andremun/InstanceSpace extern/InstanceSpace
git submodule add https://github.com/sqlp/sedumi extern/sedumi
git submodule add https://github.com/sqlp/sdpt3 extern/sdpt3
```

---

### 3.4 `tools/`

Contiene la lógica principal del framework.

#### `wrappers_v2/`

Implementa los wrappers de cada solver. Cada wrapper se encarga de:

1. cargar la configuración,
2. preparar el entorno,
3. ejecutar el solver,
4. capturar la salida,
5. normalizar los resultados.

#### `runners/`

Encapsula mecanismos de ejecución, como la integración con MATLAB.

#### `logging/`

Contiene el sistema de logging unificado para registrar ejecuciones.

#### `installation/`

Scripts auxiliares para configurar el entorno.

#### `matlab/`

Componentes asociados a la integración con MATLAB.

---

## 4. Flujo general de ejecución

_Pendiente de implementación._

---

## 5. Resultado estándar esperado

_Pendiente de definición._

---

## 6. Dependencias

El proyecto depende de:

- Python
- pandas
- MATLAB Engine para Python
- Toolboxes de MATLAB (según solver)

---

## 7. Cómo ejecutar

_Pendiente de implementación._

---

## 8. Estado actual del proyecto

El repositorio actualmente cuenta con:

- configuración centralizada,
- instancias organizadas,
- dependencias externas separadas,
- wrappers para SDPT3 y SeDuMi,
- sistema de logging,
- soporte para ejecución mediante runners.

---

## 9. Features

Esta sección documenta los scripts de extracción de features diseñados para caracterizar instancias SDP en formato `.dat-s`. La idea general es que cada script calcule una familia específica de atributos del problema y retorne un diccionario con una entrada por feature, de modo que luego un orquestador pueda construir un `pandas.DataFrame` con:

- una fila por instancia,
- una columna `Instance` con el nombre del archivo,
- y una columna por cada feature calculada.

Las features se organizan por tipo para separar claramente:

- tamaño del problema,
- estructura por bloques,
- patrón de sparsity,
- y escalamiento numérico.

---

### 9.1 `tools/features/size_features.py`

Script encargado de extraer **features de tamaño básico** desde el header de la instancia `.dat-s`.

Estas features describen cuán grande es el problema y cómo se reparte su tamaño entre los bloques declarados en la estructura SDPA.

#### Features que retorna

##### `feature_m`
- **Qué es:** número de restricciones del problema.
- **En simple:** cuántas ecuaciones o restricciones lineales tiene la instancia.
- **Cómo se calcula:** leyendo la primera línea relevante del archivo `.dat-s`.

##### `feature_n_blocks`
- **Qué es:** número total de bloques declarados.
- **En simple:** cuántas partes separadas tiene la variable matricial del problema.
- **Cómo se calcula:** leyendo la segunda línea relevante del archivo.

##### `feature_n_total_matrix`
- **Qué es:** tamaño total agregado de la estructura matricial.
- **En simple:** suma de los tamaños absolutos de todos los bloques.
- **Cómo se calcula:** sumando `abs(block_size)` para cada bloque.

##### `feature_max_block_size`
- **Qué es:** tamaño del bloque más grande.
- **En simple:** el bloque dominante en tamaño dentro del problema.
- **Cómo se calcula:** máximo de los tamaños absolutos de bloque.

##### `feature_min_block_size`
- **Qué es:** tamaño del bloque más pequeño.
- **En simple:** el bloque más chico dentro de la estructura.
- **Cómo se calcula:** mínimo de los tamaños absolutos de bloque.

##### `feature_mean_block_size`
- **Qué es:** promedio del tamaño de los bloques.
- **En simple:** tamaño medio de bloque.
- **Cómo se calcula:** promedio aritmético de los tamaños absolutos de bloque.

##### `feature_std_block_size`
- **Qué es:** desviación estándar del tamaño de los bloques.
- **En simple:** mide qué tan parecidos o distintos son los bloques entre sí en tamaño.
- **Cómo se calcula:** desviación estándar poblacional de los tamaños absolutos de bloque.

##### `feature_num_positive_blocks`
- **Qué es:** cantidad de bloques con tamaño positivo.
- **En simple:** número de bloques SDP propiamente tales.
- **Cómo se calcula:** contando los `block_size > 0`.

##### `feature_num_negative_blocks`
- **Qué es:** cantidad de bloques con tamaño negativo.
- **En simple:** número de bloques diagonales o tipo LP-like bajo la convención SDPA.
- **Cómo se calcula:** contando los `block_size < 0`.

##### `feature_num_unit_blocks`
- **Qué es:** cantidad de bloques de tamaño absoluto 1.
- **En simple:** cuántos bloques singleton tiene la instancia.
- **Cómo se calcula:** contando los bloques tales que `abs(block_size) == 1`.

##### `feature_sum_positive_blocks`
- **Qué es:** suma de tamaños de los bloques positivos.
- **En simple:** tamaño total aportado por la parte SDP.
- **Cómo se calcula:** sumando todos los `block_size > 0`.

##### `feature_sum_negative_abs_blocks`
- **Qué es:** suma del valor absoluto de los bloques negativos.
- **En simple:** tamaño total aportado por los bloques diagonales/LP-like.
- **Cómo se calcula:** sumando `abs(block_size)` para cada bloque negativo.

##### `feature_aspect_ratio_m_over_n`
- **Qué es:** razón entre número de restricciones y tamaño total de la matriz.
- **En simple:** indica si el problema tiene relativamente muchas o pocas restricciones respecto a su tamaño matricial.
- **Cómo se calcula:** `m / n_total_matrix`.

##### `feature_aspect_ratio_m_over_nsq`
- **Qué es:** razón entre número de restricciones y tamaño cuadrático de la matriz.
- **En simple:** una medida más agresiva de densidad de restricciones respecto al espacio matricial potencial.
- **Cómo se calcula:** `m / (n_total_matrix ** 2)`.

##### `feature_block_sizes_raw`
- **Qué es:** representación textual de los tamaños de bloque originales.
- **En simple:** deja registrado el vector de bloques tal como fue leído.
- **Cómo se calcula:** concatenando los `block_size` parseados en una cadena separada por `;`.

---

### 9.2 `tools/features/structure_features.py`

Script encargado de extraer **features estructurales del problema** a partir de la organización por bloques del archivo `.dat-s`.

Estas features no miden tamaño puro, sino la forma en que ese tamaño está distribuido: si el problema está concentrado en un bloque grande, si tiene muchos bloques pequeños, si mezcla bloques SDP y bloques diagonales, etc.

#### Features que retorna

##### `feature_num_sdp_blocks`
- **Qué es:** cantidad de bloques SDP reales.
- **En simple:** cuántos bloques positivos tiene la estructura.
- **Cómo se calcula:** contando los bloques con tamaño positivo.

##### `feature_num_lp_like_blocks`
- **Qué es:** cantidad de bloques diagonales o LP-like.
- **En simple:** cuántos bloques negativos tiene la estructura.
- **Cómo se calcula:** contando los bloques con tamaño negativo.

##### `feature_is_single_block`
- **Qué es:** indicador binario de estructura mono-bloque.
- **En simple:** vale 1 si el problema tiene un solo bloque.
- **Cómo se calcula:** `1` si `n_blocks == 1`, en otro caso `0`.

##### `feature_is_multi_block`
- **Qué es:** indicador binario de estructura multi-bloque.
- **En simple:** vale 1 si el problema tiene más de un bloque.
- **Cómo se calcula:** `1` si `n_blocks > 1`, en otro caso `0`.

##### `feature_has_sdp_blocks`
- **Qué es:** indicador binario de presencia de bloques SDP.
- **En simple:** dice si existe al menos un bloque positivo.
- **Cómo se calcula:** `1` si `num_sdp_blocks > 0`, en otro caso `0`.

##### `feature_has_lp_blocks`
- **Qué es:** indicador binario de presencia de bloques LP-like.
- **En simple:** dice si existe al menos un bloque negativo.
- **Cómo se calcula:** `1` si `num_lp_like_blocks > 0`, en otro caso `0`.

##### `feature_is_pure_sdp`
- **Qué es:** indicador binario de problema puramente SDP.
- **En simple:** vale 1 si todos los bloques son positivos.
- **Cómo se calcula:** `1` si `num_sdp_blocks == n_blocks`, en otro caso `0`.

##### `feature_is_mixed_sdp_lp`
- **Qué es:** indicador binario de estructura mixta.
- **En simple:** vale 1 si el problema mezcla bloques SDP y bloques diagonales.
- **Cómo se calcula:** `1` si hay al menos un bloque positivo y al menos un bloque negativo.

##### `feature_sdp_total_size`
- **Qué es:** tamaño total de los bloques SDP.
- **En simple:** cuánto aporta la parte SDP al tamaño total.
- **Cómo se calcula:** sumando los bloques positivos.

##### `feature_lp_total_size`
- **Qué es:** tamaño total de los bloques LP-like.
- **En simple:** cuánto aporta la parte diagonal al tamaño total.
- **Cómo se calcula:** sumando el valor absoluto de los bloques negativos.

##### `feature_sdp_size_fraction`
- **Qué es:** fracción del tamaño total que corresponde a bloques SDP.
- **En simple:** qué porcentaje del problema pertenece a la parte SDP.
- **Cómo se calcula:** `sdp_total_size / n_total_matrix`.

##### `feature_lp_size_fraction`
- **Qué es:** fracción del tamaño total que corresponde a bloques LP-like.
- **En simple:** qué porcentaje del problema pertenece a la parte diagonal.
- **Cómo se calcula:** `lp_total_size / n_total_matrix`.

##### `feature_largest_block_fraction`
- **Qué es:** fracción del tamaño total concentrada en el bloque más grande.
- **En simple:** mide cuánto domina el bloque principal.
- **Cómo se calcula:** `max_block_size / n_total_matrix`.

##### `feature_smallest_block_fraction`
- **Qué es:** fracción del tamaño total concentrada en el bloque más pequeño.
- **En simple:** mide qué tan pequeño es el bloque mínimo respecto del total.
- **Cómo se calcula:** `min_block_size / n_total_matrix`.

##### `feature_nonlargest_fraction`
- **Qué es:** fracción del tamaño total que queda fuera del bloque más grande.
- **En simple:** cuánto del problema no está concentrado en el bloque dominante.
- **Cómo se calcula:** `1 - largest_block_fraction`.

##### `feature_block_dominance_ratio`
- **Qué es:** razón entre el mayor bloque y el tamaño promedio de bloque.
- **En simple:** mide si existe un bloque desproporcionadamente grande.
- **Cómo se calcula:** `max_block_size / mean_abs_block_size`.

##### `feature_block_size_entropy`
- **Qué es:** entropía de Shannon de la distribución relativa de tamaños de bloque.
- **En simple:** mide qué tan repartido está el tamaño entre los bloques.
- **Cómo se calcula:** usando las proporciones `size_i / sum(size_i)` y la fórmula `-sum(p_i log p_i)`.

##### `feature_block_size_range`
- **Qué es:** rango de tamaños de bloque.
- **En simple:** diferencia entre el mayor y el menor bloque.
- **Cómo se calcula:** `max_block_size - min_block_size`.

##### `feature_cv_block_size`
- **Qué es:** coeficiente de variación del tamaño de bloque.
- **En simple:** dispersión relativa de los tamaños de bloque.
- **Cómo se calcula:** `std(block_sizes_abs) / mean(block_sizes_abs)`.

##### `feature_num_singleton_blocks`
- **Qué es:** número de bloques de tamaño 1.
- **En simple:** cuántos bloques extremadamente pequeños hay.
- **Cómo se calcula:** contando los bloques con tamaño absoluto 1.

##### `feature_singleton_block_fraction`
- **Qué es:** fracción de bloques que son singleton.
- **En simple:** qué proporción de bloques tiene tamaño 1.
- **Cómo se calcula:** `num_singleton_blocks / n_blocks`.

##### `feature_num_large_blocks_ge_10`
- **Qué es:** cantidad de bloques con tamaño al menos 10.
- **En simple:** cuántos bloques ya pueden considerarse moderados o grandes.
- **Cómo se calcula:** contando los bloques con `abs(size) >= 10`.

##### `feature_num_large_blocks_ge_50`
- **Qué es:** cantidad de bloques con tamaño al menos 50.
- **En simple:** cuántos bloques son grandes de verdad dentro de la instancia.
- **Cómo se calcula:** contando los bloques con `abs(size) >= 50`.

##### `feature_large_blocks_ge_10_fraction`
- **Qué es:** fracción de bloques de tamaño al menos 10.
- **En simple:** porcentaje de bloques medianos o grandes.
- **Cómo se calcula:** `num_large_blocks_ge_10 / n_blocks`.

##### `feature_large_blocks_ge_50_fraction`
- **Qué es:** fracción de bloques de tamaño al menos 50.
- **En simple:** porcentaje de bloques grandes.
- **Cómo se calcula:** `num_large_blocks_ge_50 / n_blocks`.

---

### 9.3 `tools/features/sparsity_features.py`

Script encargado de extraer **features de sparsity** a partir del patrón de no ceros almacenado en el cuerpo sparse del `.dat-s`.

En formato SDPA, el archivo almacena típicamente solo la parte triangular superior de cada bloque simétrico, por lo que este script calcula tanto sparsity sobre lo almacenado como sobre la matriz simétrica completa implícita.

#### Features que retorna

##### `feature_upper_capacity_per_matrix`
- **Qué es:** capacidad máxima de posiciones almacenables en triangular superior por matriz.
- **En simple:** cuántos lugares podría ocupar una matriz si estuviera completamente llena bajo la representación del archivo.
- **Cómo se calcula:** sumando `k(k+1)/2` para bloques SDP positivos de tamaño `k`, y `|k|` para bloques diagonales negativos.

##### `feature_full_capacity_per_matrix`
- **Qué es:** capacidad máxima de posiciones en la matriz completa implícita.
- **En simple:** cuántas posiciones tendría la matriz reconstruida completa.
- **Cómo se calcula:** sumando `k^2` para bloques SDP positivos y `|k|` para bloques diagonales negativos.

##### `feature_total_possible_upper_all_ai`
- **Qué es:** capacidad upper total para todas las matrices `A_i`.
- **En simple:** número máximo de entradas que podrían aparecer en todas las restricciones juntas en formato almacenado.
- **Cómo se calcula:** `m * upper_capacity_per_matrix`.

##### `feature_total_possible_full_all_ai`
- **Qué es:** capacidad full total para todas las matrices `A_i`.
- **En simple:** número máximo de posiciones que tendrían todas las restricciones juntas en forma matricial completa.
- **Cómo se calcula:** `m * full_capacity_per_matrix`.

##### `feature_nnz_c_upper`
- **Qué es:** número de no ceros de `C` en la representación almacenada.
- **En simple:** cuántas entradas no nulas de la matriz objetivo aparecen en el archivo.
- **Cómo se calcula:** contando las entradas con `matrix_number = 0`.

##### `feature_density_c_upper`
- **Qué es:** densidad de `C` sobre la triangular superior almacenada.
- **En simple:** fracción de posiciones usadas por `C` respecto del máximo posible en el formato del archivo.
- **Cómo se calcula:** `nnz_c_upper / upper_capacity_per_matrix`.

##### `feature_nnz_c_full_implied`
- **Qué es:** número de no ceros de `C` en la matriz simétrica completa implícita.
- **En simple:** cuántos no ceros tendría `C` al reconstruirla como matriz completa.
- **Cómo se calcula:** contando 1 para diagonales y 2 para entradas fuera de diagonal almacenadas una sola vez.

##### `feature_density_c_full_implied`
- **Qué es:** densidad de `C` en la matriz completa implícita.
- **En simple:** qué tan llena está `C` al pensarla como matriz completa.
- **Cómo se calcula:** `nnz_c_full_implied / full_capacity_per_matrix`.

##### `feature_total_nnz_ai_upper`
- **Qué es:** total de no ceros almacenados en todas las matrices `A_i`.
- **En simple:** suma de no ceros de todas las restricciones en el archivo.
- **Cómo se calcula:** sumando los `nnz_upper` de cada `A_i`.

##### `feature_avg_nnz_ai_upper`
- **Qué es:** promedio de no ceros almacenados por restricción.
- **En simple:** cuán poblada está en promedio una matriz de restricción.
- **Cómo se calcula:** promedio de `nnz_upper(A_i)`.

##### `feature_max_nnz_ai_upper`
- **Qué es:** máximo número de no ceros almacenados entre las restricciones.
- **En simple:** la restricción más poblada.
- **Cómo se calcula:** máximo de `nnz_upper(A_i)`.

##### `feature_min_nnz_ai_upper`
- **Qué es:** mínimo número de no ceros almacenados entre las restricciones.
- **En simple:** la restricción más vacía.
- **Cómo se calcula:** mínimo de `nnz_upper(A_i)`.

##### `feature_std_nnz_ai_upper`
- **Qué es:** desviación estándar de no ceros por restricción.
- **En simple:** cuánta variabilidad hay entre restricciones en términos de sparsity.
- **Cómo se calcula:** desviación estándar poblacional de `nnz_upper(A_i)`.

##### `feature_avg_density_ai_upper`
- **Qué es:** densidad promedio upper de las `A_i`.
- **En simple:** porcentaje promedio de ocupación de las restricciones sobre su capacidad almacenada.
- **Cómo se calcula:** promedio de `nnz_upper(A_i) / upper_capacity_per_matrix`.

##### `feature_max_density_ai_upper`
- **Qué es:** máxima densidad upper entre las `A_i`.
- **En simple:** la restricción más densa.
- **Cómo se calcula:** máximo de `nnz_upper(A_i) / upper_capacity_per_matrix`.

##### `feature_min_density_ai_upper`
- **Qué es:** mínima densidad upper entre las `A_i`.
- **En simple:** la restricción más dispersa.
- **Cómo se calcula:** mínimo de `nnz_upper(A_i) / upper_capacity_per_matrix`.

##### `feature_std_density_ai_upper`
- **Qué es:** desviación estándar de la densidad upper de las `A_i`.
- **En simple:** variabilidad relativa de densidad entre restricciones.
- **Cómo se calcula:** desviación estándar poblacional de las densidades upper de cada `A_i`.

##### `feature_total_density_all_ai_upper`
- **Qué es:** densidad upper global de todas las restricciones juntas.
- **En simple:** ocupación total del conjunto de restricciones respecto del máximo posible.
- **Cómo se calcula:** `total_nnz_ai_upper / total_possible_upper_all_ai`.

##### `feature_total_nnz_ai_full_implied`
- **Qué es:** total de no ceros de las `A_i` en forma completa implícita.
- **En simple:** número total de no ceros si todas las restricciones se expandieran como matrices completas.
- **Cómo se calcula:** sumando 1 por diagonal y 2 por fuera de diagonal para cada `A_i`.

##### `feature_avg_nnz_ai_full_implied`
- **Qué es:** promedio de no ceros completos implícitos por restricción.
- **En simple:** tamaño efectivo promedio de las `A_i` vistas como matrices completas.
- **Cómo se calcula:** promedio de `nnz_full_implied(A_i)`.

##### `feature_avg_density_ai_full_implied`
- **Qué es:** densidad promedio completa implícita de las `A_i`.
- **En simple:** ocupación promedio de las restricciones al reconstruirlas como matrices completas.
- **Cómo se calcula:** promedio de `nnz_full_implied(A_i) / full_capacity_per_matrix`.

##### `feature_total_density_all_ai_full_implied`
- **Qué es:** densidad global completa implícita de las `A_i`.
- **En simple:** ocupación total de todas las restricciones como matrices completas.
- **Cómo se calcula:** `total_nnz_ai_full_implied / total_possible_full_all_ai`.

##### `feature_num_empty_ai`
- **Qué es:** cantidad de restricciones sin entradas no nulas.
- **En simple:** cuántas matrices `A_i` están completamente vacías en el archivo.
- **Cómo se calcula:** contando los `A_i` con `nnz_upper == 0`.

##### `feature_fraction_empty_ai`
- **Qué es:** fracción de restricciones vacías.
- **En simple:** porcentaje de matrices `A_i` sin no ceros.
- **Cómo se calcula:** `num_empty_ai / m`.

---

### 9.4 `tools/features/scaling_features.py`

Script encargado de extraer **features de escalamiento numérico** usando las magnitudes de los coeficientes en `C`, en las matrices `A_i` y en el vector `b`.

Estas features buscan capturar si el problema está bien o mal escalado, si hay grandes diferencias de magnitud entre restricciones, y si la matriz objetivo, las restricciones y el lado derecho viven o no en órdenes comparables.

#### Features que retorna

##### `feature_c_fro_norm_upper`
- **Qué es:** norma de Frobenius de `C` reconstruida como matriz simétrica completa.
- **En simple:** tamaño global de la matriz objetivo.
- **Cómo se calcula:** usando las entradas upper almacenadas, contando una vez la diagonal y dos veces los términos fuera de diagonal en la suma cuadrática.

##### `feature_c_max_abs_entry`
- **Qué es:** valor absoluto máximo en `C`.
- **En simple:** coeficiente más grande de la matriz objetivo.
- **Cómo se calcula:** máximo de `|C_ij|` sobre entradas no nulas almacenadas.

##### `feature_c_min_abs_nonzero_entry`
- **Qué es:** valor absoluto mínimo no nulo en `C`.
- **En simple:** coeficiente no nulo más pequeño de la matriz objetivo.
- **Cómo se calcula:** mínimo de `|C_ij|` considerando solo entradas no nulas.

##### `feature_c_dynamic_range`
- **Qué es:** rango dinámico interno de `C`.
- **En simple:** diferencia relativa entre el coeficiente más grande y el más pequeño no nulo.
- **Cómo se calcula:** `c_max_abs_entry / c_min_abs_nonzero_entry`.

##### `feature_avg_ai_fro_norm_upper`
- **Qué es:** promedio de la norma de Frobenius de las `A_i`.
- **En simple:** tamaño promedio de una restricción.
- **Cómo se calcula:** promedio de las normas de Frobenius completas implícitas de cada `A_i`.

##### `feature_max_ai_fro_norm_upper`
- **Qué es:** máxima norma de Frobenius entre las `A_i`.
- **En simple:** la restricción de mayor magnitud global.
- **Cómo se calcula:** máximo de las normas de Frobenius de las `A_i`.

##### `feature_min_ai_fro_norm_upper`
- **Qué es:** mínima norma de Frobenius entre las `A_i`.
- **En simple:** la restricción más pequeña en escala.
- **Cómo se calcula:** mínimo de las normas de Frobenius de las `A_i`.

##### `feature_std_ai_fro_norm_upper`
- **Qué es:** desviación estándar de las normas de Frobenius de las `A_i`.
- **En simple:** cuánta dispersión hay entre restricciones en términos de escala global.
- **Cómo se calcula:** desviación estándar poblacional de las normas de Frobenius de las `A_i`.

##### `feature_ai_fro_norm_cv`
- **Qué es:** coeficiente de variación de las normas de Frobenius de las `A_i`.
- **En simple:** dispersión relativa de escala entre restricciones.
- **Cómo se calcula:** `std_ai_fro_norm_upper / avg_ai_fro_norm_upper`.

##### `feature_avg_ai_l1_norm`
- **Qué es:** promedio de norma L1 de las `A_i`.
- **En simple:** suma promedio de magnitudes absolutas por restricción.
- **Cómo se calcula:** promedio de `sum(|a|)` sobre las entradas almacenadas de cada `A_i`.

##### `feature_max_ai_l1_norm`
- **Qué es:** máxima norma L1 entre las `A_i`.
- **En simple:** la restricción con mayor suma total de magnitudes.
- **Cómo se calcula:** máximo de las normas L1 de las `A_i`.

##### `feature_min_ai_l1_norm`
- **Qué es:** mínima norma L1 entre las `A_i`.
- **En simple:** la restricción con menor suma total de magnitudes.
- **Cómo se calcula:** mínimo de las normas L1 de las `A_i`.

##### `feature_avg_ai_max_abs_entry`
- **Qué es:** promedio del coeficiente absoluto máximo de cada `A_i`.
- **En simple:** tamaño promedio del valor dominante dentro de cada restricción.
- **Cómo se calcula:** promedio de `max(|a|)` por matriz `A_i`.

##### `feature_max_ai_max_abs_entry`
- **Qué es:** mayor coeficiente absoluto máximo entre todas las `A_i`.
- **En simple:** el coeficiente más grande presente en alguna restricción.
- **Cómo se calcula:** máximo de los máximos absolutos por `A_i`.

##### `feature_avg_ai_min_abs_nonzero_entry`
- **Qué es:** promedio del menor coeficiente absoluto no nulo de cada `A_i`.
- **En simple:** tamaño promedio de los coeficientes más pequeños no nulos en las restricciones.
- **Cómo se calcula:** promedio de `min(|a|)` no nulo por `A_i`.

##### `feature_min_ai_min_abs_nonzero_entry`
- **Qué es:** menor coeficiente absoluto no nulo observado entre todas las `A_i`.
- **En simple:** el coeficiente no nulo más pequeño de todas las restricciones.
- **Cómo se calcula:** mínimo entre los mínimos absolutos no nulos por `A_i`.

##### `feature_avg_ai_dynamic_range`
- **Qué es:** promedio del rango dinámico interno de las `A_i`.
- **En simple:** desbalance promedio entre coeficientes grandes y pequeños dentro de las restricciones.
- **Cómo se calcula:** promedio de `max_abs(A_i) / min_abs_nonzero(A_i)`.

##### `feature_max_ai_dynamic_range`
- **Qué es:** mayor rango dinámico interno entre las `A_i`.
- **En simple:** la restricción más mal escalada internamente.
- **Cómo se calcula:** máximo de los rangos dinámicos por `A_i`.

##### `feature_min_ai_dynamic_range`
- **Qué es:** menor rango dinámico interno entre las `A_i`.
- **En simple:** la restricción más uniforme en magnitudes.
- **Cómo se calcula:** mínimo de los rangos dinámicos por `A_i`.

##### `feature_b_l1_norm`
- **Qué es:** norma L1 de `b`.
- **En simple:** suma de magnitudes absolutas del lado derecho.
- **Cómo se calcula:** `sum(|b_i|)`.

##### `feature_b_l2_norm`
- **Qué es:** norma L2 de `b`.
- **En simple:** tamaño euclidiano del vector lado derecho.
- **Cómo se calcula:** `sqrt(sum(b_i^2))`.

##### `feature_b_max_abs`
- **Qué es:** valor absoluto máximo de `b`.
- **En simple:** componente de mayor magnitud del vector `b`.
- **Cómo se calcula:** `max(|b_i|)`.

##### `feature_b_min_abs_nonzero`
- **Qué es:** valor absoluto mínimo no nulo de `b`.
- **En simple:** componente no nula más pequeña del lado derecho.
- **Cómo se calcula:** `min(|b_i|)` sobre entradas no nulas.

##### `feature_b_dynamic_range`
- **Qué es:** rango dinámico de `b`.
- **En simple:** diferencia relativa entre la componente más grande y la más pequeña no nula del lado derecho.
- **Cómo se calcula:** `b_max_abs / b_min_abs_nonzero`.

##### `feature_b_mean`
- **Qué es:** promedio de las entradas de `b`.
- **En simple:** nivel medio del lado derecho.
- **Cómo se calcula:** promedio aritmético de `b`.

##### `feature_b_std`
- **Qué es:** desviación estándar de `b`.
- **En simple:** dispersión de las entradas del lado derecho.
- **Cómo se calcula:** desviación estándar poblacional de `b`.

##### `feature_global_all_coeff_max_abs`
- **Qué es:** mayor valor absoluto entre todos los coeficientes no nulos del cuerpo sparse.
- **En simple:** el coeficiente más grande del problema considerando `C` y todas las `A_i`.
- **Cómo se calcula:** máximo de `|value|` sobre todas las entradas no nulas leídas.

##### `feature_global_all_coeff_min_abs_nonzero`
- **Qué es:** menor valor absoluto no nulo entre todos los coeficientes del cuerpo sparse.
- **En simple:** el coeficiente no nulo más pequeño del problema.
- **Cómo se calcula:** mínimo de `|value|` sobre todas las entradas no nulas leídas.

##### `feature_global_all_coeff_dynamic_range`
- **Qué es:** rango dinámico global del problema.
- **En simple:** cuánta diferencia existe entre el coeficiente más grande y el más pequeño no nulo en todo el cuerpo sparse.
- **Cómo se calcula:** `global_all_coeff_max_abs / global_all_coeff_min_abs_nonzero`.

##### `feature_ratio_c_to_avg_ai_fro`
- **Qué es:** razón entre la escala de `C` y la escala promedio de las `A_i`.
- **En simple:** compara el tamaño del objetivo con el tamaño típico de una restricción.
- **Cómo se calcula:** `c_fro_norm_upper / avg_ai_fro_norm_upper`.

##### `feature_ratio_c_to_b_l2`
- **Qué es:** razón entre la escala de `C` y la escala de `b`.
- **En simple:** compara el objetivo con el lado derecho.
- **Cómo se calcula:** `c_fro_norm_upper / b_l2_norm`.

##### `feature_ratio_avg_ai_to_b_l2`
- **Qué es:** razón entre la escala promedio de las `A_i` y la escala de `b`.
- **En simple:** compara restricciones típicas con el lado derecho.
- **Cómo se calcula:** `avg_ai_fro_norm_upper / b_l2_norm`.

##### `feature_max_ai_to_min_ai_fro_ratio`
- **Qué es:** razón entre la mayor y la menor norma de Frobenius de las `A_i`.
- **En simple:** mide cuán desbalanceadas están las restricciones entre sí.
- **Cómo se calcula:** `max_ai_fro_norm_upper / min_ai_fro_norm_upper`.

##### `feature_max_ai_to_avg_ai_fro_ratio`
- **Qué es:** razón entre la mayor norma de Frobenius y la norma promedio de las `A_i`.
- **En simple:** mide si existe una restricción particularmente dominante en escala.
- **Cómo se calcula:** `max_ai_fro_norm_upper / avg_ai_fro_norm_upper`.

---

### 9.5 Otras features

Esta sección queda reservada para futuras familias de features, por ejemplo:

- features espectrales,
- features de rango,
- features de redundancia o dependencia lineal,
- features dinámicas obtenidas tras pocas iteraciones de un solver,
- features derivadas o combinadas para modelos de selección de solver.

---

## 10. Convención general

- `data/`: instancias
- `config/`: configuración
- `tools/wrappers_v2/`: wrappers
- `tools/runners/`: ejecución
- `tools/logging/`: logs

---

## 11. Licencia

Ver archivo `LICENSE`.
