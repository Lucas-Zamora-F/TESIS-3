import matlab.engine
import os

def run_arch0_instance():
    # 1. Configuración de rutas
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sdpnal_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'extern', 'SDPNAL+v1.0'))
    instance_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'data', 'instances', 'sdplib', 'arch0.dat-s'))

    if not os.path.exists(instance_path):
        print(f"Error: No se encontró el archivo en {instance_path}")
        return

    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        # 2. Configurar el entorno (Path recursivo para incluir 'util')
        eng.eval(f"addpath(genpath('{sdpnal_path}'))", nargout=0)
        eng.cd(sdpnal_path, nargout=0)
        eng.eval("startup", nargout=0)

        # 3. Leer la instancia usando la función detectada: read_sdpa
        print(f"Leyendo instancia SDPA: {os.path.basename(instance_path)}...")
        # read_sdpa devuelve [blk, At, C, b]
        clean_path = instance_path.replace('\\', '/')
        eng.eval(f"[blk, At, C, b] = read_sdpa('{clean_path}');", nargout=0)

        # 4. Ejecutar el solver
        print("Resolviendo con SDPNAL+...")
        # Se añaden los arrays vacíos [] para los parámetros opcionales (L, U, etc.)
        eng.eval("[obj, X, y, Z, info, runhist] = sdpnalplus(blk, At, C, b, [], [], [], [], [], []);", nargout=0)

        # 5. Mostrar resultados finales
        obj_value = eng.workspace['obj']
        print("-" * 50)
        print("RESULTADOS EXITOSOS")
        print(f"Instancia: arch0.dat-s")
        print(f"Valor objetivo (primal): {obj_value}")
        print("-" * 50)

    except Exception as e:
        print(f"Error durante la ejecución:\n{e}")

    finally:
        eng.quit()
        print("\nMotor de MATLAB cerrado.")

if __name__ == "__main__":
    run_arch0_instance()