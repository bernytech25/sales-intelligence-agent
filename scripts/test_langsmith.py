"""
Test suite para evaluar el Sales Agent con trazabilidad en LangSmith.

Requisitos:
- Tener LANGCHAIN_TRACING_V2=true en tu .env
- Tener LANGCHAIN_API_KEY y LANGCHAIN_PROJECT configurados

Uso:
    python test_langsmith.py

Esto ejecuta 12 preguntas contra el agente real (10 evaluadas + 1 caso
negativo + 1 límite conocido informativo) y evalúa dos cosas de forma
automática (no solo "no tiró excepción"):
  1. Tool selection accuracy: ¿el agente llamó a la tool esperada?
  2. Groundedness (heurística básica): ¿la respuesta contiene datos
     concretos (números/$) en vez de una respuesta vacía o evasiva?
Los traces completos, con el detalle de grounding real contra el output
de cada tool, quedan disponibles en LangSmith si el tracing está activo.
"""

import sys
import os
import time

# Agregar la carpeta padre al path para poder importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent_langgraph import run_agent

# ── Preguntas de test ─────────────────────────────────────────────────────────

TESTS = [
    {
        "name": "Ranking general",
        "question": "¿Quién vendió más?",
        # Sin filtro de fecha, el LLM elige indistintamente entre la tool
        # específica y la general (evidencia de que son redundantes —
        # candidata a fusionar ventas_por_vendedor como wrapper de
        # vendedor_ranking_periodo sin rango). Se acepta cualquiera de las dos
        # mientras no se fusionen en código.
        "expected_tool": ["tool_ventas_por_vendedor", "tool_vendedor_ranking_periodo"],
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
        "question": "¿Cuánto vendió Ana García en febrero?",
        "expected_tool": "tool_ventas_vendedor_por_mes",
    },
    {
        "name": "Producto + región",
        # Antes decía "Laptop Dell XPS", que no existe en el catálogo real
        # (data/ventas.csv) — probaba sin querer el camino de error, no el
        # camino feliz. "Laptop Pro" sí existe.
        "question": "¿En qué región se vende más el producto Laptop Pro?",
        "expected_tool": "tool_ventas_por_producto",
    },
    {
        "name": "Producto inexistente (caso negativo)",
        # Ahora el caso de error queda como test explícito: se espera que
        # la tool avise que no encontró el producto, no que traiga datos.
        "question": "¿En qué región se vende más el producto Laptop Dell XPS?",
        "expected_tool": "tool_ventas_por_producto",
        "expect_not_found": True,
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
    {
        "name": "Meses no contiguos (límite conocido)",
        # No hay tool para comparar meses puntuales no contiguos; el agente
        # aproxima con vendedor_ranking_periodo, tratando "mayo y octubre"
        # como si fuera "mayo a octubre" (6 meses), sin avisarlo. No hay
        # tool correcta para exigir todavía, así que este caso no cuenta
        # para pass/fail — queda como registro del gap hasta que se
        # resuelva (prompt más explícito o tool de meses puntuales).
        "question": "¿Quién vendió más en mayo y octubre?",
        "known_limitation": True,
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
            trace = run_agent(question=test["question"], history=history, return_trace=True)
            elapsed = time.perf_counter() - start
            answer = trace["answer"]
            tools_called = trace["tools_called"]

            # Caso informativo: sin tool correcta disponible todavía, no se
            # evalúa pass/fail — solo se imprime la respuesta para revisión manual.
            if test.get("known_limitation"):
                print(f"    ℹ️  INFO (límite conocido, no cuenta para pass/fail) | ⏱️  {elapsed:.2f}s")
                print(f"    Respuesta: {answer[:200]}...")
                results.append({"name": test["name"], "status": "INFO", "latency": elapsed})
                continue

            expected = test["expected_tool"]
            expected_set = expected if isinstance(expected, list) else [expected]
            tool_correct = any(t in tools_called for t in expected_set)

            if test.get("expect_not_found"):
                # Caso negativo: se espera que el agente avise que no
                # encontró el dato, no que traiga datos concretos.
                not_found_ok = any(
                    kw in answer.lower()
                    for kw in ["no encontr", "no se encuentra", "no está en", "no disponible", "no existe"]
                )
                ok = tool_correct and not_found_ok
                status = "✅ PASS" if ok else f"❌ FAIL (se esperaba un mensaje de 'no encontrado')"
                print(f"    {status} | ⏱️  {elapsed:.2f}s")
                print(f"    Respuesta: {answer[:120]}...")
                results.append({
                    "name": test["name"], "status": "PASS" if ok else "FAIL",
                    "latency": elapsed, "expected_tool": expected_set, "tools_called": tools_called,
                })
                continue

            # Groundedness heurístico: la respuesta debe traer datos concretos.
            has_data = any(char.isdigit() for char in answer) or "$" in answer

            if tool_correct and has_data:
                status = "✅ PASS"
            elif not tool_correct:
                status = f"❌ FAIL (llamó {tools_called or 'ninguna tool'}, esperaba {expected_set})"
            else:
                status = "⚠️  REVISAR (sin datos concretos en la respuesta)"

            print(f"    {status} | ⏱️  {elapsed:.2f}s")
            print(f"    Respuesta: {answer[:120]}...")

            results.append({
                "name": test["name"],
                "status": "PASS" if (tool_correct and has_data) else ("FAIL" if not tool_correct else "REVIEW"),
                "latency": elapsed,
                "expected_tool": expected_set,
                "tools_called": tools_called,
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
    info = sum(1 for r in results if r["status"] == "INFO")
    scored = [r for r in results if r["status"] != "INFO"]
    avg_latency = sum(r["latency"] for r in results) / len(results)
    tool_correct_count = sum(
        1 for r in scored
        if "tools_called" in r and any(t in r["tools_called"] for t in r["expected_tool"])
    )

    print(f"✅ Pass:     {passed}/{len(scored)}")
    print(f"⚠️  Revisar:  {review}/{len(scored)}")
    print(f"❌ Fail:     {failed}/{len(scored)}")
    if info:
        print(f"ℹ️  Info (límites conocidos, no puntúan): {info}")
    print(f"🎯 Tool selection accuracy: {tool_correct_count}/{len(scored)}")
    print(f"⏱️  Latencia promedio: {avg_latency:.2f}s")

    print("\n🌐 Abre LangSmith para ver los traces detallados:")
    print(f"   https://smith.langchain.com/o/{os.getenv('LANGCHAIN_API_KEY', 'tu-org')[:8]}...")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    import sys
    ok = run_tests()
    sys.exit(0 if ok else 1)