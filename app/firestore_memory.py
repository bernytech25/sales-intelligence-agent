"""Memoria durable de FastAPI respaldada por Cloud Firestore.

Cada conversación vive debajo del usuario autenticado:
``users/{user_id}/conversations/{conversation_id}/messages/{message_id}``.
De esta forma no existe una consulta que pueda devolver conversaciones de otro
usuario por accidente: ``user_id`` siempre forma parte de la ruta.
"""

from datetime import datetime, timezone
from typing import Any


class FirestoreMemory:
    """Implementa memoria persistente, aislada por usuario y conversación.

    El cliente de Firestore se crea de manera diferida para que la aplicación
    pueda arrancar localmente sin credenciales de Google. Cloud Run usa su
    cuenta de servicio por defecto; en desarrollo se usa ADC.
    """

    def __init__(self, client: Any | None = None):
        self._client = client

    def _get_client(self):
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client()
        return self._client

    def _conversation(self, user_id: str, conversation_id: str):
        return (
            self._get_client()
            .collection("users")
            .document(user_id)
            .collection("conversations")
            .document(conversation_id)
        )

    def add_message(self, user_id: str, conversation_id: str, role: str, content: str):
        conversation = self._conversation(user_id, conversation_id)
        now = datetime.now(timezone.utc)
        conversation.set({"updated_at": now}, merge=True)
        conversation.collection("messages").add({
            "role": role,
            "content": content,
            "created_at": now,
        })

    def get_history(self, user_id: str, conversation_id: str) -> list[dict]:
        return [
            {"role": message["role"], "content": message["content"]}
            for message in self.get_history_with_timestamps(user_id, conversation_id)
        ]

    def get_history_with_timestamps(self, user_id: str, conversation_id: str) -> list[dict]:
        messages = (
            self._conversation(user_id, conversation_id)
            .collection("messages")
            .order_by("created_at")
            .stream()
        )
        result = []
        for snapshot in messages:
            message = snapshot.to_dict()
            created_at = message["created_at"]
            result.append({
                "role": message["role"],
                "content": message["content"],
                "timestamp": created_at.isoformat(),
            })
        return result

    def clear(self, user_id: str, conversation_id: str):
        """Borra mensajes y metadatos de una conversación del usuario dueño."""
        conversation = self._conversation(user_id, conversation_id)
        client = self._get_client()
        batch = client.batch()
        count = 0
        for message in conversation.collection("messages").stream():
            batch.delete(message.reference)
            count += 1
            # Firestore limita cada batch a 500 escrituras.
            if count == 499:
                batch.commit()
                batch = client.batch()
                count = 0
        batch.delete(conversation)
        batch.commit()
