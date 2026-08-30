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
import time
import asyncio
from collections import defaultdict

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.tools import (
    ventas_por_vendedor,
    ventas_por_categoria,
    ventas_por_region,
    ventas_por_mes,
    ventas_vendedor_por_mes,
    vendedor_ranking_periodo,
    ventas_producto_por_region,
    lista_productos,
    producto_mas_vendido,
    resumen_general,
)
from app.prompts import MCP_SERVER_INSTRUCTIONS

# ── Instancia del servidor ───────────────────────────────────────────────────
# El nombre es lo que ve el usuario en el cliente MCP (ej. lista de conectores
# en Claude Desktop). Las instrucciones vienen de app/prompts.py, que también
# usa agent_langgraph.py -- así la regla de resolución de pronombres no se
# desincroniza entre los dos consumidores.
def _allowed_hosts() -> list[str]:
    """Hosts permitidos para el header Host (protección DNS rebinding del SDK).
    El SDK exige coincidencia EXACTA (no wildcards de subdominio tipo *.run.app),
    así que el host real de Cloud Run se pasa por la variable ALLOWED_HOST en
    el momento del deploy (--set-env-vars ALLOWED_HOST=<tu-url>.run.app)."""
    hosts = ["127.0.0.1", "127.0.0.1:8080", "localhost", "localhost:8080"]
    extra = os.environ.get("ALLOWED_HOST")
    if extra:
        hosts.append(extra)
    return hosts


mcp = FastMCP(
    name="sales-intelligence-agent",
    instructions=MCP_SERVER_INSTRUCTIONS,
    transport_security=TransportSecuritySettings(allowed_hosts=_allowed_hosts()),
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
def tool_vendedor_ranking_periodo(mes_desde: str, mes_hasta: str, orden: str = "desc") -> str:
    """Rankea vendedores por ventas totales en un rango de meses (formato
    YYYY-MM, ej. mes_desde='2024-10' mes_hasta='2024-12' para el último
    trimestre). orden='desc' da el que más vendió primero; orden='asc' da el
    que menos vendió primero. Usar para '¿quién vendió más/menos en los
    últimos N meses?' en una sola llamada, en vez de consultar vendedor por
    vendedor o mes por mes."""
    return json.dumps(vendedor_ranking_periodo(mes_desde, mes_hasta, orden), ensure_ascii=False)


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

class AuthAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Exige el header 'Authorization: Bearer <token>' en cada request, y
    aplica rate limiting por token (60 requests/minuto por default).

    Nota de diseño importante sobre por qué esto va en un solo middleware
    y no en dos separados: el orden de ejecución entre varios middlewares
    de Starlette depende del orden en que se agregan (el último agregado
    se ejecuta primero), lo cual es fácil de mezclar mal. Combinarlos acá
    evita esa fuente de bugs -- primero valida el token, y solo si es
    válido cuenta ese request contra el límite de ESE token específico
    (un token inválido no debería "gastar" cupo de nadie).

    Limitación conocida: el contador vive en memoria del proceso. Si Cloud
    Run escala a más de una instancia, cada una lleva su propio conteo por
    separado -- el límite real termina siendo N x 60/min en vez de 60/min
    total, donde N es la cantidad de instancias activas. Para un límite
    estricto de verdad en múltiples instancias, el siguiente paso sería
    mover el contador a Memorystore (Redis) en vez de memoria local."""

    def __init__(self, app, expected_token: str, requests_per_minute: int = 60):
        super().__init__(app)
        self.expected_header = f"Bearer {expected_token}"
        self.limit = requests_per_minute
        self.window_seconds = 60
        self._requests_by_token: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(self, request, call_next):
        auth_header = request.headers.get("authorization", "")
        if not secrets.compare_digest(auth_header, self.expected_header):
            return JSONResponse(
                {"error": "unauthorized", "detail": "Falta o es inválido el header Authorization: Bearer <token>"},
                status_code=401,
            )

        # Usamos el propio token como clave -- hoy hay un solo token, pero
        # esto ya queda preparado para el día que existan varios (uno por
        # cliente), sin tener que rediseñar el rate limiting.
        token_key = auth_header
        now = time.monotonic()

        async with self._lock:
            timestamps = self._requests_by_token[token_key]
            # Descartar timestamps fuera de la ventana de 60s
            cutoff = now - self.window_seconds
            timestamps[:] = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self.limit:
                retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
                return JSONResponse(
                    {
                        "error": "rate_limited",
                        "detail": f"Límite de {self.limit} requests/minuto excedido. Reintentar en {retry_after}s.",
                    },
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

            timestamps.append(now)

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
        requests_per_minute = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))
        http_app.add_middleware(
            AuthAndRateLimitMiddleware,
            expected_token=auth_token,
            requests_per_minute=requests_per_minute,
        )

        port = int(os.getenv("PORT", "8080"))
        uvicorn.run(http_app, host="0.0.0.0", port=port)
    else:
        raise ValueError(f"MCP_TRANSPORT desconocido: {transport}")