import matlab.engine
import os

def run_maxG11_final():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sdpnal_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'extern', 'SDPNAL+v1.0'))
    instance_path = os.path.abspath(os.path.join(current_dir, '..', '..', 'data', 'instances', 'sdplib', 'maxG11.dat-s'))

    print("Iniciando motor de MATLAB...")
    eng = matlab.engine.start_matlab()

    try:
        eng.eval(f"addpath(genpath('{sdpnal_path}'))", nargout=0)
        eng.cd(sdpnal_path, nargout=0)
        eng.eval("startup", nargout=0)

        print(f"Procesando: {os.path.basename(instance_path)}")
        clean_path = instance_path.replace('\\', '/')
        eng.eval(f"[blk, At, C, b] = read_sdpa('{clean_path}');", nargout=0)

        # Ejecución
        eng.eval("[obj, X, y, Z, info, runhist] = sdpnalplus(blk, At, C, b, [], [], [], [], [], []);", nargout=0)

        # Extracción segura de datos
        # Usamos eng.eval para traer solo el primer elemento del objetivo (el primal)
        primal_obj = eng.eval("obj(1)") 
        
        # Para info, lo traemos campo por campo para evitar errores de tipo de dato
        total_time = eng.eval("info.time")
        rel_gap = eng.eval("info.relgap")

        print("\n" + "="*50)
        print("REPORTE FINAL DE TESIS")
        print("="*50)
        print(f"Instancia:      {os.path.basename(instance_path)}")
        print(f"Objetivo Opt:   {primal_obj}")
        print(f"Relative Gap:   {rel_gap:.2e}")
        print(f"Tiempo Total:   {total_time:.2f} s")
        print("="*50)

    except Exception as e:
        print(f"Error detectado: {e}")

    finally:
        eng.quit()
        print("Proceso finalizado.")

if __name__ == "__main__":
    run_maxG11_final()