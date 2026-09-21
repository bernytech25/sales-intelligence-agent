"""
Rate limiting para la API REST (app/main.py).

Limita requests por IP dentro de una ventana deslizante de 60s usando el
header X-Forwarded-For (necesario detrás de Cloud Run, que actúa como proxy).

Nota: Este módulo es específico para la API REST con autenticación JWT.
El servidor MCP (mcp_server.py) tiene su propio middleware que combina
auth + rate limit por token, porque sus necesidades son distintas:
- REST: múltiples usuarios JWT, rate limit por IP para prevenir abuso
- MCP: un solo token fijo, rate limit por token

No hay duplicación real porque cada implementación cuenta contra claves
distintas (IP vs token) y sirve propósitos diferentes.
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