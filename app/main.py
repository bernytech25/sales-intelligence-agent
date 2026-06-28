"""
FastAPI - Sales Agent API con autenticación JWT

Endpoints públicos (no requieren token):
  GET  /              → health check
  POST /auth/token    → obtener token JWT

Endpoints protegidos (requieren Authorization: Bearer <token>):
  GET  /ventas/resumen          → resumen general sin agente
  POST /chat                    → conversación con memoria in-session
  POST /chat/persistent         → conversación con memoria persistente
  GET  /memory/{session_id}     → ver historial
  DELETE /memory/{session_id}   → limpiar historial
"""

from typing import Annotated
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.agent_langgraph import run_agent
from app.tools import resumen_general
from app.memory import in_session_memory, persistent_memory
from app.auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

app = FastAPI(
    title="Sales Agent API",
    description="Agente de análisis de ventas con LangGraph + Groq + Memoria + JWT Auth",
    version="3.0.0",
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    question: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "user-123",
                "question": "¿Quién vendió más este trimestre?"
            }
        }
    }


class ChatResponse(BaseModel):
    session_id: str
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

    history = in_session_memory.get_history(request.session_id)

    try:
        answer = run_agent(question=request.question, history=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    in_session_memory.add_message(request.session_id, "user", request.question)
    in_session_memory.add_message(request.session_id, "assistant", answer)

    return ChatResponse(
        session_id=request.session_id,
        question=request.question,
        answer=answer,
    )


@app.post("/chat/persistent", response_model=ChatResponse, tags=["Agente - Memoria Persistente"])
def chat_persistent(
    request: ChatRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Conversación con memoria persistente (Cosmos DB). Requiere autenticación."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    history = persistent_memory.get_history(request.session_id)

    try:
        answer = run_agent(question=request.question, history=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    persistent_memory.add_message(request.session_id, "user", request.question)
    persistent_memory.add_message(request.session_id, "assistant", answer)

    return ChatResponse(
        session_id=request.session_id,
        question=request.question,
        answer=answer,
    )


@app.get("/memory/{session_id}", tags=["Memoria"])
def get_memory(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    persistent: bool = False
):
    """Ver historial de conversación. Requiere autenticación."""
    if persistent:
        history = persistent_memory.get_history_with_timestamps(session_id)
    else:
        history = in_session_memory.get_history(session_id)
    return {"session_id": session_id, "messages": history, "total": len(history)}


@app.delete("/memory/{session_id}", tags=["Memoria"])
def clear_memory(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    persistent: bool = False
):
    """Limpiar historial de una sesión. Requiere autenticación."""
    if persistent:
        persistent_memory.clear(session_id)
    else:
        in_session_memory.clear(session_id)
    return {"status": "cleared", "session_id": session_id}