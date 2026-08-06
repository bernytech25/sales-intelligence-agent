"""
Test suite para evaluar el Sales Agent con trazabilidad en LangSmith.

Requisitos:
- Tener LANGCHAIN_TRACING_V2=true en tu .env
- Tener LANGCHAIN_API_KEY y LANGCHAIN_PROJECT configurados

Uso:
    python test_langsmith.py

Esto ejecutará 8 preguntas representativas y generará traces en LangSmith
para que puedas analizar latencia, tool calling, y calidad de respuestas.
"""

import os
import time
from dotenv import load_dotenv

# Cargar variables de entorno (incluyendo LangSmith)
load_dotenv()

from app.agent_langgraph import run_agent

# ── Preguntas de test ─────────────────────────────────────────────────────────

TESTS = [
    {
        "name": "Ranking general",
        "question": "¿Quién vendió más?",
        "expected_tool": "tool_ventas_por_vendedor",
    },
    {
        "name": "Análisis por categoría",
        "question": "¿Qué categoría de producto tiene más ventas?",
        "expected_tool": "tool_ventas_por_categoria",
    },
    {
        "name": "Análisis geográfico",
        "question": "¿Qué región vendió más?",
        "expected_tool": "tool_ventas_por_region",
    },
    {
        "name": "Tendencia temporal",
        "question": "¿Cómo fueron las ventas mes a mes?",
        "expected_tool": "tool_ventas_por_mes",
    },
    {
        "name": "Vendedor específico",
        "question": "¿Cuánto vendió Ana en febrero?",
        "expected_tool": "tool_ventas_vendedor_por_mes",
    },
    {
        "name": "Producto + región",
        "question": "¿En qué región se vende más el producto Laptop Dell XPS?",
        "expected_tool": "tool_ventas_por_producto",
    },
    {
        "name": "Catálogo",
        "question": "¿Qué productos vende la tienda?",
        "expected_tool": "tool_lista_productos",
    },
    {
        "name": "Top producto",
        "question": "¿Cuál es el producto más vendido?",
        "expected_tool": "tool_producto_mas_vendido",
    },
    {
        "name": "Memoria conversacional",
        "question": "¿Y ella cuánto vendió en marzo?",
        "expected_tool": "tool_ventas_vendedor_por_mes",
        "history": [
            {"role": "user", "content": "¿Quién vendió más?"},
            {"role": "assistant", "content": "Laura Fernández vendió $414,412"},
        ]
    },
    {
        "name": "Resumen ejecutivo",
        "question": "Dame un resumen general de las ventas",
        "expected_tool": "tool_resumen_general",
    },
]

# ── Ejecutar tests ────────────────────────────────────────────────────────────

def run_tests():
    print("=" * 70)
    print("🧪 SALES AGENT - LANGSMITH TEST SUITE")
    print("=" * 70)
    print(f"📊 Proyecto LangSmith: {os.getenv('LANGCHAIN_PROJECT', 'default')}")
    print(f"🔑 Tracing activo: {os.getenv('LANGCHAIN_TRACING_V2', 'false')}")
    print("=" * 70)

    results = []

    for i, test in enumerate(TESTS, 1):
        print(f"\n[{i}/{len(TESTS)}] 📝 {test['name']}")
        print(f"    Pregunta: {test['question']}")

        history = test.get("history", [])
        start = time.perf_counter()

        try:
            answer = run_agent(question=test["question"], history=history)
            elapsed = time.perf_counter() - start

            # Verificar que no sea una alucinación (debe contener datos o $)
            has_data = any(char.isdigit() for char in answer) or "$" in answer

            status = "✅ PASS" if has_data else "⚠️  REVISAR (sin datos?)"
            print(f"    {status} | ⏱️  {elapsed:.2f}s")
            print(f"    Respuesta: {answer[:120]}...")

            results.append({
                "name": test["name"],
                "status": "PASS" if has_data else "REVIEW",
                "latency": elapsed,
                "expected_tool": test["expected_tool"],
            })

        except Exception as e:
            elapsed = time.perf_counter() - start
            print(f"    ❌ FAIL | ⏱️  {elapsed:.2f}s | Error: {str(e)[:80]}")
            results.append({
                "name": test["name"],
                "status": "FAIL",
                "latency": elapsed,
                "error": str(e),
            })

    # ── Resumen ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("📈 RESUMEN")
    print("=" * 70)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    review = sum(1 for r in results if r["status"] == "REVIEW")
    avg_latency = sum(r["latency"] for r in results) / len(results)

    print(f"✅ Pass:     {passed}/{len(results)}")
    print(f"⚠️  Revisar:  {review}/{len(results)}")
    print(f"❌ Fail:     {failed}/{len(results)}")
    print(f"⏱️  Latencia promedio: {avg_latency:.2f}s")

    print("\n🌐 Abre LangSmith para ver los traces detallados:")
    print(f"   https://smith.langchain.com/o/{os.getenv('LANGCHAIN_API_KEY', 'tu-org')[:8]}...")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()