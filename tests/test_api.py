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


@pytest.fixture
def demo_headers():
    token = create_access_token(data={"sub": "demo"})
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
    assert response.json()["conversation_id"] == "session-inexistente"

def test_delete_memory_retorna_cleared(auth_headers):
    response = client.delete("/memory/session-test-delete", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cleared"
    assert response.json()["conversation_id"] == "session-test-delete"

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
    assert "conversation_id" in data
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
    with patch("app.main.persistent_memory") as memory:
        memory.get_history.return_value = []
        memory.get_history_with_timestamps.return_value = [
            {"role": "user", "content": "¿Cuántos productos hay?"},
            {"role": "assistant", "content": MOCK_ANSWER},
        ]
        client.post("/chat/persistent", json={
            "conversation_id": session_id,
            "question": "¿Cuántos productos hay?"
        }, headers=auth_headers)
        response = client.get(f"/memory/{session_id}?persistent=true", headers=auth_headers)
    assert response.json()["total"] == 2
    memory.add_message.assert_any_call("admin", session_id, "user", "¿Cuántos productos hay?")


def test_memoria_en_sesion_esta_aislada_por_usuario(auth_headers, demo_headers, mock_agent):
    """El mismo ID de conversación no permite que demo lea la de admin."""
    conversation_id = "conversation-compartida"
    client.post("/chat", json={
        "conversation_id": conversation_id,
        "question": "Pregunta privada de admin"
    }, headers=auth_headers)
    response = client.get(f"/memory/{conversation_id}", headers=demo_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 0

# ── Chat: manejo de errores (no debe filtrar detalle interno) ────────────────

def test_chat_error_interno_no_filtra_detalle_de_excepcion(auth_headers):
    """Si run_agent explota, el cliente no debe ver el mensaje crudo de la
    excepción de Python (podría filtrar rutas, nombres de variables, etc.)."""
    mensaje_interno_sensible = "KeyError: '/home/user/secretkeys.json' not found"
    with patch("app.main.run_agent", side_effect=RuntimeError(mensaje_interno_sensible)):
        response = client.post("/chat", json={
            "session_id": "test-error-500",
            "question": "¿Quién vendió más?"
        }, headers=auth_headers)
    assert response.status_code == 500
    assert mensaje_interno_sensible not in response.text

def test_chat_persistent_error_interno_no_filtra_detalle_de_excepcion(auth_headers):
    mensaje_interno_sensible = "ConnectionError: could not reach internal-db-host:5432"
    with patch("app.main.run_agent", side_effect=RuntimeError(mensaje_interno_sensible)):
        response = client.post("/chat/persistent", json={
            "session_id": "test-error-persistent-500",
            "question": "¿Quién vendió más?"
        }, headers=auth_headers)
    assert response.status_code == 500
    assert mensaje_interno_sensible not in response.text
