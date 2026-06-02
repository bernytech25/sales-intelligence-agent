"""
Tests de integración para los endpoints de FastAPI.
Usa httpx.TestClient para simular requests HTTP sin levantar el servidor.
"""

import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

client = TestClient(app)


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_retorna_200():
    response = client.get("/")
    assert response.status_code == 200

def test_health_retorna_ok():
    response = client.get("/")
    assert response.json()["status"] == "ok"


# ── Ventas resumen ────────────────────────────────────────────────────────────

def test_ventas_resumen_retorna_200():
    response = client.get("/ventas/resumen")
    assert response.status_code == 200

def test_ventas_resumen_tiene_campos():
    response = client.get("/ventas/resumen")
    data = response.json()
    assert "total_ingresos" in data
    assert "total_transacciones" in data


# ── Memoria ───────────────────────────────────────────────────────────────────

def test_get_memory_session_vacia():
    response = client.get("/memory/session-inexistente")
    assert response.status_code == 200
    assert response.json()["total"] == 0

def test_delete_memory_retorna_cleared():
    response = client.delete("/memory/session-test-delete")
    assert response.status_code == 200
    assert response.json()["status"] == "cleared"


# ── Chat ──────────────────────────────────────────────────────────────────────

def test_chat_pregunta_vacia_retorna_400():
    response = client.post("/chat", json={
        "session_id": "test-vacio",
        "question": "   "
    })
    assert response.status_code == 400

def test_chat_retorna_estructura_correcta():
    response = client.post("/chat", json={
        "session_id": "test-estructura",
        "question": "¿Cuál es el resumen de ventas?"
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "question" in data
    assert "answer" in data

def test_chat_respuesta_no_vacia():
    response = client.post("/chat", json={
        "session_id": "test-respuesta",
        "question": "¿Cuántos vendedores hay?"
    })
    assert response.status_code == 200
    assert len(response.json()["answer"]) > 0

def test_chat_guarda_en_memoria():
    session_id = "test-memoria-guardado"
    client.post("/chat", json={
        "session_id": session_id,
        "question": "¿Cuál es el resumen de ventas?"
    })
    response = client.get(f"/memory/{session_id}")
    assert response.json()["total"] == 2  # user + assistant

def test_chat_persistent_guarda_historial():
    session_id = "test-persistent-guardado"
    client.post("/chat/persistent", json={
        "session_id": session_id,
        "question": "¿Cuántos productos hay?"
    })
    response = client.get(f"/memory/{session_id}?persistent=true")
    assert response.json()["total"] >= 2