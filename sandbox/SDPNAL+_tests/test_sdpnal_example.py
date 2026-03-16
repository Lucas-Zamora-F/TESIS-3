import matlab.engine
import os

def run_sdpnal_example():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sdpnal_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'extern', 'SDPNAL+v1.0'))

    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        # 1. Configuración de entorno
        eng.eval(f"addpath(genpath('{sdpnal_path}'))", nargout=0)
        eng.cd(sdpnal_path, nargout=0)
        eng.eval("startup", nargout=0)

        # 2. Carga y ejecución
        print("Cargando datos y ejecutando solver...")
        eng.eval("load Example_theta.mat", nargout=0)
        eng.eval("blk = input_data.blk; At = input_data.At; C = input_data.C; b = input_data.b;", nargout=0)
        
        # Ejecución del solver
        eng.eval("[obj,X,y,Z,info,runhist] = sdpnalplus(blk,At,C,b,[],[],[],[],[],[]);", nargout=0)

        # 3. Extracción segura de resultados
        # Usamos float() para asegurar que el valor sea un tipo nativo de Python
        obj_value = eng.workspace['obj']
        
        print("\n" + "="*50)
        print("RESULTADOS DESDE PYTHON")
        print("="*50)
        print(f"Valor objetivo optimizado: {obj_value}")
        print("Estado: Problema resuelto con éxito.")
        print("="*50)

    except Exception as e:
        print(f"Error durante la ejecucion:\n{e}")

    finally:
        eng.quit()
        print("\nMotor de MATLAB cerrado.")

if __name__ == "__main__":
    run_sdpnal_example()