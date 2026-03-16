import os
import sys

# 1. Configuración de rutas para encontrar los wrappers
current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_script_path, ".."))
sys.path.insert(0, project_root)

# Importamos los wrappers
try:
    from tools.wrappers.sdpt3_wrapper import run_benchmark as run_sdpt3
    from tools.wrappers.sedumi_wrapper import run_benchmark as run_sedumi
except ImportError as e:
    print(f"Error: No se pudieron importar los wrappers. Verifica las rutas. {e}")
    sys.exit(1)

def main():
    # Configuración de directorios
    instance_dir = os.path.join(project_root, "data", "instances", "sdplib")
    config_file = os.path.join(project_root, "metadata", "solver_config.json")

    # 2. Escaneo automático de la carpeta
    if not os.path.exists(instance_dir):
        print(f"Error: La carpeta de instancias no existe en {instance_dir}")
        return

    # Listar todos los archivos .dat-s en la carpeta
    all_instances = sorted([f for f in os.listdir(instance_dir) if f.endswith(".dat-s")])

    if not all_instances:
        print(f"No se encontraron archivos .dat-s en {instance_dir}")
        return

    print(f"--- Comparativa Masiva: SDPT3 vs SeDuMi ---")
    print(f"Total de instancias detectadas: {len(all_instances)}\n")

    try:
        # 3. Ejecución de Benchmarks
        print(f"Ejecutando SDPT3 sobre {len(all_instances)} instancias...")
        results_sdpt3 = run_sdpt3(instance_dir, config_file, filter_list=all_instances)
        
        print(f"Ejecutando SeDuMi sobre {len(all_instances)} instancias...")
        results_sedumi = run_sedumi(instance_dir, config_file, filter_list=all_instances)

        # 4. Mapeo de resultados
        dict_sdpt3 = {res['instance']: res for res in results_sdpt3}
        dict_sedumi = {res['instance']: res for res in results_sedumi}

        # 5. Salida en pantalla
        header = (f"{'INSTANCE':<18} | {'SOLVER':<8} | {'OBJ VAL':<12} | "
                  f"{'GAP':<9} | {'ITS':<4} | {'TIME':<6} | {'OPT':<4} | {'CODE'}")
        
        width = 88
        print("\n" + "=" * width)
        print(header)
        print("-" * width)

        for inst in all_instances:
            # Datos SDPT3
            s3 = dict_sdpt3.get(inst)
            if s3:
                print_row(inst, "SDPT3", s3)
            else:
                print(f"{inst:<18} | {'SDPT3':<8} | {'Error/Skip':<12}")

            # Datos SeDuMi
            sm = dict_sedumi.get(inst)
            if sm:
                print_row("", "SeDuMi", sm)
            else:
                print(f"{'':<18} | {'SeDuMi':<8} | {'Error/Skip':<12}")
            
            print("-" * width)

        print(f"\nProceso finalizado. Se procesaron {len(all_instances)} instancias.")

    except Exception as e:
        print(f"Error crítico durante la ejecución masiva: {e}")

def print_row(inst_name, solver_name, data):
    """Formatea una fila de la tabla con validación de tipos."""
    obj  = data.get('obj_val', 'NaN')
    gap  = data.get('gap', 'NaN')
    its  = data.get('iterations', 0)
    time = data.get('runtime', 0)
    code = data.get('status', 'N/A')
    
    # Lógica de optimalidad
    is_opt_val = data.get('is_optimal', False)
    is_opt = "YES" if str(is_opt_val) in ['True', '1', '1.0'] else "NO"

    # Formateo numérico seguro
    obj_str  = f"{float(obj):.3e}" if is_numeric(obj) else "N/A"
    gap_str  = f"{float(gap):.1e}" if is_numeric(gap) else "N/A"
    its_str  = f"{int(float(its))}" if is_numeric(its) else "N/A"
    time_str = f"{float(time):.2f}" if is_numeric(time) else "N/A"
    code_str = f"{int(float(code))}" if is_numeric(code) else "N/A"

    print(f"{inst_name:<18} | {solver_name:<8} | {obj_str:<12} | "
          f"{gap_str:<9} | {its_str:<4} | {time_str:<6} | {is_opt:<4} | {code_str}")

def is_numeric(val):
    if val is None: return False
    try:
        import math
        f_val = float(val)
        return not math.isnan(f_val)
    except (ValueError, TypeError):
        return False

if __name__ == "__main__":
    main()