import os
import matlab.engine
from pathlib import Path

def run_matilda_with_my_data():
    # 1. Configuración de Rutas
    # Estamos en: .../sandbox/matilda_tests/
    CURRENT_DIR = Path(__file__).resolve().parent
    METADATA_CSV = CURRENT_DIR / "matilda_metadata.csv"
    OUTPUT_DIR = CURRENT_DIR / "matilda_run"
    
    # El repo está en: .../extern/matilda (o InstanceSpace)
    REPO_PATH = str(CURRENT_DIR.parent.parent / "extern" / "matilda")
    
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("Iniciando el motor de MATLAB... (esto puede tardar unos segundos)")
    eng = matlab.engine.start_matlab()

    try:
        # 2. Agregar el repositorio al PATH de MATLAB
        print(f"Conectando MATLAB al repositorio en: {REPO_PATH}")
        eng.addpath(eng.genpath(REPO_PATH), nargout=0)

        # 3. Configurar parámetros para MATILDA
        # Creamos una estructura de opciones (struct) para que el código sepa dónde leer y escribir
        print(f"Procesando: {METADATA_CSV.name}")
        
        # En el repo de andremun, la función principal suele ser 'ISA' o 'build_instance_space'
        # Le pasamos la ruta de tu CSV y la carpeta donde queremos los resultados
        
        # NOTA: Ajustamos 'ISA' por el nombre de la función principal si es necesario
        eng.workspace['csv_path'] = str(METADATA_CSV)
        eng.workspace['output_path'] = str(OUTPUT_DIR)
        
        print("Ejecutando el análisis de espacio de instancias (esto generará los gráficos)...")
        
        # Ejecutamos el comando de MATLAB que procesa el archivo
        # 'opts' es la forma estándar en que MATILDA recibe parámetros
        eng.eval("opts = struct('input', csv_path, 'output', output_path, 'saveplots', true);", nargout=0)
        eng.eval("ISA(opts);", nargout=0) 
        
        print(f"\n¡Éxito! Los gráficos y resultados deberían estar en: {OUTPUT_DIR}")

    except Exception as e:
        print(f"\nOcurrió un error durante la ejecución: {e}")
        print("\nTIP: Si dice que 'ISA' no se reconoce, verifica si el archivo principal del repo se llama 'build_instance_space.m' y cambia el nombre en este script.")

    finally:
        eng.quit()
        print("Motor de MATLAB cerrado.")

if __name__ == "__main__":
    run_matilda_with_my_data()