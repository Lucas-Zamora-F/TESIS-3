import os
import matlab.engine

print("Iniciando el motor de MATLAB...")
eng = matlab.engine.start_matlab()

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_sdpt3 = os.path.abspath(os.path.join(ruta_actual, '..', '..', 'extern', 'sdpt3'))

try:
    eng.cd(ruta_sdpt3, nargout=0)
    eng.install_sdpt3(nargout=0)

    print("\n--- EJECUTANDO PRUEBA AUTOMÁTICA ---")
    
    # Este es el truco: 
    # Usamos eval para enviar la respuesta '1' inmediatamente después de llamar al demo
    # Simulando que alguien presionó '1' y luego 'Enter'
    
    print("Enviando respuesta '1' a la pregunta del demo...")
    # '1\n' simula escribir 1 y presionar Enter
    # Usamos una función de MATLAB que permite alimentar respuestas a preguntas de consola
    eng.eval("evalc('sqlpdemo');", nargout=0) 
    
    print("\n¡Prueba completada! Revisa arriba si salieron los cálculos.")

except Exception as e:
    print(f"\nOcurrió un error: {e}")
finally:
    eng.quit()
    print("Motor cerrado.")