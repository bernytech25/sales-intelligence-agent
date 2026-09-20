#!/bin/bash
# Script de despliegue en Google Cloud Run con Secret Manager
# Uso: ./deploy.sh [REPO_NAME]
# Ejemplo: ./deploy.sh sales-mcp-repo

set -e

# Configuración
PROJECT_ID=$(gcloud config get-value core/project)
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sales-agent}"

# Detectar repositorio automáticamente si no se proporciona
if [ -n "$1" ]; then
    REPO_NAME="$1"
elif [ -n "$REPO_NAME" ]; then
    echo "📦 Usando REPO_NAME de variable de entorno: $REPO_NAME"
else
    # Intentar detectar repositorio existente
    if gcloud artifacts repositories describe sales-mcp-repo --location=$REGION --project=$PROJECT_ID &>/dev/null; then
        REPO_NAME="sales-mcp-repo"
        echo "📦 Repositorio detectado: sales-mcp-repo"
    elif gcloud artifacts repositories describe ${SERVICE_NAME}-repo --location=$REGION --project=$PROJECT_ID &>/dev/null; then
        REPO_NAME="${SERVICE_NAME}-repo"
        echo "📦 Repositorio detectado: ${SERVICE_NAME}-repo"
    else
        echo "⚠️ No se encontró un repositorio automático."
        echo "💡 Usa: ./deploy.sh nombre-de-tu-repo"
        echo "   O exporta: export REPO_NAME=nombre-de-tu-repo"
        exit 1
    fi
fi

IMAGE_NAME="${IMAGE_NAME:-sales-agent}"

echo "🔍 Proyecto: ${PROJECT_ID}"
echo "🌍 Región: ${REGION}"
echo "📦 Servicio: ${SERVICE_NAME}"
echo "🗄️ Repositorio: ${REPO_NAME}"

# Paso 1: Verificar que los secretos existen
echo ""
echo "🔐 Verificando secretos..."

if ! gcloud secrets describe jwt-secret-key --project="${PROJECT_ID}" &>/dev/null; then
    echo "   ❌ El secreto 'jwt-secret-key' no existe."
    echo "   Crealo con: openssl rand -hex 32 | gcloud secrets create jwt-secret-key --data-file=-"
    exit 1
else
    echo "   ✅ jwt-secret-key existe"
fi

if ! gcloud secrets describe google-api-key --project="${PROJECT_ID}" &>/dev/null; then
    echo "   ❌ El secreto 'google-api-key' no existe."
    echo "   Crealo con: echo 'TU_API_KEY' | gcloud secrets create google-api-key --data-file=-"
    exit 1
else
    echo "   ✅ google-api-key existe"
fi

# Paso 2: Construir y subir la imagen
echo ""
echo "🔨 Construyendo imagen Docker..."
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest"
echo "   Imagen: ${IMAGE_URL}"
gcloud builds submit --tag "${IMAGE_URL}" --project="${PROJECT_ID}"

# Paso 3: Desplegar en Cloud Run
echo ""
echo "🚀 Desplegando en Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URL}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest,GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="GEMINI_MODEL=gemini-3.1-flash-lite,RATE_LIMIT_PER_MINUTE=60,CORS_ALLOWED_ORIGINS=*" \
  --timeout=300 \
  --project="${PROJECT_ID}"

echo ""
echo "✅ ¡Despliegue completado!"
echo ""
echo "📬 URL del servicio:"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)" --project="${PROJECT_ID}"
echo ""
echo "📊 Ver logs:"
echo "   gcloud run services logs read ${SERVICE_NAME} --region ${REGION} --limit 50"
