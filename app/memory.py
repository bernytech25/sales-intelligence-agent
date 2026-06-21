"""
Módulo de memoria del agente.

Dos tipos:
- InSessionMemory: historial dentro de una conversación (en RAM)
- PersistentMemory: historial entre conversaciones (en disco, JSON)
- CosmosMemory: historial entre conversaciones (Azure Cosmos DB)

El backend de memoria persistente se elige con la variable de entorno
MEMORY_BACKEND:
    MEMORY_BACKEND=json    -> usa el archivo local data/memory.json (default)
    MEMORY_BACKEND=cosmos  -> usa Azure Cosmos DB

Las tres clases comparten la misma interfaz pública
(add_message, get_history, get_history_with_timestamps, clear),
por lo que main.py no necesita saber cuál backend está activo.
"""

import os
import json
from pathlib import Path
from datetime import datetime


# ── Memoria en sesión ─────────────────────────────────────────────────────────

class InSessionMemory:
    """
    Mantiene el historial de mensajes durante una conversación.
    Se pierde al reiniciar el servidor.
    Útil para que el agente recuerde el contexto dentro del mismo chat.
    """

    def __init__(self):
        self._sessions: dict[str, list[dict]] = {}

    def add_message(self, session_id: str, role: str, content: str):
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    def get_history(self, session_id: str) -> list[dict]:
        """Retorna el historial sin timestamps (formato para el agente)."""
        messages = self._sessions.get(session_id, [])
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def clear(self, session_id: str):
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


# ── Memoria persistente ───────────────────────────────────────────────────────

MEMORY_FILE = Path(__file__).parent.parent / "data" / "memory.json"


class PersistentMemory:
    """
    Persiste el historial de conversaciones en un archivo JSON.
    Sobrevive reinicios del servidor.

    En producción → reemplazar por Cosmos DB, PostgreSQL, Redis, etc.
    La interfaz (add_message, get_history) no cambia.
    """

    def _load(self) -> dict:
        if not MEMORY_FILE.exists():
            return {}
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict):
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add_message(self, session_id: str, role: str, content: str):
        data = self._load()
        if session_id not in data:
            data[session_id] = []
        data[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self._save(data)

    def get_history(self, session_id: str) -> list[dict]:
        data = self._load()
        messages = data.get(session_id, [])
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def get_history_with_timestamps(self, session_id: str) -> list[dict]:
        data = self._load()
        return data.get(session_id, [])

    def clear(self, session_id: str):
        data = self._load()
        data.pop(session_id, None)
        self._save(data)

    def list_sessions(self) -> list[str]:
        return list(self._load().keys())


# ── Selección de backend ──────────────────────────────────────────────────────
# El servidor FastAPI las comparte entre requests.

in_session_memory = InSessionMemory()

_backend = os.getenv("MEMORY_BACKEND", "json").lower()

if _backend == "cosmos":
    from app.cosmos_memory import CosmosMemory
    persistent_memory = CosmosMemory()
else:
    persistent_memory = PersistentMemory()