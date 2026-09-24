"""
Agente de análisis de ventas - LangGraph + Gemini
"""

import os
import json
from typing import TypedDict, Annotated

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from app.tools import (
    ventas_por_vendedor,
    ventas_por_categoria,
    ventas_por_region,
    ventas_por_mes,
    ventas_vendedor_por_mes,
    vendedor_ranking_periodo,
    ventas_producto_por_region,
    ranking_vendedores_por_region,
    ranking_productos_por_region,
    analisis_vendedores_y_productos_por_region,
    lista_productos,
    producto_mas_vendido,
    resumen_general,
)
from app.prompts import SALES_AGENT_SYSTEM_PROMPT

load_dotenv()

# ── Estado ────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# ── Tools ─────────────────────────────────────────────────────────────────────

@tool
def tool_ventas_por_vendedor() -> str:
    """Obtiene el total de ventas en pesos agrupado por vendedor. Útil para comparar rendimiento del equipo comercial."""
    return json.dumps(ventas_por_vendedor(), ensure_ascii=False)

@tool
def tool_ventas_por_categoria() -> str:
    """Obtiene el total de ventas agrupado por categoría de producto."""
    return json.dumps(ventas_por_categoria(), ensure_ascii=False)

@tool
def tool_ventas_por_region() -> str:
    """Obtiene el total de ventas agrupado por región geográfica (Norte, Sur, Centro, Este, Oeste)."""
    return json.dumps(ventas_por_region(), ensure_ascii=False)

@tool
def tool_ventas_por_mes() -> str:
    """Obtiene la evolución de ventas mes a mes. Útil para detectar tendencias temporales."""
    return json.dumps(ventas_por_mes(), ensure_ascii=False)

@tool
def tool_ventas_vendedor_por_mes(vendedor: str) -> str:
    """Obtiene las ventas mes a mes de un vendedor específico. Usar cuando pregunten cuánto vendió una persona en un mes."""
    return json.dumps(ventas_vendedor_por_mes(vendedor), ensure_ascii=False)

@tool
def tool_vendedor_ranking_periodo(mes_desde: str, mes_hasta: str, orden: str = "desc") -> str:
    """Rankea vendedores por ventas totales en un rango de meses (formato YYYY-MM, ej.
    mes_desde='2024-10' mes_hasta='2024-12' para el último trimestre). orden='desc' da el
    que más vendió primero; orden='asc' da el que menos vendió primero. Usar para
    '¿quién vendió más/menos en los últimos N meses?' en una sola llamada, en vez de
    consultar vendedor por vendedor o mes por mes."""
    return json.dumps(vendedor_ranking_periodo(mes_desde, mes_hasta, orden), ensure_ascii=False)

@tool
def tool_ventas_por_producto(producto: str) -> str:
    """Obtiene en qué regiones se vende un producto específico con unidades y pesos por región. Usar cuando pregunten dónde se vende un producto."""
    return json.dumps(ventas_producto_por_region(producto), ensure_ascii=False)

@tool
def tool_ranking_vendedores_por_region(top_n: int = 5, metrica: str = "total", mes_desde: str | None = None, mes_hasta: str | None = None) -> str:
    """Obtiene los vendedores con mejor desempeño dentro de cada región en una sola consulta.
    Usar cuando pregunten quiénes son los vendedores que más o menos vendieron por región.
    metrica='total' ordena por facturación y metrica='cantidad' por unidades."""
    return json.dumps(ranking_vendedores_por_region(top_n, metrica, mes_desde, mes_hasta), ensure_ascii=False)

@tool
def tool_ranking_productos_por_region(top_n: int = 5, metrica: str = "cantidad", mes_desde: str | None = None, mes_hasta: str | None = None) -> str:
    """Obtiene los productos más vendidos dentro de cada región en una sola consulta.
    Usar cuando pregunten cuáles productos lideran por región.
    metrica='cantidad' ordena por unidades y metrica='total' por facturación."""
    return json.dumps(ranking_productos_por_region(top_n, metrica, mes_desde, mes_hasta), ensure_ascii=False)

@tool
def tool_analisis_vendedores_y_productos_por_region(
    mes_desde: str,
    mes_hasta: str,
    top_vendedores: int = 1,
    top_productos: int = 3,
    metrica_vendedor: str = "total",
    metrica_producto: str = "cantidad",
) -> str:
    """Relaciona los vendedores líderes de cada región con los productos que ellos mismos vendieron más.
    Usar para preguntas como: 'en septiembre, quién vendió más por región y qué artículos vendió'.
    mes_desde y mes_hasta usan YYYY-MM e incluyen ambos meses."""
    return json.dumps(
        analisis_vendedores_y_productos_por_region(
            mes_desde, mes_hasta, top_vendedores, top_productos,
            metrica_vendedor, metrica_producto,
        ),
        ensure_ascii=False,
    )

@tool
def tool_lista_productos() -> str:
    """Lista todos los productos que vende la tienda con nombre, categoría y unidades vendidas. Usar cuando pregunten qué productos vende la tienda o cuántos productos distintos hay."""
    return json.dumps(lista_productos(), ensure_ascii=False)

@tool
def tool_producto_mas_vendido() -> str:
    """Obtiene el producto con mayor cantidad de unidades vendidas en todo el período."""
    return json.dumps(producto_mas_vendido(), ensure_ascii=False)

@tool
def tool_resumen_general() -> str:
    """Obtiene un resumen ejecutivo: ingresos totales, ticket promedio, cantidad de transacciones."""
    return json.dumps(resumen_general(), ensure_ascii=False)

TOOLS = [
    tool_ventas_por_vendedor,
    tool_ventas_por_categoria,
    tool_ventas_por_region,
    tool_ventas_por_mes,
    tool_ventas_vendedor_por_mes,
    tool_vendedor_ranking_periodo,
    tool_ventas_por_producto,
    tool_ranking_vendedores_por_region,
    tool_ranking_productos_por_region,
    tool_analisis_vendedores_y_productos_por_region,
    tool_lista_productos,
    tool_producto_mas_vendido,
    tool_resumen_general,
]

TOOLS_MAP = {t.name: t for t in TOOLS}

# ── LLM ───────────────────────────────────────────────────────────────────────

def get_llm():
    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
    )
    return llm.bind_tools(TOOLS)

# ── Nodos ─────────────────────────────────────────────────────────────────────

def node_llm(state: AgentState) -> AgentState:
    llm = get_llm()
    messages = [SystemMessage(content=SALES_AGENT_SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

def node_tools(state: AgentState) -> AgentState:
    last_message = state["messages"][-1]
    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_fn = TOOLS_MAP[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        tool_results.append(ToolMessage(
            content=result,
            tool_call_id=tool_call["id"],
            name=tool_call["name"],
        ))
    return {"messages": tool_results}

def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# ── Grafo ─────────────────────────────────────────────────────────────────────

def build_agent():
    graph = StateGraph(AgentState)
    graph.add_node("llm", node_llm)
    graph.add_node("tools", node_tools)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_continue)
    graph.add_edge("tools", "llm")
    return graph.compile()

_agent = build_agent()

# ── Función pública ───────────────────────────────────────────────────────────

def _enrich_question(question: str, history: list[dict]) -> str:
    if not history:
        return question
    # Búsqueda case-insensitive que incluye variantes con/sin acentos
    question_lower = question.lower()
    referencias = [
        "cuanto vendi", "cuánto vendi",  # vendió/vendio
        "cuanto gano", "cuánto gan",     # ganó/gano
        "y ella", "y el ",               # espacio después de "el" para evitar "tienda"
        "ese mes", "ese producto", "esa region", "esa persona",
    ]
    if not any(ref in question_lower for ref in referencias):
        return question
    ultimas = [m["content"] for m in history if m["role"] == "assistant"]
    if not ultimas:
        return question
    return f"{question} (Contexto: {ultimas[-1][:300]})"

MAX_HISTORY = 10

def _truncate_history(history: list[dict]) -> list[dict]:
    if len(history) <= MAX_HISTORY:
        return history
    return history[-MAX_HISTORY:]


def _extract_answer(result: dict) -> str:
    """Extrae texto de la respuesta del agente. Solo Gemini (list)."""
    content = result["messages"][-1].content

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                texts.append(part.get("text", ""))
            else:
                texts.append(str(part))
        return " ".join(texts)

    return str(content)


def run_agent(question: str, history: list[dict] | None = None, return_trace: bool = False):
    """Runs the agent. By default returns just the answer string (backward
    compatible with main.py). Pass return_trace=True to also get back which
    tools were actually called, for automated tool-selection evaluation."""
    history = history or []
    history = _truncate_history(history)
    enriched = _enrich_question(question, history)
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=enriched))
    result = _agent.invoke({"messages": messages})
    answer = _extract_answer(result)

    if not return_trace:
        return answer

    tools_called = [
        m.name for m in result["messages"]
        if isinstance(m, ToolMessage)
    ]
    return {"answer": answer, "tools_called": tools_called}
