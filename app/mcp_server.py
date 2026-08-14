"""
Servidor MCP (Model Context Protocol) para el Sales Intelligence Agent.

Expone las mismas 9 funciones de análisis de app/tools.py como "tools" MCP,
de forma que cualquier cliente MCP (Claude Desktop, Claude.ai, Cursor, otro
agente) pueda consultarlas directamente, sin pasar por LangGraph.

Reutiliza tools.py sin modificarlo: la separación entre lógica de negocio
(pandas) y framework de orquestación (antes LangGraph, ahora también MCP)
es exactamente el principio de decoupling que ya tenía el proyecto.

Transportes soportados (se elige por variable de entorno MCP_TRANSPORT):
  - stdio          → uso local (Claude Desktop, Cursor, mcp dev inspector)
  - streamable-http → uso remoto vía HTTP (Cloud Run u otro host)

Uso local:
    python -m app.mcp_server

Uso remoto (HTTP en el puerto 8080, el que espera Cloud Run):
    MCP_TRANSPORT=streamable-http PORT=8080 python -m app.mcp_server
"""

import os
import json
import secrets

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.tools import (
    ventas_por_vendedor,
    ventas_por_categoria,
    ventas_por_region,
    ventas_por_mes,
    ventas_vendedor_por_mes,
    ventas_producto_por_region,
    lista_productos,
    producto_mas_vendido,
    resumen_general,
)

# ── Instancia del servidor ───────────────────────────────────────────────────
# El nombre es lo que ve el usuario en el cliente MCP (ej. lista de conectores
# en Claude Desktop), y las instrucciones cumplen el mismo rol que el
# SYSTEM_PROMPT de agent_langgraph.py: orientan al LLM sobre cuándo y cómo
# usar estas tools.
mcp = FastMCP(
    name="sales-intelligence-agent",
    instructions=(
        "Herramientas de análisis sobre un dataset de ventas (~15K transacciones, "
        "$16M+ en ingresos). Usalas para responder preguntas sobre rendimiento de "
        "vendedores, categorías, regiones y productos. Si la pregunta usa pronombres "
        "(el, ella, ese producto), identificá primero a qué vendedor o producto se "
        "refiere antes de llamar a la tool correspondiente."
    ),
)


# ── Tools ─────────────────────────────────────────────────────────────────────
# Cada función es un wrapper delgado sobre tools.py. El docstring es la
# descripción que el LLM cliente va a leer para decidir si la usa: mantené
# el mismo nivel de detalle que ya usaste en agent_langgraph.py.

@mcp.tool()
def tool_ventas_por_vendedor() -> str:
    """Obtiene el total de ventas en pesos agrupado por vendedor.
    Útil para comparar rendimiento del equipo comercial."""
    return json.dumps(ventas_por_vendedor(), ensure_ascii=False)


@mcp.tool()
def tool_ventas_por_categoria() -> str:
    """Obtiene el total de ventas agrupado por categoría de producto."""
    return json.dumps(ventas_por_categoria(), ensure_ascii=False)


@mcp.tool()
def tool_ventas_por_region() -> str:
    """Obtiene el total de ventas agrupado por región geográfica (Norte, Sur, Centro)."""
    return json.dumps(ventas_por_region(), ensure_ascii=False)


@mcp.tool()
def tool_ventas_por_mes() -> str:
    """Obtiene la evolución de ventas mes a mes. Útil para detectar tendencias temporales."""
    return json.dumps(ventas_por_mes(), ensure_ascii=False)


@mcp.tool()
def tool_ventas_vendedor_por_mes(vendedor: str) -> str:
    """Obtiene las ventas mes a mes de un vendedor específico.
    Usar cuando pregunten cuánto vendió una persona en un mes."""
    return json.dumps(ventas_vendedor_por_mes(vendedor), ensure_ascii=False)


@mcp.tool()
def tool_ventas_por_producto(producto: str) -> str:
    """Obtiene en qué regiones se vende un producto específico, con unidades y
    pesos por región. Usar cuando pregunten dónde se vende un producto."""
    return json.dumps(ventas_producto_por_region(producto), ensure_ascii=False)


@mcp.tool()
def tool_lista_productos() -> str:
    """Lista todos los productos que vende la tienda con nombre, categoría y
    unidades vendidas. Usar cuando pregunten qué productos vende la tienda o
    cuántos productos distintos hay."""
    return json.dumps(lista_productos(), ensure_ascii=False)


@mcp.tool()
def tool_producto_mas_vendido() -> str:
    """Obtiene el producto con mayor cantidad de unidades vendidas en todo el período."""
    return json.dumps(producto_mas_vendido(), ensure_ascii=False)


@mcp.tool()
def tool_resumen_general() -> str:
    """Obtiene un resumen ejecutivo: ingresos totales, ticket promedio,
    cantidad de transacciones."""
    return json.dumps(resumen_general(), ensure_ascii=False)


# ── Autenticación (solo aplica al transporte HTTP remoto) ────────────────────
# El modo stdio NO pasa por acá: ese transporte ya es inherentemente privado
# (Claude Desktop lanza el proceso directamente en tu máquina, no hay red de
# por medio). El bearer token solo tiene sentido cuando el servidor escucha
# en un puerto abierto a internet, como va a pasar en Cloud Run.

class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Exige el header 'Authorization: Bearer <token>' en cada request.
    Usa secrets.compare_digest para comparar el token de forma segura contra
    ataques de timing (comparar strings con '==' filtra cuántos caracteres
    coinciden por el tiempo que tarda la comparación)."""

    def __init__(self, app, expected_token: str):
        super().__init__(app)
        self.expected_header = f"Bearer {expected_token}"

    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("authorization", "")
        if not secrets.compare_digest(auth_header, self.expected_header):
            return JSONResponse(
                {"error": "unauthorized", "detail": "Falta o es inválido el header Authorization: Bearer <token>"},
                status_code=401,
            )
        return await call_next(request)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")

    if transport == "stdio":
        # Uso local: Claude Desktop/Cursor lanzan este proceso y hablan
        # con él por stdin/stdout. No abre ningún puerto de red.
        mcp.run(transport="stdio")
    elif transport == "streamable-http":
        # Uso remoto: levanta un servidor HTTP real, protegido con bearer
        # token. Cloud Run inyecta el puerto en la variable de entorno PORT.
        import uvicorn

        auth_token = os.environ.get("MCP_AUTH_TOKEN")
        if not auth_token:
            raise RuntimeError(
                "Falta la variable de entorno MCP_AUTH_TOKEN. "
                "El servidor remoto no puede arrancar sin un token configurado "
                "(evita que quede expuesto sin protección por accidente)."
            )

        http_app = mcp.streamable_http_app()
        http_app.add_middleware(BearerAuthMiddleware, expected_token=auth_token)

        port = int(os.getenv("PORT", "8080"))
        uvicorn.run(http_app, host="0.0.0.0", port=port)
    else:
        raise ValueError(f"MCP_TRANSPORT desconocido: {transport}")