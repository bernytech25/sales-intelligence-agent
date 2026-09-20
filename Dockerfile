# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Metadata
LABEL maintainer="sales-agent"
LABEL description="Agente de análisis de ventas con LangGraph + Gemini + FastAPI"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias primero (cacheable layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY app/ ./app/

# Copiar solo el dataset estático (NO memory.json -- ese es estado de
# runtime, no se versiona ni se empaqueta en la imagen; cada deploy
# arranca con memoria persistente vacía, no con sesiones viejas adentro)
COPY data/ventas.csv ./data/ventas.csv

# Crear carpeta de datos si no existe
RUN mkdir -p ./data

# Cloud Run inyecta secretos como variables de entorno automáticamente
# cuando se usa --set-secrets en el deploy. No hardcodear claves en el Dockerfile.

# Cloud Run inyecta PORT en runtime (default 8080 si no está seteado,
# útil también para correrlo local con `docker run -p 8080:8080`)
ENV PORT=8080
EXPOSE 8080

# Health check: usa $PORT, no un valor fijo, para no quedar desincronizado
# si Cloud Run cambia el puerto inyectado
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8080\")}/')" || exit 1

# Usuario no-root por seguridad
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Shell form (no JSON array) + exec: así ${PORT} se expande en runtime.
# El array ["uvicorn", ..., "--port", "8000"] anterior NUNCA leía la
# variable de entorno -- por eso Cloud Run esperaba en 8080 y la app
# escuchaba en 8000, timeout garantizado.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}