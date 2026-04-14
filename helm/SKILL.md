---
name: helm
description: Use when installing Helm charts, managing Kubernetes releases, overriding chart values, discovering charts on Artifact Hub, upgrading or rolling back deployments, or deploying third-party software (databases, message queues, stacks) on Kubernetes. Also trigger when extending a Bitnami chart image, writing a values override file, or pinning chart versions for reproducibility. NOT for cluster setup (see k3s), writing Kubernetes manifests directly (see k8s-workloads, k8s-storage), networking and ingress (see k8s-networking), or day-2 cluster operations (see k8s-operations).
---

# Helm

Helm is the package manager for Kubernetes — charts bundle all the resources and logic to deploy complex applications; releases are the installed instances. Helm stores release state in a `helm.sh/release.v1` secret in the same namespace, enabling history, rollback, and status inspection.

---

## Workflow: add repo → inspect → install → upgrade → rollback

### 1. Add a chart repository

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update                          # refresh index after adding repos
helm repo list                            # show configured repos
```

Start discovery at [Artifact Hub](https://artifacthub.io) — it indexes hundreds of repos. Prefer charts flagged **Official**, **Verified Publisher**, or **CNCF**. Bitnami is a Verified Publisher with broad coverage.

> **Bitnami licensing change:** After mid-2024, Bitnami moved to a paid model. Free images moved from `docker.io/bitnami` to `docker.io/bitnamilegacy`. Charts remain available but may not receive updates under the free model. Evaluate alternatives if long-term maintenance matters.

### 2. Search and inspect

```bash
helm search repo bitnami                  # list all charts in repo
helm search repo bitnami/postgresql       # narrow to a chart

# Dump default values for a specific chart version — pipe to file for reference
helm show values bitnami/postgresql --version 16.4.9 > postgresql-defaults.yaml

# Show chart metadata and requirements
helm show chart bitnami/postgresql --version 16.4.9
```

Always inspect default values before writing your override file. The defaults file is the authoritative reference for available keys and their types.

### 3. Install

```bash
helm install postgres0 bitnami/postgresql \
  --version 16.4.9 \
  --values postgres0_values.yaml \
  --namespace db \
  --atomic
```

**Flag decisions:**
- `--version` — always pin; unpinned installs break on chart updates
- `--values` — prefer a values file over `--set` for anything going into version control
- `--namespace` — isolate releases by namespace; create the namespace first with `kubectl create namespace db`
- `--atomic` — wait for completion; roll back automatically on failure; recommended for CI and first installs. Note: on a failed atomic install, the release is deleted entirely — re-run `helm install` (not `helm upgrade`) to retry.

Release name (`postgres0`) appears in resource names, secret names, and service DNS — use a meaningful name with a numeric suffix when you'll run multiple instances.

### 4. Inspect a running release

```bash
helm list -A                              # all releases across all namespaces
helm list -n db                           # releases in a specific namespace
helm status postgres0 -n db              # state, revision, notes
helm get notes postgres0 -n db           # chart notes (connection strings, passwords, etc.)
helm get values postgres0 -n db          # values used for this release
```

### 5. Upgrade

```bash
helm upgrade postgres0 bitnami/postgresql \
  --version 16.4.9 \
  --values postgres0_values.yaml \
  --namespace db \
  --atomic
```

Some chart values cannot be changed after install (e.g., auth passwords managed by the chart). Check chart docs before upgrading. Use `--dry-run` to preview changes without applying.

> **Bitnami auth credentials on upgrade:** Bitnami charts read auth passwords from the existing Kubernetes secret on upgrade — changing `auth.password` in your values file has no effect. Retrieve the current password first: `helm get values postgres0 -n db` or `kubectl get secret postgres0 -n db -o jsonpath="{.data.postgres-password}" | base64 -d`. Pass it explicitly with `--set auth.postgresPassword=<existing>` if you need to keep it consistent.

### 6. History and rollback

```bash
helm history postgres0 -n db             # list revisions with timestamps and descriptions
helm rollback postgres0 2 -n db          # roll back to revision 2
helm rollback postgres0 -n db            # roll back to previous revision
```

### 7. Uninstall

```bash
helm uninstall postgres0 -n db
```

This removes all chart-managed resources and the Helm release secret. **PersistentVolumeClaims are deleted by default**, destroying all data — PersistentVolumes survive only if the StorageClass reclaim policy is `Retain`. Verify before uninstalling a database release: `kubectl get pvc -n db`.

---

## Values Management

**Prefer values files over `--set`** for anything non-trivial. Values files are readable, diffable, and version-controllable. Use `--set` only for one-off overrides or secrets injected at deploy time.

**Precedence (last wins):** chart defaults → `--values file1.yaml` → `--values file2.yaml` → `--set key=value`

```bash
# Multiple values files — later files override earlier ones for the same key
helm install myapp repo/chart \
  -f base-values.yaml \
  -f env-specific-values.yaml \
  --set image.tag=abc123          # CI-injected; overrides both files
```

**Values file conventions:**
- Name files after the release: `postgres0_values.yaml`
- Add a comment at the top identifying the release and chart version
- Only include keys you're actually overriding — don't copy the full defaults

```yaml
# postgres0 - default postgres instance for the application
# Chart: bitnami/postgresql 16.4.9

architecture: standalone

global:
  defaultStorageClass: "local-path"
```

---

## Helm vs Raw Manifests

| Situation | Use |
|---|---|
| Third-party app with an official/verified chart | Helm — chart handles complexity, upgrades, and defaults |
| Your own application manifests | Raw `kubectl apply` — full control, no templating overhead |
| App with a chart from an unknown/unmaintained source | Raw manifests — copy what you need, own the result |
| Complex app with pre/post-install hooks or conditional resources | Helm — hooks and conditionals are where Helm earns its keep |

---

## Guide: Deploy pgvector-Enhanced PostgreSQL

This walkthrough deploys a PostgreSQL instance with the [pgvector](https://github.com/pgvector/pgvector) extension for vector similarity search. The Bitnami chart doesn't include pgvector, so we extend the base image.

### Step 1: Find the base image

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm show values bitnami/postgresql --version 16.4.9 > postgresql-defaults.yaml
# Look for the `.image` section to find the registry, repository, and tag
```

### Step 2: Build a custom image extending the base

```dockerfile
# 20.01.pgvector.dockerfile
# syntax=docker/dockerfile:1
FROM docker.io/bitnamilegacy/postgresql:17.3.0-debian-12-r0

# Switch to root to install system packages
USER root
RUN apt-get update && apt-get upgrade -y

# pgxnclient: PostgreSQL Extension Network client
# build-essential: needed to compile pgvector from source
RUN apt-get install -y pgxnclient build-essential

# Install pgvector via PGXN
RUN pgxn install vector

# Clean up to reduce image size
RUN apt-get clean && rm -rf /var/lib/apt/lists /var/cache/apt/archives

# Return to non-root user (1001 is the Bitnami convention)
USER 1001
```

Build and push:

```bash
docker build \
  --no-cache \
  --platform linux/amd64 \
  -t your-registry.example.com/pgvector:17.3.0-debian-12-r0 \
  - < 20.01.pgvector.dockerfile

docker push your-registry.example.com/pgvector:17.3.0-debian-12-r0
```

### Step 3: Write the values override file

```yaml
# 20.02.postgres0_values.yaml
# postgres0 - default postgres instance for the application
# Chart: bitnami/postgresql 16.4.9

architecture: standalone

global:
  defaultStorageClass: "local-path"
  security:
    allowInsecureImages: true    # required: our image isn't signed by Bitnami
  imagePullSecrets:
    - scaleway.registry    # flat string list — NOT {name: ...} objects (that's the K8s pod spec format)

image:
  registry: rg.fr-par.scw.cloud
  repository: chlabs-io/pgvector
  tag: 17.3.0-debian-12-r0      # pin to exact tag — database version compatibility is critical

primary:
  persistence:
    size: "20Gi"                 # vector data is large; size up accordingly
```

**Key decisions in this file:**
- `allowInsecureImages: true` — Bitnami enforces image signing; custom images need this opt-out
- `imagePullSecrets` — create the registry secret in the `db` namespace before installing
- Pinned image tag — for databases, even minor version changes can break data compatibility

### Step 4: Install

```bash
kubectl create namespace db

# Create registry pull secret in the target namespace
kubectl create secret docker-registry scaleway.registry \
  --docker-server=rg.fr-par.scw.cloud \
  --docker-username=<user> \
  --docker-password=<token> \
  --namespace db

helm install postgres0 bitnami/postgresql \
  --version 16.4.9 \
  --values 20.02.postgres0_values.yaml \
  --namespace db \
  --atomic
```

### Step 5: Verify and get credentials

```bash
helm list -n db
helm status postgres0 -n db

kubectl get all -n db
# Expect: StatefulSet postgres0-postgresql (1/1), two Services (ClusterIP + headless)

# Get the auto-generated postgres password
kubectl get secret postgres0 \
  --namespace db \
  -o jsonpath="{.data.postgres-password}" | base64 -d
```

### Step 6: Enable the extension

```bash
# Export password
export POSTGRES_PASSWORD=$(kubectl get secret --namespace db postgres0 \
  -o jsonpath="{.data.postgres-password}" | base64 -d)

# Run a temporary psql client pod (uses the custom pgvector image already in your registry)
kubectl run postgres0-client \
  --rm --tty -i --restart='Never' --namespace db \
  --image rg.fr-par.scw.cloud/chlabs-io/pgvector:17.3.0-debian-12-r0 \
  --overrides='{"spec":{"imagePullSecrets":[{"name":"scaleway.registry"}]}}' \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  --command -- psql --host postgres0-postgresql -U postgres
```

Inside psql:

```sql
-- Enable the extension (omit IF NOT EXISTS to surface errors if the image build failed)
CREATE EXTENSION "vector";

-- Verify it loaded correctly
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- Create a table with a vector column (3 dimensions for this example)
CREATE TABLE items (id bigserial PRIMARY KEY, embedding vector(3));

-- Insert test vectors
INSERT INTO items (embedding) VALUES ('[1,2,3]'), ('[4,5,6]');

-- Query by L2 distance (nearest neighbors)
SELECT * FROM items ORDER BY embedding <-> '[3,1,2]' LIMIT 5;
-- Returns row 1 ([1,2,3]) as closest, row 2 ([4,5,6]) as second
```

The `<->` operator is pgvector's L2 distance. Other operators: `<#>` (inner product), `<=>` (cosine distance).

---

## Quick Reference

```bash
# Repository management
helm repo add <name> <url>
helm repo update
helm repo list
helm repo remove <name>

# Discovery
helm search repo <term>
helm show values <chart> --version <ver>
helm show chart <chart>

# Release lifecycle
helm install <release> <chart> --version <ver> -f values.yaml -n <ns> --atomic
helm upgrade <release> <chart> --version <ver> -f values.yaml -n <ns> --atomic
helm history <release> -n <ns>
helm rollback <release> [revision] -n <ns>
helm uninstall <release> -n <ns>

# Inspection
helm list -A
helm status <release> -n <ns>
helm get notes <release> -n <ns>
helm get values <release> -n <ns>
```
