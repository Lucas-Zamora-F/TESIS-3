# TESIS-3

Framework modular para ejecutar, evaluar y comparar solvers de programación semidefinida (SDP) sobre instancias estándar, con coordinación desde Python, integración con MATLAB y generación de metadata para análisis en Instance Space / MATILDA.

---

## 1. Objetivo del repositorio

Este proyecto busca construir una base de experimentación reproducible para benchmarking de solvers SDP. La idea central es que distintas herramientas de resolución puedan ejecutarse bajo una interfaz homogénea, de manera que:

- las instancias se procesen desde una estructura común,
- la configuración esté centralizada en archivos JSON,
- los resultados se normalicen en un formato comparable,
- el flujo completo quede trazable mediante logging,
- y los datos finales puedan utilizarse para análisis de desempeño mediante Instance Space.

---

## 2. Estado actual del proyecto

Actualmente el repositorio ya permite:

- definir subconjuntos de instancias a usar desde `config/instances_config.json`,
- alternativamente, ejecutar el pipeline sobre todas las instancias disponibles en el dataset,
- calcular tablas de features estructurales y numéricas de forma configurable mediante `config/features_config.json`,
- ejecutar solvers habilitados desde un registro central (`config/solver_registry.json`) usando wrappers dinámicos,
- construir una tabla de runtimes con formato estandarizado (`algo_<solver>`),
- combinar features y resultados en una tabla final de metadata,
- estandarizar dicha metadata para compatibilidad con Instance Space (columna `Instances`),
- guardar la metadata en `ISA metadata/metadata.csv`,
- y ejecutar MATILDA / InstanceSpace utilizando configuración externa (`config/instance_space_config.json`).

Los solvers actualmente habilitados en el registro son:

- `sdpt3`
- `sedumi`

---

## 3. Estructura del repositorio

```text
TESIS-3/
├── ISA metadata/
│   └── metadata.csv
│
├── config/
│   ├── features_config.json
│   ├── instance_space_config.json
│   ├── instances_config.json
│   ├── solver_config.json
│   └── solver_registry.json
│
├── data/
│   └── instances/
│       └── sdplib/
│
├── examples/
│   └── matilda_run/
│
├── extern/
│   ├── InstanceSpace/
│   ├── InstanceSpace87fe24e/
│   ├── sdpt3/
│   └── sedumi/
│
├── logs/
│   └── benchmark_audit.log
│
├── main/
│   ├── build_features_table.py
│   ├── build_isa_metadata_table.py
│   ├── build_solver_runtime_table.py
│   └── orchestrate_isa_metadata.py
│
├── matilda_out/
│   └── run_YYYYMMDD_HHMMSS/
│
├── sandbox/
│
├── tools/
│   ├── features/
│   ├── installation/
│   ├── isa/
│   ├── logging/
│   ├── matlab/
│   ├── runners/
│   └── wrappers_v2/
│
├── .gitignore
├── .gitmodules
├── LICENSE
├── README.md
└── requirements.txt
```

---

## 3. Descripción de cada componente

### 3.1 `config/`

Contiene toda la configuración central del framework, separando completamente lógica de código y parámetros experimentales.

Archivos principales:

- `solver_config.json`: define parámetros globales y específicos por solver
- `solver_registry.json`: define qué solvers están habilitados y cómo cargarlos dinámicamente
- `features_config.json`: define qué features se calculan y cuáles existen
- `instances_config.json`: define qué instancias usar
- `instance_space_config.json`: configuración de MATILDA / Instance Space

Actualmente incluye:

- `global_settings`
  - `tolerance_gap`
  - `max_iterations`
  - `time_limit_seconds`
  - `verbose`

- `solvers.sdpt3`
- `solvers.sedumi`

Además:

- `solver_registry.json` permite desacoplar completamente los solvers del código mediante carga dinámica de wrappers
- `features_config.json` permite seleccionar features sin modificar código
- `instances_config.json` permite controlar el subconjunto de instancias a utilizar

Esta organización permite modificar el comportamiento del framework sin alterar directamente el código.

---

### 3.2 `data/instances/sdplib/`

Contiene las instancias SDP en formato `.dat-s`, utilizadas como input para todos los solvers.

El sistema puede:

- usar solo instancias definidas en `config/instances_config.json`
- o usar todas las instancias disponibles en esta carpeta

---

### 3.3 `examples/`

Contiene ejemplos persistentes de corridas del sistema.

En particular:

- `matilda_run/`: ejemplo de ejecución completa de MATILDA, conservado como referencia

Esta carpeta permite mantener resultados reproducibles que no deben ser sobrescritos ni ignorados por git.

---

### 3.4 `extern/`

Agrupa dependencias externas necesarias para ejecutar los solvers y análisis.

Incluye:

- InstanceSpace
- InstanceSpace87fe24e (versión congelada para compatibilidad)
- SeDuMi
- SDPT3

Para agregar estos submódulos:

```bash
git submodule add https://github.com/andremun/InstanceSpace extern/InstanceSpace
git submodule add https://github.com/sqlp/sedumi extern/sedumi
git submodule add https://github.com/sqlp/sdpt3 extern/sdpt3

```

---

## 4. Flujo general de ejecución

El flujo principal del sistema está orquestado por:

main/orchestrate_isa_metadata.py

Este script coordina todo el pipeline de forma secuencial.

---

### Paso 1: Inicialización

- Se carga la configuración desde `config/`
- Se inicializa el sistema de logging (`logs/benchmark_audit.log`)
- Se determinan los parámetros de ejecución:
  - `use_all_instances`
  - `run_matilda_step`

---

### Paso 2: Selección de instancias

Dependiendo del parámetro `use_all_instances`:

- Si es `False`:
  - se cargan las instancias desde `config/instances_config.json` → `enabled_instances`

- Si es `True`:
  - se toman todas las instancias `.dat-s` disponibles en:
    data/instances/sdplib/

El resultado es una lista de rutas a instancias que se utilizarán en todo el pipeline.

---

### Paso 3: Construcción de tabla de features

Script ejecutado:
main/build_features_table.py

Proceso:

1. Se carga `config/features_config.json`
2. Se identifican las `enabled_features`
3. Se recorren las instancias seleccionadas
4. Para cada grupo de features:
   - se importa dinámicamente el extractor correspondiente
   - se calculan solo las features habilitadas
5. Se construye un DataFrame con:

Instance | feature_*

Este DataFrame se mantiene en memoria (no se guarda en disco en esta etapa).

---

### Paso 4: Ejecución de solvers

Script ejecutado:
main/build_solver_runtime_table.py

Proceso:

1. Se carga `config/solver_registry.json`
2. Se identifican los `enabled_solvers`
3. Para cada solver:
   - se carga dinámicamente su wrapper (`wrappers_v2`)
4. Para cada instancia:
   - se ejecuta cada solver
   - el wrapper:
     - prepara el entorno MATLAB
     - ejecuta el solver
     - captura resultados
     - normaliza métricas
5. Se construye un DataFrame con:

Instance | algo_sdpt3 | algo_sedumi

Cada columna representa el tiempo de ejecución del solver para cada instancia.

---

### Paso 5: Construcción de metadata final

Script ejecutado:
main/build_isa_metadata_table.py

Proceso:

1. Se reciben:
   - `features_df`
   - `solver_runtime_df`
2. Se realiza un merge por la columna `Instance`
3. Se renombra la columna a `Instances` (requisito de MATILDA)
4. Se ordenan las columnas

Resultado:

Instances | feature_* | algo_*

---

### Paso 6: Guardado de metadata

El resultado final se guarda en:

ISA metadata/metadata.csv

Este archivo es el input directo para Instance Space.

---

### Paso 7: Ejecución de MATILDA (opcional)

Si `run_matilda_step = True`, se ejecuta:

tools/isa/run_matilda.py

Proceso:

1. Se carga:
   - metadata.csv
   - `config/instance_space_config.json`
2. Se crea una carpeta de ejecución:

matilda_out/run_YYYYMMDD_HHMMSS/

3. Se copian:
   - metadata
   - configuración (`options.json`)
4. Se inicia MATLAB
5. Se ejecuta InstanceSpace (`buildIS`)

---

### Paso 8: Resultados

Los resultados de MATILDA quedan en:

matilda_out/run_YYYYMMDD_HHMMSS/

Mientras que la metadata base queda en:

ISA metadata/metadata.csv

---

## Resumen del flujo

Instancias  
→ Features  
→ Solvers  
→ Metadata  
→ (Opcional) MATILDA  
→ Resultados

---

## 5. Resultado estándar esperado

El resultado principal del pipeline es una tabla de metadata consolidada que combina:

- información estructural de las instancias (features),
- y desempeño de los solvers (runtimes).

Esta tabla se guarda en:

ISA metadata/metadata.csv

---

### Estructura general

La tabla debe cumplir con el siguiente formato:

Instances | feature_* | algo_*

Donde:

- `Instances`: nombre de la instancia (incluye extensión `.dat-s`)
- `feature_*`: características estructurales y numéricas
- `algo_*`: métricas de desempeño de los solvers (actualmente, tiempo de ejecución)

---

### Ejemplo

Instances | feature_m | feature_n_blocks | feature_b_l2_norm | algo_sdpt3 | algo_sedumi  
arch0.dat-s | ... | ... | ... | 12.53 | 8.91  
arch2.dat-s | ... | ... | ... | 20.11 | 14.77  

---

### Reglas del formato

- La primera columna debe llamarse exactamente `Instances` (requisito de MATILDA)
- Los nombres de instancias deben conservar la extensión `.dat-s`
- Todas las features deben comenzar con el prefijo `feature_`
- Todas las métricas de solvers deben comenzar con el prefijo `algo_`
- Cada fila representa una instancia única
- No deben existir duplicados en la columna `Instances`

---

### Consideraciones sobre las métricas

- Actualmente, las columnas `algo_*` representan el tiempo de ejecución de cada solver
- El criterio implícito es: **menor valor = mejor desempeño**
- Todas las métricas deben ser comparables entre solvers

---

### Uso del resultado

Este archivo es utilizado como input para:

tools/isa/run_matilda.py

y posteriormente por Instance Space (MATILDA) para:

- análisis de desempeño,
- visualización de instancias,
- construcción de espacios de instancia,
- y generación de modelos de predicción de solvers.

---

### Consistencia

Este formato actúa como contrato entre:

- el pipeline de generación de datos,
- y la etapa de análisis (MATILDA),

por lo que cualquier modificación en la estructura debe mantener compatibilidad con Instance Space.

---

## 6. Dependencias

El proyecto requiere dependencias tanto en Python como en MATLAB, además de repositorios externos para los solvers.

---

### Python

Dependencias principales:

- Python 3.10+
- pandas
- numpy
- scipy
- matplotlib

Estas dependencias están definidas en:

requirements.txt

Instalación:

pip install -r requirements.txt

---

### MATLAB

Se requiere:

- MATLAB instalado
- MATLAB Engine API for Python

Para instalar el engine:

```bash
cd "MATLAB_ROOT/extern/engines/python"
python -m pip install .
```

---

## 7. Cómo ejecutar

El punto de entrada principal del proyecto es:

main/orchestrate_isa_metadata.py

Este script coordina la selección de instancias, la construcción de features, la ejecución de solvers, la generación de metadata y, opcionalmente, la ejecución de MATILDA.

---

### 7.1 Preparar el entorno

Instalar dependencias Python:

pip install -r requirements.txt

Inicializar submódulos:

git submodule sync --recursive
git submodule update --init --recursive

Si se desea, también puede ejecutarse el script de preparación del entorno:

python tools/installation/setup_env.py

---

### 7.2 Ejecutar el pipeline principal

Desde la raíz del repositorio:

python main/orchestrate_isa_metadata.py

Esto ejecuta el flujo completo definido en el orquestador.

---

### 7.3 Ejecutar desde Python

También es posible importar y ejecutar el orquestador directamente:

from main.orchestrate_isa_metadata import orchestrate_isa_metadata

metadata_df = orchestrate_isa_metadata(
    run_matilda_step=False,
    use_all_instances=False
)

Parámetros principales:

- `run_matilda_step`: si es `True`, ejecuta MATILDA al final del pipeline
- `use_all_instances`: si es `True`, usa todas las instancias disponibles en `data/instances/sdplib/`; si es `False`, usa solo las definidas en `config/instances_config.json`

---

### 7.4 Ejecutar usando solo instancias habilitadas

Configuración típica:

- definir las instancias en `config/instances_config.json`
- ejecutar con:

from main.orchestrate_isa_metadata import orchestrate_isa_metadata

metadata_df = orchestrate_isa_metadata(
    run_matilda_step=False,
    use_all_instances=False
)

---

### 7.5 Ejecutar usando todas las instancias del dataset

from main.orchestrate_isa_metadata import orchestrate_isa_metadata

metadata_df = orchestrate_isa_metadata(
    run_matilda_step=False,
    use_all_instances=True
)

---

### 7.6 Ejecutar con MATILDA

Para correr también la etapa de Instance Space:

from main.orchestrate_isa_metadata import orchestrate_isa_metadata

metadata_df = orchestrate_isa_metadata(
    run_matilda_step=True,
    use_all_instances=False
)

Esto generará:

- la metadata en `ISA metadata/metadata.csv`
- una carpeta de salida en `matilda_out/run_YYYYMMDD_HHMMSS/`

---

### 7.7 Salidas esperadas

Después de una ejecución exitosa, el proyecto debe generar:

- `ISA metadata/metadata.csv`
- logs en `logs/benchmark_audit.log`
- si MATILDA está habilitado, una nueva carpeta en `matilda_out/`

---

### 7.8 Recomendación de uso

Para pruebas rápidas, se recomienda:

- usar pocas instancias en `enabled_instances`
- ejecutar primero con `run_matilda_step=False`
- verificar la metadata generada
- luego habilitar `run_matilda_step=True` para lanzar MATILDA

---

## 8. Estado actual del proyecto

El repositorio se encuentra en una etapa funcional y estable para benchmarking reproducible de solvers SDP.

Actualmente, el sistema:

- cuenta con un pipeline completo desde instancias hasta análisis en Instance Space,
- permite configuración flexible mediante archivos JSON (sin hardcodeo),
- implementa una arquitectura modular basada en builders, wrappers y orquestador,
- soporta ejecución de múltiples solvers bajo una interfaz homogénea,
- y genera metadata directamente utilizable por MATILDA.

---

### Nivel de madurez

El proyecto ya no es un prototipo aislado, sino un framework estructurado que permite:

- repetir experimentos de forma consistente,
- agregar nuevas features sin modificar el pipeline,
- integrar nuevos solvers mediante wrappers,
- y escalar el número de instancias analizadas.

---

### Componentes completamente operativos

- pipeline de features (`build_features_table.py`)
- pipeline de runtimes de solvers (`build_solver_runtime_table.py`)
- construcción de metadata (`build_isa_metadata_table.py`)
- orquestador principal (`orchestrate_isa_metadata.py`)
- integración con MATILDA (`run_matilda.py`)
- sistema de logging unificado

---

### Limitaciones actuales

- número limitado de solvers integrados (`sdpt3`, `sedumi`)
- dependencia directa de MATLAB para ejecución de solvers
- ejecución secuencial (sin paralelización avanzada en Python)
- validación limitada de errores en wrappers (dependiente del solver)
- dependencia de versiones específicas de InstanceSpace para compatibilidad

---

### Próximas extensiones naturales

La arquitectura actual permite extender el sistema en varias direcciones:

- agregar nuevos solvers mediante nuevos wrappers
- incorporar paralelización en la ejecución de instancias
- ampliar el conjunto de features disponibles
- integrar nuevos runners (por ejemplo, ejecución vía CLI)
- mejorar validación y manejo de errores
- automatizar experimentos a mayor escala

---

En su estado actual, el repositorio ya es utilizable como base para experimentación sistemática en benchmarking de solvers SDP y análisis mediante Instance Space.
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

## 10. Convención general

El proyecto sigue un conjunto de convenciones para asegurar consistencia, trazabilidad y compatibilidad entre componentes.

---

### Nombres de instancias

- Las instancias deben conservar su nombre original de archivo
- Siempre deben incluir la extensión `.dat-s`
- La identificación de cada instancia se basa exclusivamente en este nombre

Ejemplo:

arch0.dat-s  
arch2.dat-s  

---

### Columnas de datos

Se utilizan prefijos estándar para distinguir tipos de información:

- `feature_*`: características estructurales o numéricas
- `algo_*`: métricas de desempeño de los solvers

Ejemplo:

feature_m  
feature_n_blocks  
algo_sdpt3  
algo_sedumi  

---

### Columna principal

- La tabla final debe contener una columna llamada exactamente:

Instances

- Esta columna es obligatoria para compatibilidad con MATILDA
- Debe ser la primera columna del DataFrame

---

### Estructura de metadata

- Cada fila representa una instancia única
- No deben existir duplicados en `Instances`
- Todas las columnas deben ser consistentes entre ejecuciones

---

### Configuración

- Toda configuración debe residir en la carpeta `config/`
- No se deben hardcodear parámetros en los scripts
- Los cambios experimentales deben realizarse vía archivos JSON

---

### Solvers

- Los solvers deben integrarse mediante wrappers en `tools/wrappers_v2/`
- Cada solver debe declararse en `solver_registry.json`
- Las métricas deben seguir el formato estándar del proyecto

---

### Logging

- Todas las ejecuciones deben registrarse en:

logs/benchmark_audit.log

- El logging debe permitir trazabilidad completa del pipeline

---

### Reproducibilidad

- Los resultados deben ser reproducibles a partir de:
  - las instancias
  - los archivos de configuración
  - la versión de los submódulos externos

---

### Estructura del proyecto

- Separación estricta entre:
  - configuración (`config/`)
  - lógica (`main/`, `tools/`)
  - datos (`data/`)
  - resultados (`ISA metadata/`, `matilda_out/`, `examples/`)

---

### Uso de git

- `matilda_out/` contiene resultados generados → no versionados
- `examples/` contiene corridas de referencia → sí versionadas
- `logs/benchmark_audit.log` se mantiene persistente

---

Estas convenciones permiten mantener un flujo consistente, extensible y reproducible a lo largo del desarrollo del proyecto.
---

## 11. Licencia

Ver archivo `LICENSE`.
