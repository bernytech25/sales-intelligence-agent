#!/bin/bash
# Script de despliegue en Google Cloud Run con Secret Manager
# Uso: ./deploy.sh

set -e

# Configuración
PROJECT_ID=$(gcloud config get-value core/project)
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-sales-agent}"
REPO_NAME="${REPO_NAME:-sales-repo}"
IMAGE_NAME="${IMAGE_NAME:-sales-agent}"

echo "🔍 Proyecto: ${PROJECT_ID}"
echo "🌍 Región: ${REGION}"
echo "📦 Servicio: ${SERVICE_NAME}"

# Paso 1: Verificar que los secretos existen, si no crearlos
echo ""
echo "🔐 Verificando secretos..."

if ! gcloud secrets describe jwt-secret-key --project="${PROJECT_ID}" &>/dev/null; then
    echo "   Creando secreto jwt-secret-key..."
    openssl rand -hex 32 | gcloud secrets create jwt-secret-key --data-file=- --project="${PROJECT_ID}"
else
    echo "   ✅ jwt-secret-key ya existe"
fi

if ! gcloud secrets describe google-api-key --project="${PROJECT_ID}" &>/dev/null; then
    echo "   ⚠️  google-api-key no existe. Crealo manualmente:"
    echo "      echo 'TU_API_KEY' | gcloud secrets create google-api-key --data-file=-"
    read -p "   ¿Querés crearlo ahora? (y/n): " CREATE_KEY
    if [[ "$CREATE_KEY" == "y" ]]; then
        read -p "   Ingresá tu GOOGLE_API_KEY: " API_KEY
        echo "$API_KEY" | gcloud secrets create google-api-key --data-file=- --project="${PROJECT_ID}"
    fi
else
    echo "   ✅ google-api-key ya existe"
fi

# Paso 2: Construir y subir la imagen
echo ""
echo "🔨 Construyendo imagen Docker..."
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest"
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
echo ""
echo "🔑 Ver configuración de secretos:"
echo "   gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format='yaml(spec.template.spec.containers[0].env)'"
