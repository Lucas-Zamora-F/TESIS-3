import os
import matlab.engine

print("Iniciando el motor de MATLAB para SeDuMi...")
eng = matlab.engine.start_matlab()

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_sedumi = os.path.abspath(os.path.join(ruta_actual, '..', '..', 'extern', 'sedumi'))

try:
    eng.cd(ruta_sedumi, nargout=0)
    print("Configurando SeDuMi...")
    eng.install_sedumi(nargout=0)
    
    # --- CAMBIO AQUÍ ---
    # Entramos a la carpeta 'test' que es donde vive el script sedumitest.m
    ruta_test = os.path.join(ruta_sedumi, 'test')
    if os.path.exists(ruta_test):
        eng.cd(ruta_test, nargout=0)
        print("\nEjecutando test de autoverificación (sedumitest)...")
        print("-" * 50)
        eng.sedumitest(nargout=0)
        print("-" * 50)
    else:
        # Si no existe la carpeta test, probamos con un ejemplo simple
        print("\nNo se encontró 'sedumitest', probando comando básico...")
        eng.eval("sedumi(eye(2), [1;1], [1;1])", nargout=0)
    
    print("¡SeDuMi verificado con éxito!")

except Exception as e:
    print(f"\nOcurrió un error: {e}")

finally:
    eng.quit()
    print("Motor de MATLAB cerrado.")