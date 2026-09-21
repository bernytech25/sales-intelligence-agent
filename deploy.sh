#!/bin/bash
# deploy.sh - Script simplificado para desplegar la API REST (FastAPI) en Cloud Run
# Usa cloudbuild.rest.yaml como única fuente de verdad para el build.
#
# Requisitos previos:
# 1. Tener gcloud configurado: gcloud config set project <TU_PROJECT_ID>
# 2. Tener los secretos en Secret Manager:
#    - google-api-key (clave de API de Gemini)
#    - jwt-secret-key (clave secreta para JWT)
# 3. Si ejecutas manualmente (sin trigger), debes proveer SHORT_SHA:
#    ./deploy.sh --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)

set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="sales-agent"
IMAGE_NAME="sales-agent"
REPO_NAME="sales-repo"

echo "🚀 Desplegando ${SERVICE_NAME} en ${REGION}..."
echo "   Project: ${PROJECT_ID}"
echo "   Image:   ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:\$SHORT_SHA"
echo ""

# Ejecutar Cloud Build usando la configuración declarativa
# Nota: $SHORT_SHA se llena automáticamente si usas un Trigger de Cloud Build.
# Para builds manuales, usa: --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)
gcloud builds submit --config cloudbuild.rest.yaml \
  --substitutions=_REGION=${REGION},_REPO=${REPO_NAME},_IMAGE=${IMAGE_NAME},_SERVICE=${SERVICE_NAME}

echo ""
echo "✅ Deploy completado exitosamente."
echo "   Servicio: ${SERVICE_NAME}"
echo "   URL:      https://${SERVICE_NAME}-${PROJECT_ID}.${REGION}.run.app"
echo ""
echo "⚠️  NOTA: Si el deploy falló por '\$SHORT_SHA no definido', ejecuta:"
echo "   ./deploy.sh --substitutions=SHORT_SHA=\$(git rev-parse --short HEAD)"
