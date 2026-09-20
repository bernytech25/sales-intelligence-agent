# Guía de Despliegue en Google Cloud Run con Secret Manager

## Problema Común: Claves Secretas en Cloud Run

Cuando despliegas tu aplicación en Cloud Run, las variables de entorno que funcionan localmente (desde `.env`) **no están disponibles automáticamente**. Cloud Run es un entorno efímero que no tiene acceso a tu archivo `.env`.

## Solución Recomendada: Google Secret Manager + `--set-secrets`

### 1. Crear los Secretos en Secret Manager

Primero, crea archivos temporales con tus claves:

```bash
# Crear archivo con la clave JWT (genera una segura)
openssl rand -hex 32 > jwt_secret_key.txt

# Crear archivo con tu Google API Key
echo "TU_GOOGLE_API_KEY_AQUI" > google_api_key.txt
```

Luego, súbelos a Secret Manager:

```bash
# Crear secreto para JWT_SECRET_KEY
gcloud secrets create jwt-secret-key \
  --data-file=jwt_secret_key.txt \
  --replication-policy="automatic"

# Crear secreto para GOOGLE_API_KEY
gcloud secrets create google-api-key \
  --data-file=google_api_key.txt \
  --replication-policy="automatic"
```

### 2. Desplegar en Cloud Run con los Secretos

```bash
gcloud run deploy sales-agent \
  --image us-central1-docker.pkg.dev/PROJECT_ID/sales-repo/sales-agent:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest,GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="GEMINI_MODEL=gemini-3.1-flash-lite,RATE_LIMIT_PER_MINUTE=60,CORS_ALLOWED_ORIGINS=*"
```

**¿Qué hace `--set-secrets`?**
- Monta cada secreto como una variable de entorno en el contenedor
- La app lee `os.environ.get("JWT_SECRET_KEY")` normalmente
- Los secretos se rotan automáticamente sin redeploy (usando `:latest`)

### 3. Verificar el Despliegue

```bash
# Ver las variables y secretos configurados
gcloud run services describe sales-agent \
  --region us-central1 \
  --format="yaml(spec.template.spec.containers[0].env)"

# Ver logs en tiempo real
gcloud run services logs read sales-agent --region us-central1 --limit 50
```

## Alternativa: Variables de Entorno Directas (Menos Seguro)

⚠️ **No recomendado para producción** porque las claves quedan visibles en el comando y en Cloud Build logs.

```bash
gcloud run deploy sales-agent \
  --image us-central1-docker.pkg.dev/PROJECT_ID/sales-repo/sales-agent:latest \
  --region us-central1 \
  --set-env-vars="JWT_SECRET_KEY=tu-clave-muy-larga-y-segura,GOOGLE_API_KEY=tu-api-key"
```

## Actualizar Secretos Existentes

Si necesitas rotar una clave:

```bash
# Añadir nueva versión del secreto
gcloud secrets versions add jwt-secret-key --data-file=nuevo_jwt_secret_key.txt

# El servicio en Cloud Run usará automáticamente la versión :latest
# Si usaste una versión específica, actualízala:
gcloud run services update sales-agent \
  --region us-central1 \
  --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest"
```

## Permisos Necesarios

La cuenta de servicio de Cloud Run necesita permiso para leer secretos:

```bash
# Obtener la cuenta de servicio de Cloud Run (si usás la default)
SERVICE_ACCOUNT=$(gcloud iam service-accounts list \
  --filter="displayName:Compute Engine default" \
  --format="value(email)")

# Dar permiso de Secret Manager Secret Accessor
gcloud secrets add-iam-policy-binding jwt-secret-key \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding google-api-key \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.secretAccessor"
```

## Script de Despliegue Completo

Guardá esto como `deploy.sh`:

```bash
#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value core/project)
REGION="us-central1"
SERVICE_NAME="sales-agent"
IMAGE_TAG="latest"
IMAGE_URL="${REGION}-docker.pkg.dev/${PROJECT_ID}/sales-repo/sales-agent:${IMAGE_TAG}"

echo "🔨 Construyendo imagen..."
gcloud builds submit --tag "${IMAGE_URL}"

echo "🔐 Configurando secretos..."
# (Asumiendo que ya creaste los secretos previamente)

echo "🚀 Desplegando en Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URL}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest,GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="GEMINI_MODEL=gemini-3.1-flash-lite,RATE_LIMIT_PER_MINUTE=60" \
  --timeout=300

echo "✅ Despliegue completado!"
gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format="value(status.url)"
```

## Comparación: Local vs Cloud Run

| Aspecto | Local (FastAPI) | Cloud Run |
|---------|----------------|-----------|
| Variables de entorno | Archivo `.env` o shell | Secret Manager + `--set-secrets` |
| Persistencia | Archivos en disco | Efímero (usar DB externa) |
| Escalado | Manual | Automático (0 a N instancias) |
| Logs | Consola/File | Cloud Logging |

## Troubleshooting

### Error: `Falta la variable de entorno JWT_SECRET_KEY`

**Causa:** El secreto no está montado correctamente.

**Solución:**
```bash
# Verificar que el secreto existe
gcloud secrets list

# Verificar que el servicio tiene el secreto configurado
gcloud run services describe sales-agent --region us-central1 \
  --format="yaml(spec.template.spec.containers[0].env)"

# Redeployar con el secreto explícitamente
gcloud run deploy sales-agent \
  --set-secrets="JWT_SECRET_KEY=jwt-secret-key:latest" \
  --region us-central1
```

### Error: `Permission denied` al acceder al secreto

**Causa:** La cuenta de servicio de Cloud Run no tiene permisos.

**Solución:**
```bash
gcloud secrets add-iam-policy-binding jwt-secret-key \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### La app funciona local pero no en Cloud Run

**Checklist:**
1. ✅ ¿Los secretos están creados en Secret Manager?
2. ✅ ¿El deploy usa `--set-secrets` correctamente?
3. ✅ ¿La cuenta de servicio tiene permisos de `secretAccessor`?
4. ✅ ¿Los logs de Cloud Run muestran el error específico?

```bash
gcloud run services logs read sales-agent --region us-central1 --limit 100
```

## Recursos Oficiales

- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs/creating-and-accessing-secrets)
- [Cloud Run Environment Variables](https://cloud.google.com/run/docs/configuring/services/environment-variables)
- [Using Secrets in Cloud Run](https://cloud.google.com/run/docs/configuring/services/secrets)
