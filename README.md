# SDP Benchmark Framework

## 1. Descripción general

Este repositorio implementa un framework modular para la ejecución, evaluación y comparación de solvers de programación semidefinida (SDP) utilizando instancias estándar, principalmente del conjunto SDPLIB en formato `.dat-s`.

El sistema está diseñado para:

- Ejecutar múltiples solvers bajo un esquema homogéneo.
- Centralizar la configuración de parámetros.
- Normalizar los resultados obtenidos.
- Registrar detalladamente la ejecución para análisis posterior.

La coordinación completa del sistema se realiza desde Python.

---

## 2. Estructura del repositorio

La organización del repositorio sigue una separación clara por responsabilidades:

```
TESIS-3/
│
├── config/
│   └── solver_config.json
│
├── data/
│   └── instances/
│       └── sdplib/
│
├── extern/
│   ├── sdpt3/
│   ├── sedumi/
│   ├── lorads/
│   ├── SDPNAL+v1.0/
│   └── manopt/
│
├── tools/
│   ├── wrappers_v2/
│   ├── runners/
│   └── logging/
│
├── sandbox/
│   └── *_tester.py
│
└── README.md
```

---

## 3. Descripción de componentes

### 3.1 `config/`

Contiene el archivo:

```
solver_config.json
```

Define:

- Parámetros globales aplicables a todos los solvers.
- Parámetros específicos por solver.

---

### 3.2 `data/instances/`

Contiene las instancias de prueba en formato `.dat-s`.

Ejemplos:

- `arch0.dat-s`
- `arch2.dat-s`
- `arch4.dat-s`
- `arch8.dat-s`

Estas instancias son utilizadas como entrada común para todos los solvers.

---

### 3.3 `extern/`

Contiene los repositorios externos de los solvers:

- SDPT3
- SeDuMi
- LoRADS
- SDPNAL+
- Manopt

Estos no forman parte del desarrollo del framework, pero son dependencias necesarias para la ejecución.

---

### 3.4 `tools/`

Contiene los módulos principales del sistema.

#### a) `wrappers_v2/`

Implementa un wrapper por cada solver.

Ejemplos:

```
lorads_wrapper.py
sedumi_wrapper.py
sdpt3_wrapper.py
```

Cada wrapper es responsable de:

- Leer configuración.
- Construir la ejecución del solver.
- Ejecutar el solver.
- Capturar y procesar resultados.
- Normalizar la salida.

---

#### b) `runners/`

Contiene la lógica de ejecución de procesos externos.

Archivo principal:

```
tools/runners/cli_runner.py
```

Responsabilidades:

- Ejecutar procesos mediante `subprocess`.
- Manejar timeouts.
- Capturar `stdout` y `stderr`.

---

#### c) `logging/`

Contiene el sistema de logging centralizado.

Archivo principal:

```
tools/logging/universal_logger.py
```

Registra:

- Eventos del sistema.
- Comandos ejecutados.
- Resultados.
- Errores.

---

### 3.5 `sandbox/`

Contiene scripts de prueba para ejecutar benchmarks.

Ejemplo:

```
lorads_wrapper_tester.py
```

Estos scripts:

- Seleccionan instancias.
- Ejecutan el wrapper correspondiente.
- Imprimen resultados.

---

## 4. Flujo de ejecución

El flujo de ejecución sigue la siguiente secuencia:

### 4.1 Script tester

Un script en `sandbox/` controla el experimento:

```python
wrapper = Wrapper()

for instance in instances:
    result = wrapper.solve(instance)
    results.append(result)

wrapper.close()
```

---

### 4.2 Wrapper

El wrapper es el componente central del sistema.

Responsabilidades:

1. Cargar configuración desde `solver_config.json`.
2. Construir el comando o llamada al solver.
3. Ejecutar el solver.
4. Capturar la salida.
5. Parsear resultados relevantes.
6. Normalizar el formato de salida.

Cada solver tiene su propio wrapper independiente.

---

### 4.3 Runner

El runner ejecuta el solver como proceso externo.

Funciones principales:

- Ejecutar comandos CLI.
- Aplicar timeouts.
- Capturar salida estándar y de error.

---

### 4.4 Logger

El logger registra todos los eventos relevantes:

- Inicio de ejecución.
- Parámetros utilizados.
- Comandos ejecutados.
- Resultados obtenidos.
- Errores.

---

## 5. Configuración

El archivo `config/solver_config.json` define el comportamiento del sistema.

### 5.1 Estructura

```json
{
  "global_settings": {
    "tolerance_gap": 1e-6,
    "max_iterations": 2000,
    "time_limit_seconds": 3600,
    "verbose": 0
  },
  "solvers": {
    "lorads": {
      "executable_path": "...",
      "hard_kill_timeout_seconds": 3630
    }
  }
}
```

---

### 5.2 Parámetros globales

- `tolerance_gap`: tolerancia de convergencia.
- `max_iterations`: máximo número de iteraciones.
- `time_limit_seconds`: límite de tiempo del solver.
- `verbose`: nivel de salida.

---

### 5.3 Parámetros por solver

Cada solver define sus propios parámetros adicionales, utilizados exclusivamente por su wrapper.

---

## 6. Criterio de evaluación

Todos los solvers se evalúan bajo el mismo criterio:

```
phi = max(gap, pinfeas, dinfeas)
```

Una solución se considera óptima si:

```
phi <= tolerance_gap
```

---

## 7. Formato de salida

Todos los wrappers retornan un diccionario con estructura uniforme:

```python
{
    "instance": str,
    "status": str,
    "obj_val": float,
    "gap": float,
    "pinfeas": float,
    "dinfeas": float,
    "phi": float,
    "optimal": bool,
    "iterations": int,
    "runtime": float,
    "numerr": int
}
```

---

## 8. Tipos de ejecución de solvers

### 8.1 Solvers basados en MATLAB

- SDPT3
- SeDuMi
- SDPNAL+

El wrapper:

- Inicializa MATLAB Engine.
- Ejecuta scripts `.m`.
- Extrae resultados desde MATLAB.

---

### 8.2 Solvers basados en CLI

Ejemplo:

- LoRADS

El wrapper:

- Construye un comando de ejecución.
- Ejecuta el binario (posiblemente vía WSL).
- Parsea la salida del proceso.

---

## 9. Manejo de tiempo de ejecución

Existen dos niveles de control:

### 9.1 Límite interno del solver

```
time_limit_seconds
```

---

### 9.2 Límite externo del wrapper

```
hard_kill_timeout_seconds
```

---

## 10. Logging

### 10.1 Log global

```
logs/benchmark_audit.log
```

---

### 10.2 Logs por instancia

Cada ejecución genera un archivo independiente que contiene:

- Comando ejecutado.
- Salida completa (`stdout`).
- Errores (`stderr`).

---

## 11. Ejecución

```
python sandbox/<solver>_wrapper_tester.py
```

Ejemplo:

```
python sandbox/lorads_wrapper_tester.py
```

---

## 12. Secuencia operacional

1. Python coordina la ejecución.
2. El wrapper construye la llamada al solver.
3. El runner ejecuta el proceso.
4. Se captura la salida.
5. Se extraen métricas relevantes.
6. Se normalizan los resultados.
7. Se registran logs.
