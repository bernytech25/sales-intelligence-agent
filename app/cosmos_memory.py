"""
Memoria persistente usando Azure Cosmos DB (NoSQL API).

Reemplaza el almacenamiento basado en JSON local por una base de datos
real en la nube, resolviendo la limitación de consistencia cuando
Azure Container Apps escala a múltiples réplicas.

Modelo de datos:
    Cada sesión de conversación es UN documento en el container 'memory'.
    El documento tiene esta forma:
    {
        "id": "<session_id>",          <- requerido por Cosmos, usamos el mismo session_id
        "session_id": "<session_id>",  <- partition key
        "messages": [
            {"role": "user", "content": "...", "timestamp": "..."},
            {"role": "assistant", "content": "...", "timestamp": "..."}
        ]
    }

Por qué un documento por sesión (en vez de un documento por mensaje):
    - Todas las lecturas de una conversación se hacen por session_id completo,
      nunca se necesita un mensaje individual aislado.
    - Cosmos DB cobra Request Units por operación; leer 1 documento con 20
      mensajes es más barato que leer 20 documentos con upsert constante.
    - El partition key /session_id hace que todos los mensajes de una
      conversación vivan en la misma partición física, maximizando
      la eficiencia de la query de lectura.

Mantiene la misma interfaz pública que la versión basada en JSON
(add_message, get_history, get_history_with_timestamps, clear)
para que main.py no requiera ningún cambio al migrar.
"""

import os
from datetime import datetime
from azure.cosmos import CosmosClient, exceptions
from azure.cosmos.partition_key import PartitionKey


class CosmosMemory:
    """
    Memoria persistente respaldada por Azure Cosmos DB.
    Reemplazo directo de la clase PersistentMemory basada en JSON.
    """

    def __init__(self):
        endpoint = os.getenv("COSMOS_ENDPOINT")
        key = os.getenv("COSMOS_KEY")
        database_name = os.getenv("COSMOS_DATABASE", "sales-agent-db")
        container_name = os.getenv("COSMOS_CONTAINER", "memory")

        if not endpoint or not key:
            raise ValueError(
                "Faltan COSMOS_ENDPOINT y/o COSMOS_KEY en las variables de entorno."
            )

        self._client = CosmosClient(endpoint, credential=key)
        self._database = self._client.create_database_if_not_exists(id=database_name)
        self._container = self._database.create_container_if_not_exists(
            id=container_name,
            partition_key=PartitionKey(path="/session_id"),
        )

    def _get_document(self, session_id: str) -> dict | None:
        """Obtiene el documento completo de una sesión, o None si no existe."""
        try:
            return self._container.read_item(
                item=session_id, partition_key=session_id
            )
        except exceptions.CosmosResourceNotFoundError:
            return None

    def add_message(self, session_id: str, role: str, content: str):
        """
        Agrega un mensaje al historial de la sesión.
        Si la sesión no existe todavía, crea el documento.
        Si ya existe, hace upsert con el mensaje agregado al array.
        """
        document = self._get_document(session_id)

        new_message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        if document is None:
            document = {
                "id": session_id,
                "session_id": session_id,
                "messages": [new_message],
            }
        else:
            document["messages"].append(new_message)

        self._container.upsert_item(document)

    def get_history(self, session_id: str) -> list[dict]:
        """Retorna el historial sin timestamps (formato que espera el agente)."""
        document = self._get_document(session_id)
        if document is None:
            return []
        return [
            {"role": m["role"], "content": m["content"]}
            for m in document["messages"]
        ]

    def get_history_with_timestamps(self, session_id: str) -> list[dict]:
        """Retorna el historial completo, incluyendo timestamps."""
        document = self._get_document(session_id)
        if document is None:
            return []
        return document["messages"]

    def clear(self, session_id: str):
        """Elimina el documento completo de una sesión."""
        try:
            self._container.delete_item(item=session_id, partition_key=session_id)
        except exceptions.CosmosResourceNotFoundError:
            pass  # Ya no existía, no hay nada que limpiar

    def list_sessions(self) -> list[str]:
        """Lista todos los session_id existentes en el container."""
        query = "SELECT c.session_id FROM c"
        items = self._container.query_items(query=query, enable_cross_partition_query=True)
        return [item["session_id"] for item in items]