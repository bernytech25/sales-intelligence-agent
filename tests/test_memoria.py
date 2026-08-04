"""
Prueba de memoria truncada del agente de ventas
"""

import sys
import os

# Agregar la carpeta padre al path para poder importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent_langgraph import run_agent

def probar_memoria():
    print("=" * 60)
    print("PRUEBA DE MEMORIA TRUNCADA")
    print("=" * 60)
    
    history = []
    
    preguntas = [
        "¿Quiénes son los vendedores?",
        "¿Cuánto vendió Ana?",
        "¿Cuánto vendió Pedro?",
        "¿Cuál es el producto más vendido?",
        "¿Qué productos hay en la tienda?",
        "¿Cuáles son las ventas por región?",
        "¿Y las ventas por categoría?",
        "¿Cómo fueron las ventas en Enero?",
        "¿Y en Febrero?",
        "¿Y en Marzo?",
        "¿Cuánto vendió Ana en Enero?",
    ]
    
    for i, pregunta in enumerate(preguntas, 1):
        print(f"\n[{i}] Pregunta: {pregunta}")
        
        history.append({"role": "user", "content": pregunta})
        respuesta = run_agent(pregunta, history)
        history.append({"role": "assistant", "content": respuesta})
        
        print(f"Respuesta: {respuesta[:200]}...")
        print(f"Historial: {len(history)} mensajes")
    
    print("\n" + "=" * 60)
    print("RESULTADO FINAL")
    print("=" * 60)
    
    ultima_respuesta = history[-1]["content"]
    if "Ana" in ultima_respuesta and ("ventas" in ultima_respuesta or "$" in ultima_respuesta or "pesos" in ultima_respuesta):
        print("✅ MEMORIA FUNCIONA: El agente recuerda quién es Ana")
    else:
        print("⚠️ REVISA MANUALMENTE:")
        print(f"Respuesta: {ultima_respuesta}")

if __name__ == "__main__":
    probar_memoria()