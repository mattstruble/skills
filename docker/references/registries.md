# Container Registry Setup

## AWS Elastic Container Registry (ECR)

**URL format:** `<account-id>.dkr.ecr.<region>.amazonaws.com/<namespace>/<repo>`

### One-time setup

1. Create repository in AWS Console → ECR → Create Repository
   - Enable **Tag Immutability** — prevents overwriting existing tags
   - Enable **Scan on Push** if compliance requires it
2. Create IAM user (e.g., `local.cli`) with a least-privilege inline policy:
   - Attach `AmazonEC2ContainerRegistryPowerUser` (push/pull, no admin) — or use a custom inline policy scoped to specific repository ARNs
   - Avoid `AmazonEC2ContainerRegistryFullAccess` — it grants delete/admin permissions not needed for push
   - **Prefer IAM Identity Center (SSO)** over static access keys: `aws configure sso` — SSO credentials are short-lived and don't require storing a secret
3. Generate access key under Security Credentials → Access Keys (only if SSO is unavailable)
4. Configure AWS CLI:
   ```bash
   aws configure
   # Enter: Access Key ID, Secret Access Key, region, output format
   ```

### Login (token expires after 12 hours)

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login \
    --username AWS \
    --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com
```

### Push

```bash
docker tag myapp:1.2.3 <account-id>.dkr.ecr.us-east-1.amazonaws.com/myns/myapp:1.2.3
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/myns/myapp:1.2.3
```

---

## Scaleway Container Registry

~10x cheaper than AWS ECR. No tag immutability or image scanning. Good for personal/small-team use.

**URL format:** `rg.<region>.scw.cloud/<namespace>/<repo>`  
**Regions:** `fr-par` (Paris), `nl-ams` (Amsterdam), `pl-waw` (Warsaw)

### One-time setup

1. Scaleway Console → Containers → Container Registry → Create namespace
   - Set privacy to **Private**
2. IAM → API Keys → Generate API Key (select yourself as bearer, set expiration)
3. Copy the Secret Key (UUIDv4 format)

### Login

```bash
# Secure: read secret from env var
echo "$SCW_SECRET_KEY" | docker login \
  --username nologin \
  --password-stdin \
  rg.fr-par.scw.cloud/my-namespace
```

### Push

Repositories are created automatically on first push — no pre-creation needed.

```bash
docker tag myapp:1.2.3 rg.fr-par.scw.cloud/my-namespace/myapp:1.2.3
docker push rg.fr-par.scw.cloud/my-namespace/myapp:1.2.3
```

Repository names support `/` for sub-grouping: `rg.fr-par.scw.cloud/ns/myapp/v2`.

---

## Docker Hub

Default registry for Docker CLI. Free for public images; paid for private. Use a Personal Access Token (PAT) rather than your account password — create one at hub.docker.com → Account Settings → Security → New Access Token.

### Login

```bash
echo "$DOCKERHUB_TOKEN" | docker login --username myuser --password-stdin
```

### Push

```bash
docker tag myapp:1.2.3 myuser/myapp:1.2.3
docker push myuser/myapp:1.2.3
```

---

## Managing Credentials

Stored credentials are in `~/.docker/config.json` (references OS keychain):

```bash
cat ~/.docker/config.json   # list registered registry hosts
docker logout rg.fr-par.scw.cloud   # remove credentials for a registry
```
