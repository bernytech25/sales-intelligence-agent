"""
Agente de análisis de ventas con LangGraph + Gemini + Memoria + JWT Auth

Endpoints públicos (no requieren token):
  GET  /              → health check
  POST /auth/token    → obtener token JWT

Endpoints protegidos (requieren Authorization: Bearer <token>):
  GET /ventas/resumen          → resumen general sin agente
  POST /chat                    → conversación con memoria in-session
  POST /chat/persistent         → conversación con memoria persistente
  GET  /memory/{session_id}     → ver historial
  DELETE /memory/{session_id}   → limpiar historial
"""

import logging
import os
from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import AliasChoices, BaseModel, Field

from app.agent_langgraph import run_agent
from app.tools import resumen_general
from app.memory import in_session_memory, persistent_memory
from app.rate_limit import RateLimitMiddleware
from app.auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

logger = logging.getLogger("sales_agent")

app = FastAPI(
    title="Sales Agent API",
    description="Agente de análisis de ventas con LangGraph + Gemini + Memoria + JWT Auth",
    version="3.0.0",
)


# El último middleware agregado se ejecuta primero en Starlette. CORS se agrega
# al final para que también pueda añadir sus headers a respuestas como el 429
# producido por el rate limiter. Ambos se ejecutan antes de las rutas.
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
)

_cors_allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
# La API no necesita CORS para Swagger (/docs) ni para clientes servidor-a-servidor.
# Sólo se habilita cuando una interfaz web conocida declara sus orígenes exactos.
if _cors_allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.info("CORS cross-origin disabled; configure CORS_ALLOWED_ORIGINS for a web UI")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    conversation_id: str = Field(
        validation_alias=AliasChoices("conversation_id", "session_id"),
        min_length=1,
    )
    question: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "conversation-123",
                "question": "¿Quién vendió más este trimestre?"
            }
        }
    }


class ChatResponse(BaseModel):
    conversation_id: str
    question: str
    answer: str


# ── Endpoints públicos ────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "sales-agent", "version": "3.0.0"}


@app.post("/auth/token", response_model=Token, tags=["Autenticación"])
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Obtiene un token JWT. Usuarios disponibles para demo:
    - admin / admin123
    - demo / demo123
    """
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ── Endpoints protegidos ──────────────────────────────────────────────────────

@app.get("/ventas/resumen", tags=["Ventas"])
def get_resumen(current_user: Annotated[User, Depends(get_current_user)]):
    """Retorna el resumen general de ventas. Requiere autenticación."""
    return resumen_general()


@app.post("/chat", response_model=ChatResponse, tags=["Agente - Memoria In-Session"])
def chat(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Conversación con memoria in-session. Requiere autenticación."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    history = in_session_memory.get_history(current_user.username, request.conversation_id)

    try:
        answer = run_agent(question=request.question, history=history)
    except Exception:
        logger.exception("Fallo en run_agent (/chat) - conversation_id=%s", request.conversation_id)
        raise HTTPException(status_code=500, detail="Error interno procesando la pregunta. Intentá de nuevo.")

    in_session_memory.add_message(current_user.username, request.conversation_id, "user", request.question)
    in_session_memory.add_message(current_user.username, request.conversation_id, "assistant", answer)

    return ChatResponse(
        conversation_id=request.conversation_id,
        question=request.question,
        answer=answer,
    )


@app.post("/chat/persistent", response_model=ChatResponse, tags=["Agente - Memoria Persistente"])
def chat_persistent(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Conversación con memoria persistente. Requiere autenticación."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    history = persistent_memory.get_history(current_user.username, request.conversation_id)

    try:
        answer = run_agent(question=request.question, history=history)
    except Exception:
        logger.exception("Fallo en run_agent (/chat/persistent) - conversation_id=%s", request.conversation_id)
        raise HTTPException(status_code=500, detail="Error interno procesando la pregunta. Intentá de nuevo.")

    persistent_memory.add_message(current_user.username, request.conversation_id, "user", request.question)
    persistent_memory.add_message(current_user.username, request.conversation_id, "assistant", answer)

    return ChatResponse(
        conversation_id=request.conversation_id,
        question=request.question,
        answer=answer,
    )


@app.get("/memory/{conversation_id}", tags=["Memoria"])
def get_memory(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    persistent: bool = False
):
    """Ver historial de conversación. Requiere autenticación."""
    if persistent:
        history = persistent_memory.get_history_with_timestamps(current_user.username, conversation_id)
    else:
        history = in_session_memory.get_history(current_user.username, conversation_id)
    return {"conversation_id": conversation_id, "messages": history, "total": len(history)}


@app.delete("/memory/{conversation_id}", tags=["Memoria"])
def clear_memory(
    conversation_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    persistent: bool = False
):
    """Limpiar historial de una sesión. Requiere autenticación."""
    if persistent:
        persistent_memory.clear(current_user.username, conversation_id)
    else:
        in_session_memory.clear(current_user.username, conversation_id)
    return {"status": "cleared", "conversation_id": conversation_id}
