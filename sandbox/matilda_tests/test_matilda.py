import os
import matlab.engine

print("Iniciando el motor de MATLAB... (esto puede tardar unos 10-15 segundos)")
eng = matlab.engine.start_matlab()

# 1. Obtener la ruta exacta de la carpeta donde está MATILDA
ruta_actual = os.path.dirname(os.path.abspath(__file__))

# AQUÍ ESTÁ EL CAMBIO: Retrocedemos dos carpetas (..) para llegar a la raíz
ruta_matilda = os.path.abspath(os.path.join(ruta_actual, '..', '..', 'extern', 'matilda'))

print(f"Conectando MATLAB a la carpeta principal: {ruta_matilda}")

try:
    # 2. Decirle a MATLAB que "viaje" a esa carpeta
    eng.cd(ruta_matilda, nargout=0)

    # 3. Ejecutar el script "example.m"
    print("Ejecutando example.m de MATILDA...")
    eng.example(nargout=0)
    
    print("\n¡Ejecución terminada con éxito!")

except Exception as e:
    print(f"\nOcurrió un error al ejecutar MATILDA: {e}")

finally:
    # 4. Cerrar el motor para liberar memoria
    eng.quit()
    print("Motor de MATLAB cerrado.")