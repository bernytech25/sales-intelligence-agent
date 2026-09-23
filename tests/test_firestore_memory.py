"""Contratos unitarios para el aislamiento de FirestoreMemory."""

from unittest.mock import MagicMock

from app.firestore_memory import FirestoreMemory


def _conversation_client():
    client = MagicMock()
    users = client.collection.return_value
    user = users.document.return_value
    conversations = user.collection.return_value
    return client, users, user, conversations


def test_firestore_ruta_incluye_usuario_y_conversacion():
    client, users, user, conversations = _conversation_client()
    memory = FirestoreMemory(client=client)

    memory.get_history("admin", "conv-123")

    client.collection.assert_called_once_with("users")
    users.document.assert_called_once_with("admin")
    user.collection.assert_called_once_with("conversations")
    conversations.document.assert_called_once_with("conv-123")


def test_firestore_agrega_mensaje_sin_user_id_del_cliente():
    client, _, _, conversations = _conversation_client()
    conversation = conversations.document.return_value
    memory = FirestoreMemory(client=client)

    memory.add_message("demo", "conv-1", "user", "mensaje")

    conversation.set.assert_called_once()
    conversation.collection.assert_called_once_with("messages")
    conversation.collection.return_value.add.assert_called_once()
