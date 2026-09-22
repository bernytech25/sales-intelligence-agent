# CD automático para el servidor MCP

El deploy de producción se define en `.github/workflows/deploy-mcp.yml`.
Un `push` a `main` despliega únicamente si el workflow **CI - Sales Intelligence
Agent** termina correctamente. El workflow publica una imagen inmutable con el
SHA completo del commit, crea una nueva revisión del servicio MCP existente y
comprueba que el endpoint responde `401` ante un token inválido. Ese `401` es
la respuesta esperada: confirma que el proceso arrancó y que el middleware de
autenticación está activo sin exponer `MCP_AUTH_TOKEN`.

El workflow no usa claves JSON de Google Cloud. Autentica GitHub mediante
Workload Identity Federation (WIF).

## Configuración única en Google Cloud

Ejecutar una única vez desde Cloud Shell como administrador del proyecto. Estos
comandos crean identidad y permisos; no despliegan una imagen ni cambian el
servicio activo.

```bash
export PROJECT_ID="sales-intelligence-mcp-505519"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export REPOSITORY="bernytech25/sales-intelligence-agent"
export DEPLOYER_NAME="github-cloud-run-deployer"
export DEPLOYER_EMAIL="${DEPLOYER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$DEPLOYER_NAME" \
  --project "$PROJECT_ID" \
  --display-name="GitHub Actions Cloud Run deployer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/run.admin"

gcloud artifacts repositories add-iam-policy-binding sales-mcp-repo \
  --project="$PROJECT_ID" --location="us-central1" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/artifactregistry.writer"

# The MCP service currently runs as the default Compute service account. Give
# the deployer permission to deploy revisions that keep using that identity,
# without granting it permission to impersonate every account in the project.
gcloud iam service-accounts add-iam-policy-binding \
  "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${DEPLOYER_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

gcloud iam workload-identity-pools create github \
  --project="$PROJECT_ID" --location="global" \
  --display-name="GitHub Actions"

gcloud iam workload-identity-pools providers create-oidc github \
  --project="$PROJECT_ID" --location="global" \
  --workload-identity-pool="github" \
  --display-name="GitHub Actions provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='${REPOSITORY}' && assertion.ref=='refs/heads/main'" \
  --issuer-uri="https://token.actions.githubusercontent.com"

gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_EMAIL" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github/attribute.repository/${REPOSITORY}"
```

Cloud Run's runtime service account also needs `roles/secretmanager.secretAccessor`
on `mcp-auth-token`; that permission should already exist because the active
service uses that secret. Verify it before the first automatic deploy.

The project currently has a user-managed key on the default Compute service
account. Do not delete it during this setup. After the first automatic deploy
works, identify any remaining external use of that key and revoke it in a
separate security cleanup. WIF itself does not use that key.

## GitHub configuration

In **Settings → Environments**, create `production`. Add an approval rule if a
human approval before each production deployment is desired.

In **Settings → Secrets and variables → Actions → Variables**, add these
repository variables:

| Variable | Value |
| --- | --- |
| `GCP_PROJECT_ID` | `sales-intelligence-mcp-505519` |
| `GCP_REGION` | `us-central1` |
| `GCP_MCP_ARTIFACT_REPOSITORY` | `sales-mcp-repo` |
| `GCP_MCP_SERVICE` | `sales-intelligence-mcp` |
| `GCP_DEPLOYER_SERVICE_ACCOUNT` | `github-cloud-run-deployer@sales-intelligence-mcp-505519.iam.gserviceaccount.com` |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Full provider resource name returned by `gcloud iam workload-identity-pools providers describe github --project=sales-intelligence-mcp-505519 --location=global --workload-identity-pool=github --format='value(name)'` |

Do not add `MCP_AUTH_TOKEN` to GitHub. Cloud Run reads it directly from Secret
Manager during deployment.

## First deployment and rollback

After the GitHub variables and WIF are configured, use **Actions → Deploy MCP
to Cloud Run → Run workflow**. Confirm the workflow summary reports a new
revision and the expected image SHA. Subsequent pushes to `main` deploy
automatically after CI succeeds.

To roll back, select the prior ready revision in Cloud Run and move traffic
back to it; do not rebuild an old commit just to roll back.

`deploy.sh` and the Cloud Build YAML files remain temporarily as legacy
fallbacks. Do not use them once this workflow completes a successful first
deployment; remove them in a separate cleanup commit after verification.
