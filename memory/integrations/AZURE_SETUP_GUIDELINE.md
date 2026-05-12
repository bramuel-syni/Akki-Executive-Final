# Azure Setup Guideline — AKKI Production Stack

> Drafted 2026-05-12 by Patch 15-19 sprint. Read end-to-end before provisioning. The objective is a production Azure footprint that matches AKKI's original architecture: Front Door (edge + WAF) → AKS (containers) → Key Vault + Blob Storage, with optional ACR + managed identity.

---

## 1. Prerequisites

| Requirement | Detail |
|---|---|
| Azure subscription | One paid (Pay-As-You-Go) or Enterprise Agreement subscription. Free tier won't carry AKS. |
| Subscription role | **Owner** (or Owner on a target resource group + User Access Administrator). Contributor alone is not enough — we'll need to assign role assignments and link Key Vault to AKS. |
| Local CLI | `az --version` ≥ 2.55. `kubectl` ≥ 1.27. `helm` ≥ 3.13. |
| Quotas | Default region quota for D-series VMs ≥ 16 vCPU. If your subscription is new this is usually fine; otherwise raise a quota request before starting. |
| Domain control | Ownership of `akki.ai` (or chosen domain) at the registrar so we can add CNAME records. |
| GitHub repo access | Read access to this repo to wire AKS image pulls via OIDC or ACR pull credentials. |

## 2. Resource group + region

**Recommended region**: `uksouth` (lowest latency to UK/EU users; also has both AKS and Front Door GA).
Fallback: `westeurope` (Amsterdam) if uksouth is capacity-constrained.

**Naming convention** (suggested):
```
rg-akki-prod-uks            # resource group
aks-akki-prod-uks            # AKS cluster
acr-akki-prod-uks            # Azure Container Registry  (Note: ACR names cannot contain '-'. Use 'acrakkipro duks' = 'acrakkiproduks')
kv-akki-prod-uks             # Key Vault (24 char max)
stakkiproduks                # Storage Account (lowercase, no hyphens, 3-24 chars)
fd-akki-prod                 # Front Door (global resource, no region)
```

Provision RG:
```
az group create --name rg-akki-prod-uks --location uksouth
```

## 3. Identity

**Use a Managed Identity** for AKS → ACR and AKS → Key Vault. **Avoid** long-lived service principal client secrets.

Strategy:
1. Create a user-assigned managed identity for the cluster: `id-akki-aks-prod`.
2. Assign it `AcrPull` on the ACR (so kubelet can pull images) and `Key Vault Secrets User` on the Key Vault.
3. Enable AKS workload identity federation so pods can request scoped tokens without mounted secrets.

If you must use a service principal (e.g. CI/CD from outside Azure), scope it to a single RG and rotate the secret every 90 days.

## 4. AKS cluster

**Minimum nodes for AKKI today**: 2 × `Standard_D4s_v5` (4 vCPU, 16 GiB). With the current workload (FastAPI + MongoDB sidecar + frontend SPA), this gives ~50% headroom. Scale to 4 nodes for production rollout.

System node pool + a user node pool is recommended (cleaner upgrades). Provision:
```
az aks create \
  --resource-group rg-akki-prod-uks \
  --name aks-akki-prod-uks \
  --location uksouth \
  --kubernetes-version 1.29.4 \
  --node-count 2 \
  --node-vm-size Standard_D4s_v5 \
  --enable-managed-identity \
  --assign-identity /subscriptions/<SUB>/resourceGroups/rg-akki-prod-uks/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-akki-aks-prod \
  --enable-azure-keyvault-secrets-provider \
  --enable-workload-identity \
  --enable-oidc-issuer \
  --network-plugin azure \
  --max-pods 30
```

## 5. Container registry (ACR)

```
az acr create --resource-group rg-akki-prod-uks --name acrakkiproduks --sku Standard --location uksouth
az aks update --name aks-akki-prod-uks --resource-group rg-akki-prod-uks --attach-acr acrakkiproduks
```

Build + push (from this repo's root):
```
az acr login --name acrakkiproduks
docker build -t acrakkiproduks.azurecr.io/akki-backend:latest -f backend/Dockerfile backend/
docker push acrakkiproduks.azurecr.io/akki-backend:latest
# (Repeat for frontend)
```

## 6. Key Vault

```
az keyvault create --name kv-akki-prod-uks --resource-group rg-akki-prod-uks --location uksouth --sku standard --enable-rbac-authorization true
```

**Secrets AKKI needs to store** (one Key Vault secret per env var; mounted into pods via CSI driver):
| Secret name | Source / purpose |
|---|---|
| `MONGO-URL` | MongoDB connection string (production cluster) |
| `DB-NAME` | Mongo database name |
| `JWT-SECRET` | App-side JWT signing secret (long random) |
| `EMERGENT-LLM-KEY` | Emergent universal LLM key (from platform Profile > Universal Key) |
| `STRIPE-SECRET-KEY` | Stripe secret key (live) |
| `STRIPE-WEBHOOK-SIGNING-SECRET` | Stripe webhook signing secret |
| `RESEND-API-KEY` | Email provider key (if used) |
| `CLAMAV-API-KEY` | If using hosted ClamAV |
| `FRONT-DOOR-CALLBACK-SECRET` | Shared secret for AFD → AKS auth (optional) |

Grant the AKS managed identity `Key Vault Secrets User`:
```
az role assignment create --assignee <managed-identity-clientId> --role "Key Vault Secrets User" --scope $(az keyvault show -n kv-akki-prod-uks --query id -o tsv)
```

## 7. Blob Storage

Create the storage account + 3 containers (one per data class):
```
az storage account create --name stakkiproduks --resource-group rg-akki-prod-uks --location uksouth --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false
az storage container create --account-name stakkiproduks --name uploads --auth-mode login
az storage container create --account-name stakkiproduks --name exports --auth-mode login
az storage container create --account-name stakkiproduks --name audit-trails --auth-mode login
```

Containers:
- `uploads`        — original user-uploaded docs (PDF/DOCX). Lifecycle: tier to Cool after 30d, Archive after 365d.
- `exports`        — generated PDFs/DOCX from Work Studio. Lifecycle: delete after 90d.
- `audit-trails`   — append-only audit logs (use Immutable Storage policy in production for SOC-2 compliance).

## 8. Front Door (Standard tier)

Front Door routes `app.akki.ai` and `www.akki.ai` to the AKS ingress controller's public IP (or to an Application Gateway in front of AKS).

```
az afd profile create --resource-group rg-akki-prod-uks --profile-name fd-akki-prod --sku Standard_AzureFrontDoor
az afd endpoint create --resource-group rg-akki-prod-uks --profile-name fd-akki-prod --endpoint-name app-akki --enabled-state Enabled
```

**Routing rules**:
- `/api/*` → backend service (port 8001 inside AKS)
- `/*`     → frontend service (port 80 / nginx ingress)

**WAF policy** (Premium tier, optional but recommended for production):
- Bot protection: on
- Rate limit: 200 req/min per IP
- Managed rule set: `Microsoft_DefaultRuleSet_2.1`
- Custom rule: block requests where path contains `..` or `'` (basic SQLi guard before app validation)

## 9. DNS

In your registrar's DNS console for `akki.ai`:
| Record | Value |
|---|---|
| `CNAME app` | `<endpoint>.z01.azurefd.net` (from `az afd endpoint show`) |
| `CNAME www` | `<endpoint>.z01.azurefd.net` |
| `TXT _afd.app` | `<validation-token>` (Azure Front Door domain validation step) |

After DNS propagates, complete Front Door custom-domain validation in the portal.

## 10. What to give me back (checklist)

Once provisioning is done, send back these values so I can wire them into AKKI's deployment manifests + GitHub Actions secrets:

```
AZURE_TENANT_ID:              <tenant uuid>
AZURE_SUBSCRIPTION_ID:        <subscription uuid>
AZURE_RESOURCE_GROUP:         rg-akki-prod-uks
AKS_CLUSTER_NAME:             aks-akki-prod-uks
AKS_OIDC_ISSUER_URL:          <from `az aks show -n aks-akki-prod-uks -g rg-akki-prod-uks --query oidcIssuerProfile.issuerUrl`>
ACR_LOGIN_SERVER:             acrakkiproduks.azurecr.io
ACR_NAME:                     acrakkiproduks
KEY_VAULT_URI:                https://kv-akki-prod-uks.vault.azure.net/
BLOB_STORAGE_ACCOUNT:         stakkiproduks
BLOB_CONNECTION_STRING:       <from `az storage account show-connection-string -n stakkiproduks -g rg-akki-prod-uks -o tsv`>
FRONT_DOOR_HOSTNAME:          <endpoint>.z01.azurefd.net
FRONT_DOOR_CUSTOM_DOMAIN:     app.akki.ai
MANAGED_IDENTITY_CLIENT_ID:   <from `az identity show -n id-akki-aks-prod -g rg-akki-prod-uks --query clientId -o tsv`>
```

Plus paste the output of:
```
az aks show -n aks-akki-prod-uks -g rg-akki-prod-uks --query nodeResourceGroup -o tsv
```
(the auto-generated MC_ resource group AKS creates — we'll need it for ingress IP).

## 11. Cost estimate (rough, monthly, UK South, prices as of 2026-Q2)

| Component | Spec | Estimated monthly cost |
|---|---|---|
| AKS cluster (control plane) | Free tier | £0 |
| AKS nodes (2 × D4s_v5, 24/7) | 8 vCPU / 32 GiB total | £165 |
| ACR Standard | Up to 100 GB storage | £18 |
| Key Vault Standard | 100k ops/mo | £2 |
| Storage account (LRS, 100 GB) | Hot tier | £2 |
| Egress (50 GB/mo) | | £4 |
| Front Door Standard | 1 endpoint, 1 domain | £30 |
| Optional: Front Door WAF Premium | | £230 (only if you need Premium WAF) |
| Optional: Application Gateway | | £140 (if you prefer it over AKS ingress controller) |

**Baseline production minimum**: ~**£220–£260/month**.
**With Premium WAF and AppGW**: ~**£590–£640/month**.

These are rough estimates — final bill depends on actual egress, request volume, and storage growth. Use Azure Pricing Calculator with the SKUs above for a precise quote.

— end of Azure setup guideline —
