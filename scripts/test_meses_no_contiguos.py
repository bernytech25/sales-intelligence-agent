"""
Corre el caso "meses no contiguos" N veces seguidas para ver si el LLM
es consistente en cómo lo resuelve (una sola llamada con rango continuo,
o dos llamadas puntuales por mes) antes de decidir si hace falta una tool
nueva o si el comportamiento actual ya es aceptable.

Incluye una pausa entre corridas para no saturar el rate limit de Gemini
(ChatGoogleGenerativeAI ya reintenta automáticamente con max_retries=6 por
default, pero eso es solo un colchón ante errores transitorios — no
reemplaza espaciar las llamadas si tu plan de Gemini tiene límite bajo de
requests por minuto).

Este script manual vive en scripts/ para que pytest no lo recoja por
accidente (ver C4 en el diagnóstico del proyecto).

Uso:
    python scripts/test_meses_no_contiguos.py
"""

import sys
import os
import time

# Agregar la carpeta padre al path para poder importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.agent_langgraph import run_agent

PREGUNTA = "¿Quién vendió más en mayo y octubre?"
N_CORRIDAS = 5
PAUSA_ENTRE_CORRIDAS_SEG = 10  # ajustá esto según el límite de tu plan de Gemini

if __name__ == "__main__":
    for i in range(1, N_CORRIDAS + 1):
        trace = run_agent(question=PREGUNTA, history=[], return_trace=True)
        print(f"\n[Corrida {i}/{N_CORRIDAS}]")
        print(f"  Tools llamadas: {trace['tools_called']}")
        print(f"  Respuesta: {trace['answer'][:200]}")
        if i < N_CORRIDAS:
            time.sleep(PAUSA_ENTRE_CORRIDAS_SEG)