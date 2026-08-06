"""
Tests de integración para los endpoints de FastAPI.
Usa httpx.TestClient para simular requests HTTP sin levantar el servidor.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.auth import create_access_token

client = TestClient(app)

# ── Fixture: token JWT para tests ─────────────────────────────────────────────

@pytest.fixture
def auth_headers():
    """Genera un token JWT válido para usar en tests."""
    token = create_access_token(data={"sub": "admin"})
    return {"Authorization": f"Bearer {token}"}

# ── Health check ──────────────────────────────────────────────────────────────

def test_health_retorna_200():
    response = client.get("/")
    assert response.status_code == 200

def test_health_retorna_ok():
    response = client.get("/")
    assert response.json()["status"] == "ok"

# ── Ventas resumen ────────────────────────────────────────────────────────────

def test_ventas_resumen_retorna_200(auth_headers):
    response = client.get("/ventas/resumen", headers=auth_headers)
    assert response.status_code == 200

def test_ventas_resumen_tiene_campos(auth_headers):
    response = client.get("/ventas/resumen", headers=auth_headers)
    data = response.json()
    assert "total_ingresos" in data
    assert "total_transacciones" in data

# ── Memoria ───────────────────────────────────────────────────────────────────

def test_get_memory_session_vacia(auth_headers):
    response = client.get("/memory/session-inexistente", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0

def test_delete_memory_retorna_cleared(auth_headers):
    response = client.delete("/memory/session-test-delete", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cleared"

# ── Chat (con mock del agente, sin LLM real) ──────────────────────────────────

MOCK_ANSWER = "Laura Fernández vendió $414,412."

@pytest.fixture
def mock_agent():
    with patch("app.main.run_agent", return_value=MOCK_ANSWER) as m:
        yield m

def test_chat_pregunta_vacia_retorna_400(auth_headers):
    response = client.post("/chat", json={
        "session_id": "test-vacio",
        "question": "   "
    }, headers=auth_headers)
    assert response.status_code == 400

def test_chat_retorna_estructura_correcta(auth_headers, mock_agent):
    response = client.post("/chat", json={
        "session_id": "test-estructura",
        "question": "¿Cuál es el resumen de ventas?"
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "question" in data
    assert "answer" in data
    assert data["answer"] == MOCK_ANSWER

def test_chat_respuesta_no_vacia(auth_headers, mock_agent):
    response = client.post("/chat", json={
        "session_id": "test-respuesta",
        "question": "¿Cuántos vendedores hay?"
    }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["answer"]) > 0

def test_chat_guarda_en_memoria(auth_headers, mock_agent):
    session_id = "test-memoria-guardado"
    client.post("/chat", json={
        "session_id": session_id,
        "question": "¿Cuál es el resumen de ventas?"
    }, headers=auth_headers)
    response = client.get(f"/memory/{session_id}", headers=auth_headers)
    assert response.json()["total"] == 2  # user + assistant

def test_chat_persistent_guarda_historial(auth_headers, mock_agent):
    session_id = "test-persistent-guardado"
    client.post("/chat/persistent", json={
        "session_id": session_id,
        "question": "¿Cuántos productos hay?"
    }, headers=auth_headers)
    response = client.get(f"/memory/{session_id}?persistent=true", headers=auth_headers)
    assert response.json()["total"] >= 2