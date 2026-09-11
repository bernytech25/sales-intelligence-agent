"""
Rate limiting compartido, reutilizado tanto por app/main.py (FastAPI, JWT)
como por app/mcp_server.py (MCP, token fijo).

Se separa a este módulo por el mismo motivo que prompts.py: evitar que la
lógica de "ventana deslizante de 60s" quede duplicada y se desincronice
entre los dos servidores.

Nota de diseño: en mcp_server.py se cuenta por token (un solo cliente
conocido). Acá en cambio contamos por IP, porque main.py tiene múltiples
usuarios JWT distintos y lo que queremos frenar es abuso por origen de
red, no por usuario autenticado.

Misma limitación conocida que en mcp_server.py: el contador vive en
memoria del proceso. Si Cloud Run escala a más de una instancia, el
límite real es N x límite/min, no un límite global estricto. Para eso,
el siguiente paso sería mover el contador a Memorystore (Redis).
"""

import time
import asyncio
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def _client_ip(request) -> str:
    """Extrae la IP real del cliente, priorizando X-Forwarded-For
    (necesario detrás de Cloud Run, que actúa como proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limita requests por IP dentro de una ventana deslizante de 60s."""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.limit = requests_per_minute
        self.window_seconds = 60
        self._requests_by_ip: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def dispatch(self, request, call_next):
        ip = _client_ip(request)
        now = time.monotonic()

        async with self._lock:
            timestamps = self._requests_by_ip[ip]
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