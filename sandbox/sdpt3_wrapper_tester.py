import os
import sys

# Update path to find tools.wrappers
current_script_path = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_script_path, ".."))
sys.path.append(project_root)

from tools.wrappers.sdpt3_wrapper import run_benchmark


def main():
    # 1. Configuration of paths
    instances_to_test = ["arch0.dat-s", "arch2.dat-s", "arch4.dat-s", "arch8.dat-s"]
    instance_dir = os.path.join(project_root, "data", "instances", "sdplib")
    config_file = os.path.join(project_root, "metadata", "solver_config.json")
    
    print(f"--- SDPT3 Diagnostic Tester ---")
    print(f"Targeting: {len(instances_to_test)} instances")

    # 2. Execution
    try:
        results = run_benchmark(
            instance_folder=instance_dir, 
            config_path=config_file, 
            filter_list=instances_to_test
        )

        # 3. Terminal Output (Tabla de diagnóstico expandida)
        # Ajustamos el ancho para que la información técnica sea legible
        width = 95
        header = f"{'INSTANCE':<15} | {'GAP':<9} | {'P-INF':<9} | {'D-INF':<9} | {'ITER':<5} | {'TIME':<6} | {'CODE'}"
        
        print("\n" + "="*width)
        print(header)
        print("-" * width)
        
        for res in results:
            # Formateo de las tres causales (Criterios KKT)
            gap  = f"{res['gap']:.1e}" if res.get('gap') is not None else "NaN"
            pinf = f"{res['pinfeas']:.1e}" if res.get('pinfeas') is not None else "NaN"
            dinf = f"{res['dinfeas']:.1e}" if res.get('dinfeas') is not None else "NaN"
            
            runtime = f"{res['runtime']:.2f}"
            iters   = int(res['iterations'])
            code    = int(res['status'])
            
            # Etiqueta de status amigable para el código
            status_str = "Success" if code == 0 else f"Code({code})"
            
            print(f"{res['instance']:<15} | {gap:<9} | {pinf:<9} | {dinf:<9} | {iters:<5} | {runtime:<6} | {status_str}")
            
        print("="*width + "\n")
        print("Nota: P-INF (Primal Infeasibility), D-INF (Dual Infeasibility)")

    except Exception as e:
        print(f"Critical error during execution: {e}")


if __name__ == "__main__":
    main()