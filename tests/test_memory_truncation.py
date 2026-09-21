"""
Tests deterministas de la lógica de memoria: truncamiento de historial y
resolución de pronombres (_truncate_history, _enrich_question).

A diferencia de scripts/verificar_memoria_manual.py, estos tests NO llaman
al LLM -- prueban las funciones puras en aislamiento, así que corren rápido,
gratis, y en CI sin necesitar GOOGLE_API_KEY.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agent_langgraph import _truncate_history, _enrich_question, MAX_HISTORY


# ── _truncate_history ─────────────────────────────────────────────────────────

def _msg(i):
    return {"role": "user" if i % 2 == 0 else "assistant", "content": f"mensaje {i}"}


def test_truncate_history_no_recorta_si_entra_completo():
    history = [_msg(i) for i in range(MAX_HISTORY)]
    resultado = _truncate_history(history)
    assert resultado == history


def test_truncate_history_recorta_a_los_ultimos_n():
    history = [_msg(i) for i in range(MAX_HISTORY + 5)]
    resultado = _truncate_history(history)
    assert len(resultado) == MAX_HISTORY
    assert resultado == history[-MAX_HISTORY:]


def test_truncate_history_conserva_los_mas_recientes():
    history = [_msg(i) for i in range(MAX_HISTORY + 5)]
    resultado = _truncate_history(history)
    assert resultado[-1]["content"] == f"mensaje {MAX_HISTORY + 5 - 1}"


def test_truncate_history_vacio():
    assert _truncate_history([]) == []


# ── _enrich_question ──────────────────────────────────────────────────────────

def test_enrich_question_sin_historial_no_cambia():
    # Sin historial, la pregunta no se modifica
    assert _enrich_question("¿Cuánto vendió Ana García?", []) == "¿Cuánto vendió Ana García?"


def test_enrich_question_sin_pronombre_no_cambia():
    history = [{"role": "assistant", "content": "Ana García vendió $50.000"}]
    pregunta = "¿Cuál es el producto más vendido?"
    assert _enrich_question(pregunta, history) == pregunta


def test_enrich_question_con_pronombre_agrega_contexto():
    history = [{"role": "assistant", "content": "Ana García vendió $50.000 en enero"}]
    resultado = _enrich_question("¿y ella cuánto ganó en febrero?", history)
    assert "Contexto:" in resultado
    assert "Ana García vendió $50.000 en enero" in resultado


def test_enrich_question_usa_la_ultima_respuesta_del_asistente():
    history = [
        {"role": "assistant", "content": "respuesta vieja"},
        {"role": "user", "content": "otra pregunta"},
        {"role": "assistant", "content": "respuesta mas reciente"},
    ]
    resultado = _enrich_question("¿y en ese mes?", history)
    assert "respuesta mas reciente" in resultado
    assert "respuesta vieja" not in resultado