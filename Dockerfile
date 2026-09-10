# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Metadata
LABEL maintainer="sales-agent"
LABEL description="Agente de análisis de ventas con LangGraph + Gemini + FastAPI"

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

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

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Usuario no-root por seguridad
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]