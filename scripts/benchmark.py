"""
Benchmark: LangGraph + Groq vs Semantic Kernel + Azure OpenAI
Hace las mismas 10 preguntas a ambas APIs, mide latencia real,
y genera una tabla comparativa + exporta CSV con los resultados.

Uso:
    python benchmark.py

Requisitos:
    pip install httpx rich pandas
"""

import time
import json
import csv
from datetime import datetime
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table
from rich import box

# ── Configuración ─────────────────────────────────────────────────────────────

LANGGRAPH_URL = "http://localhost:8000"
SK_URL = "http://localhost:8001"

CREDENTIALS = {
    "username": "admin",
    "password": "admin123",
}

SESSION_ID = f"benchmark-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# 10 preguntas idénticas para ambos sistemas
QUESTIONS = [
    "¿Cuál es el resumen general de ventas?",
    "¿Quién vendió más?",
    "¿Qué región vendió más?",
    "¿Cuál es el producto más vendido?",
    "¿Quién vendió menos y por qué crees que fue así?",
    "¿Qué productos vende la tienda?",
    "¿Cuánto vendió Ana en febrero?",
    "¿En qué región se vende más el producto más vendido?",
    "Si tuvieras que recomendar una acción para mejorar las ventas, ¿cuál sería?",
]

console = Console()


# ── Autenticación ─────────────────────────────────────────────────────────────

def get_token(base_url: str, name: str) -> str | None:
    """Obtiene el JWT token para autenticarse."""
    try:
        response = httpx.post(
            f"{base_url}/auth/token",
            data=CREDENTIALS,
            timeout=15,
        )
        if response.status_code == 200:
            token = response.json()["access_token"]
            console.print(f"  ✅ [{name}] Token obtenido", style="green")
            return token
        else:
            console.print(f"  ❌ [{name}] Error de autenticación: {response.status_code}", style="red")
            return None
    except Exception as e:
        console.print(f"  ❌ [{name}] No se pudo conectar: {e}", style="red")
        return None


# ── Request al agente ─────────────────────────────────────────────────────────

def ask_agent(base_url: str, token: str, question: str, session_id: str) -> dict:
    """
    Hace una pregunta al agente y retorna latencia + respuesta.
    Usa /chat (in-session) para que el historial se acumule entre preguntas
    y podamos probar la memoria conversacional.
    """
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"session_id": session_id, "question": question}

    start = time.perf_counter()
    try:
        response = httpx.post(
            f"{base_url}/chat",
            json=payload,
            headers=headers,
            timeout=60,
        )
        elapsed = time.perf_counter() - start

        if response.status_code == 200:
            data = response.json()
            return {
                "ok": True,
                "latency": round(elapsed, 2),
                "answer": data.get("answer", "")[:120],  # primeros 120 chars
                "status": response.status_code,
            }
        else:
            return {
                "ok": False,
                "latency": round(elapsed, 2),
                "answer": f"Error {response.status_code}",
                "status": response.status_code,
            }
    except httpx.TimeoutException:
        elapsed = time.perf_counter() - start
        return {"ok": False, "latency": round(elapsed, 2), "answer": "TIMEOUT", "status": 0}
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"ok": False, "latency": round(elapsed, 2), "answer": str(e)[:80], "status": 0}


# ── Benchmark principal ───────────────────────────────────────────────────────

def run_benchmark():
    console.print("\n")
    console.rule("[bold blue]🚀 Sales Agent Benchmark — LangGraph vs Semantic Kernel[/bold blue]")
    console.print(f"\n📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print(f"🔑 Session ID: {SESSION_ID}")
    console.print(f"❓ Preguntas: {len(QUESTIONS)}\n")

    # Autenticación
    console.print("[bold]Autenticando...[/bold]")
    lg_token = get_token(LANGGRAPH_URL, "LangGraph")
    sk_token = get_token(SK_URL, "Semantic Kernel")

    if not lg_token or not sk_token:
        console.print("\n❌ No se pudo autenticar en uno o ambos servidores. Verificá que estén corriendo.", style="red bold")
        return

    console.print()

    # Resultados
    results = []
    lg_latencies = []
    sk_latencies = []
    lg_ok = 0
    sk_ok = 0

    for i, question in enumerate(QUESTIONS, 1):
        console.print(f"[dim]Pregunta {i}/{len(QUESTIONS)}:[/dim] {question[:60]}...")

        # LangGraph
        lg_result = ask_agent(LANGGRAPH_URL, lg_token, question, f"{SESSION_ID}-lg")
        if lg_result["ok"]:
            lg_latencies.append(lg_result["latency"])
            lg_ok += 1

        # Pequeña para respetar el rate limit de Azure OpenAI Standard (6 RPM = 10s entre requests)
        time.sleep(15)

        # Semantic Kernel
        sk_result = ask_agent(SK_URL, sk_token, question, f"{SESSION_ID}-sk")
        if sk_result["ok"]:
            sk_latencies.append(sk_result["latency"])
            sk_ok += 1

        results.append({
            "pregunta": i,
            "texto": question[:50],
            "lg_latencia": lg_result["latency"],
            "lg_ok": "✅" if lg_result["ok"] else "❌",
            "sk_latencia": sk_result["latency"],
            "sk_ok": "✅" if sk_result["ok"] else "✅",
            "diferencia": round(sk_result["latency"] - lg_result["latency"], 2),
            "lg_answer": lg_result["answer"],
            "sk_answer": sk_result["answer"],
        })

        # Mostrar resultado en tiempo real
        diff = sk_result["latency"] - lg_result["latency"]
        winner = "🟢 LangGraph" if lg_result["latency"] < sk_result["latency"] else "🔵 SK"
        console.print(
            f"  LangGraph: [green]{lg_result['latency']}s[/green]  |  "
            f"SK: [blue]{sk_result['latency']}s[/blue]  |  "
            f"Ganador: {winner}  ({abs(diff):.2f}s diff)"
        )

    # ── Tabla de resultados ───────────────────────────────────────────────────
    console.print("\n")
    console.rule("[bold]📊 Resultados por Pregunta[/bold]")
    console.print()

    table = Table(box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Pregunta", width=35)
    table.add_column("LangGraph\n(Groq)", justify="center", style="green", width=12)
    table.add_column("Semantic Kernel\n(Azure OpenAI)", justify="center", style="blue", width=16)
    table.add_column("Diferencia", justify="center", width=10)
    table.add_column("Ganador", justify="center", width=12)

    for r in results:
        diff = r["diferencia"]
        winner = "🟢 LG" if diff > 0 else "🔵 SK"
        diff_str = f"+{diff}s" if diff > 0 else f"{diff}s"
        table.add_row(
            str(r["pregunta"]),
            r["texto"],
            f"{r['lg_latencia']}s {r['lg_ok']}",
            f"{r['sk_latencia']}s {r['sk_ok']}",
            diff_str,
            winner,
        )

    console.print(table)

    # ── Resumen estadístico ───────────────────────────────────────────────────
    console.print()
    console.rule("[bold]📈 Resumen Estadístico[/bold]")
    console.print()

    lg_avg = round(sum(lg_latencies) / len(lg_latencies), 2) if lg_latencies else 0
    sk_avg = round(sum(sk_latencies) / len(sk_latencies), 2) if sk_latencies else 0
    lg_min = round(min(lg_latencies), 2) if lg_latencies else 0
    sk_min = round(min(sk_latencies), 2) if sk_latencies else 0
    lg_max = round(max(lg_latencies), 2) if lg_latencies else 0
    sk_max = round(max(sk_latencies), 2) if sk_latencies else 0
    lg_total = round(sum(lg_latencies), 2) if lg_latencies else 0
    sk_total = round(sum(sk_latencies), 2) if sk_latencies else 0

    summary = Table(box=box.ROUNDED)
    summary.add_column("Métrica", style="bold")
    summary.add_column("LangGraph + Groq", justify="center", style="green")
    summary.add_column("Semantic Kernel + Azure OpenAI", justify="center", style="blue")
    summary.add_column("Diferencia", justify="center")

    summary.add_row("LLM", "Groq LLaMA 3.3-70b", "Azure OpenAI gpt-4o", "—")
    summary.add_row("Requests exitosos", f"{lg_ok}/{len(QUESTIONS)}", f"{sk_ok}/{len(QUESTIONS)}", "—")
    summary.add_row("Latencia promedio", f"{lg_avg}s", f"{sk_avg}s", f"{round(sk_avg - lg_avg, 2)}s")
    summary.add_row("Latencia mínima", f"{lg_min}s", f"{sk_min}s", f"{round(sk_min - lg_min, 2)}s")
    summary.add_row("Latencia máxima", f"{lg_max}s", f"{sk_max}s", f"{round(sk_max - lg_max, 2)}s")
    summary.add_row("Tiempo total", f"{lg_total}s", f"{sk_total}s", f"{round(sk_total - lg_total, 2)}s")
    summary.add_row("Costo estimado", "~$0.00 (Groq gratuito)", "~$0.003-0.008 (gpt-4o)", "—")

    console.print(summary)

    # ── Veredicto ─────────────────────────────────────────────────────────────
    console.print()
    console.rule("[bold]🏆 Veredicto[/bold]")
    console.print()

    if lg_avg < sk_avg:
        faster = "LangGraph + Groq"
        diff_pct = round((sk_avg - lg_avg) / sk_avg * 100, 1)
        console.print(f"  🟢 [green bold]{faster}[/green bold] fue más rápido en promedio ({diff_pct}% más rápido)")
    else:
        faster = "Semantic Kernel + Azure OpenAI"
        diff_pct = round((lg_avg - sk_avg) / lg_avg * 100, 1)
        console.print(f"  🔵 [blue bold]{faster}[/blue bold] fue más rápido en promedio ({diff_pct}% más rápido)")

    console.print(f"  💰 Costo: LangGraph/Groq = $0.00  |  SK/Azure OpenAI = ~${round(sk_total * 0.0003, 4)} estimado")
    console.print(f"  🧠 Calidad: revisar LangSmith (LangGraph) y Azure AI Foundry (SK) para comparar respuestas\n")

    # ── Exportar CSV ──────────────────────────────────────────────────────────
    output_file = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pregunta", "texto", "lg_latencia", "lg_ok",
            "sk_latencia", "sk_ok", "diferencia", "lg_answer", "sk_answer"
        ])
        writer.writeheader()
        writer.writerows(results)

    console.print(f"  💾 Resultados exportados a: [bold]{output_file}[/bold]\n")


if __name__ == "__main__":
    run_benchmark()