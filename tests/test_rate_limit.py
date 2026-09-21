"""
Tests aislados del RateLimitMiddleware, usando una app Starlette mínima
propia (no la app real de main.py) para no compartir contador con el
resto de la suite ni depender de JWT/DB.

Nota: Este test requiere que `app` esté en el Python path. Funciona con:
  python -m pytest tests/test_rate_limit.py -v
Pero falla con:
  pytest tests/test_rate_limit.py -v
Porque no agrega automáticamente el directorio raíz al path.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.rate_limit import RateLimitMiddleware


def _build_app(limit: int) -> Starlette:
    async def ping(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/ping", ping)])
    app.add_middleware(RateLimitMiddleware, requests_per_minute=limit)
    return app


def test_dentro_del_limite_responde_200():
    client = TestClient(_build_app(limit=5))
    for _ in range(5):
        resp = client.get("/ping")
        assert resp.status_code == 200


def test_supera_el_limite_responde_429():
    client = TestClient(_build_app(limit=3))
    for _ in range(3):
        assert client.get("/ping").status_code == 200

    resp = client.get("/ping")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.json()["error"] == "rate_limited"


def test_limite_es_por_ip_no_global():
    client = TestClient(_build_app(limit=2))

    for _ in range(2):
        resp = client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
        assert resp.status_code == 200

    # Otra IP no debería verse afectada por el consumo de la primera
    resp_otra_ip = client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"})
    assert resp_otra_ip.status_code == 200

    # La primera IP ya agotó su cupo
    resp_misma_ip = client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"})
    assert resp_misma_ip.status_code == 429