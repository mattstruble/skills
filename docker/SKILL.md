---
name: docker
description: Use when writing Dockerfiles, Docker Compose files, building or debugging container images, choosing base images, pushing to registries, or running containers locally. Also trigger when asked about multi-stage builds, .dockerignore, container networking, volumes, or self-hosting an application with Docker. NOT for Kubernetes workloads (see k8s-workloads), Helm charts (see helm), Docker in CI pipelines (see github-actions), or GPU operator configuration (see gpu-operator).
---

# Docker

Patterns and decisions for containerizing applications and managing containers locally or in self-hosted environments.

---

## Dockerfile: Single-Stage vs Multi-Stage

**Use single-stage** only for interpreted languages where you don't need a separate build step (e.g., Python running directly, simple shell scripts).

**Use multi-stage for everything else.** The size difference is dramatic: a single-stage Node.js image is ~1.9 GB uncompressed; the equivalent multi-stage image is ~607 MB (75% smaller after compression). Multi-stage also prevents source code, dev dependencies, and build secrets from leaking into the final image.

### Single-stage (basic — has known problems)

```dockerfile
# syntax=docker/dockerfile:1
FROM node:24.7-trixie

WORKDIR /usr/src/app

COPY . .
RUN npm ci
RUN npm run build

ENV NODE_ENV=production
CMD npm run start   # ← shell form: doesn't forward OS signals (use exec form)
EXPOSE 3000
```

Problems with this: (1) source code and dev deps remain in the image, (2) no cache optimization — deps reinstall on every code change, (3) shell form `CMD` doesn't forward `SIGTERM` to the process.

### Multi-stage (production-ready)

```dockerfile
# syntax=docker/dockerfile:1

# stage 1: build
FROM node:24-bookworm-slim AS builder

WORKDIR /usr/src/app
COPY package*.json ./       # copy lockfile first — maximizes cache hits
RUN npm ci

COPY . .
RUN npm run build
RUN npm prune --omit=dev --omit=optional  # removes dev + optional deps

# stage 2: runtime
FROM node:24-alpine AS runner

WORKDIR /usr/src/app
COPY --chown=65534:65534 --from=builder /usr/src/app/node_modules ./node_modules
COPY --chown=65534:65534 --from=builder /usr/src/app/package.json ./package.json
COPY --chown=65534:65534 --from=builder /usr/src/app/.next ./.next
COPY --chown=65534:65534 --from=builder /usr/src/app/public ./public

EXPOSE 3000
ENV NODE_ENV=production
USER 65534:65534
CMD ["npm", "run", "start"]   # exec form: forwards signals correctly
```

**Why this ordering matters for cache:** Copy `package*.json` and install deps *before* copying application code. Deps change rarely; code changes constantly. Docker invalidates cache at the first changed layer — if you copy everything first, deps reinstall on every code change.

---

## Base Image Selection

| Situation | Reach for | Why |
|---|---|---|
| Build stage (needs compilers, tools) | `<lang>:<version>-slim` or `<lang>:<version>-bookworm` | Full toolchain, Debian base |
| Runtime stage (just needs to run) | `<lang>:<lts-version>-alpine` | Minimal attack surface, smallest size |
| System-level tools needed at runtime | `<lang>:<version>-bookworm-slim` | Debian without extras |
| Scratch binary (Go, Rust static builds) | `scratch` or `gcr.io/distroless/static` | Zero OS overhead |

**Never use `latest` in production.** Pin to at least a major version tag (`node:24-alpine`, not `node:alpine`). For maximum reproducibility, pin to a patch version (`node:24.7-alpine`). `latest` is a moving target that breaks reproducibility.

**Alpine trade-off:** Alpine uses musl libc instead of glibc. Most apps work fine, but some native extensions (certain Python packages, some Node.js addons) require glibc. If you hit mysterious runtime errors with Alpine, switch to `-slim` (Debian-based).

### Distroless and Minimal Runtime Images

Distroless images strip out the shell, package manager, and OS utilities entirely. Less software means fewer CVEs and a smaller attack surface — an attacker who gains code execution can't use `curl`, `wget`, or `bash` if they don't exist in the image.

| Image | Use case |
|---|---|
| `gcr.io/distroless/static` | Go, Rust, any static binary (includes CA certs, tzdata, `/etc/passwd`) |
| `gcr.io/distroless/base` | C/C++ needing glibc (adds glibc and OpenSSL runtime libraries (libssl, libcrypto)) |
| `gcr.io/distroless/nodejs22-debian12` | Node.js apps |
| `gcr.io/distroless/python3-debian12` | Python apps |

Unversioned tags (`/nodejs`, `/python3`) exist but are not pinned to a runtime version.

**Go example** — static binary into distroless:

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.23-bookworm AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -o /app/server ./cmd/server

FROM gcr.io/distroless/static AS runner
COPY --from=builder /app/server /server
USER nonroot  # distroless provides this user (UID 65532)
EXPOSE 8080
ENTRYPOINT ["/server"]
```

**Limitation:** No package manager means you can't install missing shared libraries at runtime. Native extensions requiring uncommon `.so` files may not work — use `gcr.io/distroless/base` (glibc) or fall back to Alpine if you need more.

**`FROM scratch`** is the extreme version: zero OS layer, static binary only. Works for Go (`CGO_ENABLED=0`) and Rust when targeting musl (`cargo build --target x86_64-unknown-linux-musl`). On glibc hosts, `-C target-feature=+crt-static` alone does not produce a fully static binary. Not practical for interpreted languages.

**Debugging without a shell (Linux hosts only):** `nsenter` runs host binaries inside a container's namespace. This does not work on macOS or Windows — Docker Desktop runs containers in a VM whose PIDs aren't accessible from the host.

```bash
# Requires root on the host; -n enters the network namespace only
PID=$(docker inspect -f '{{.State.Pid}}' container_name)
[ "$PID" -gt 0 ] && sudo nsenter -t "$PID" -n ss -tulpn || echo "container not running"
```

The `-n` flag is the least-privileged option — it only enters the network namespace. Avoid `-a` or `-m` in production; they give full filesystem and process access, equivalent to `docker exec` as root.

---

## Build Cache Optimization

Order Dockerfile instructions from least-changing to most-changing:

1. Base image (`FROM`)
2. System packages (`RUN apt-get install`)
3. Dependency manifests (`COPY package*.json ./`)
4. Dependency install (`RUN npm ci`)
5. Application code (`COPY . .`)
6. Build step (`RUN npm run build`)

**BuildKit cache mounts** (avoid reinstalling packages on every build):

```dockerfile
# npm — cache must be explicitly pointed to the mount target with npm ci
RUN --mount=type=cache,target=/root/.npm \
    npm ci --cache /root/.npm

# pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Go
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go build -o /app/server
```

**Bind mounts for build-only files** (don't copy into the layer):

```dockerfile
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt \
    pip install --requirement /tmp/requirements.txt
```

---

## .dockerignore

Always create `.dockerignore` at the build context root. Unlike `.gitignore`, Docker only reads one `.dockerignore` at the context root — subdirectory ignore files are not respected.

```
.git
.gitignore
node_modules
.env
.env.*
*.log
dist
.next/cache
__pycache__
*.pyc
.pytest_cache
```

Omitting `.dockerignore` means `COPY . .` sends your entire git history, local node_modules, and `.env` files into the build context — slowing builds and risking secret leakage.

---

## CMD vs ENTRYPOINT

**Use exec form (JSON array) for both.** Shell form (`CMD npm start`) wraps the command in `/bin/sh -c`, making the shell the PID 1 process. The shell doesn't forward `SIGTERM` to child processes, so `docker stop` kills the container forcefully instead of gracefully.

```dockerfile
# Shell form — PID 1 is /bin/sh, signals not forwarded
CMD npm run start

# Exec form — PID 1 is npm, SIGTERM forwarded correctly
CMD ["npm", "run", "start"]
```

**ENTRYPOINT vs CMD:**
- `ENTRYPOINT` — fixed executable, not easily overridden at runtime
- `CMD` — default arguments, easily overridden with `docker run <image> <args>`
- Combined: `ENTRYPOINT` sets the executable, `CMD` provides default args that can be overridden

```dockerfile
# Image acts as a CLI tool
ENTRYPOINT ["s3cmd"]
CMD ["--help"]   # default: show help; override: docker run myimage ls s3://bucket
```

---

## Running as Non-Root

Always include a `USER` directive in production Dockerfiles. Docker defaults to root (UID 0), which carries capabilities like `cap_chown` and `cap_net_raw` that can be exploited if a process is compromised. Combine `USER` with `no-new-privileges=true` and `cap_drop: [ALL]` in Compose to fully eliminate capability escalation paths — a non-root process's effective capabilities are empty, but the permitted set is still inherited from the container's bounding set without these.

**Create a dedicated user and switch to it:**

```dockerfile
# Alpine / BusyBox
RUN addgroup -g 65534 appgroup && \
    adduser -u 65534 -G appgroup -D -H appuser

# Debian / Ubuntu
RUN groupadd --gid 65534 appgroup && \
    useradd --uid 65534 --gid appgroup --no-create-home --shell /sbin/nologin appuser

USER 65534:65534
```

Or skip user creation entirely and use `USER 65534:65534` with a numeric UID — the user doesn't need to exist in `/etc/passwd` for most applications.

Place `USER` as the last directive before `ENTRYPOINT`/`CMD`. Using numeric UID:GID (not name) works in distroless images that lack `/etc/passwd` entries.

**Volume permissions:** Files written by the container will be owned by UID 65534 on the host. Two options:
- `chown 65534:65534 /host/path` before mounting
- Override in Compose with `user: "1000:1000"` to match your host UID

**Compose hardening:**

```yaml
services:
  app:
    image: myapp:1.0.0
    user: "65534:65534"
    security_opt:
      - no-new-privileges=true   # prevents setuid/setgid escalation
    cap_drop:
      - ALL                      # drop all capabilities; add back specific ones if needed
    read_only: true              # optional: make root filesystem read-only
    tmpfs:
      - /tmp                     # writable scratch space if needed
```

`no-new-privileges=true` prevents the process from gaining additional privileges via setuid binaries or file capabilities — a defense-in-depth measure even when already running as non-root.

**PUID/PGID images:** Images using `PUID`/`PGID` environment variables (common in LinuxServer.io images) still start the entrypoint as root before dropping privileges. Prefer images that set `USER` to never run as root at all.

**Kubernetes:** Clusters can enforce non-root at the pod level with `securityContext.runAsNonRoot: true` — containers that would run as UID 0 will fail to **start** with a `RunAsNonRoot` violation error.

---

## Docker Compose

Use Compose for local development and simple self-hosted deployments. It is not a substitute for Kubernetes: no self-healing, no rolling updates, no secret management, single-machine only.

**Canonical file name:** `compose.yaml` (preferred) or `docker-compose.yaml`. Docker Compose looks for these automatically in the current directory.

### Minimal production-ready Compose file

```yaml
name: my_app

services:
  db:
    image: postgres:17-bookworm
    container_name: postgres_db
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # read from .env file
    # Alternative: env_file loads all vars from file; if both are set, 'environment' takes precedence
    # env_file: .env
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      retries: 5
      start_period: 30s
      timeout: 5s
    networks:
      - internal  # no ports published — DB is only reachable from web via internal network

  web:
    build: .
    depends_on:
      db:
        condition: service_healthy  # wait for DB to be ready, not just started
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD}@db:5432/app
    networks:
      - internal   # can reach db
      - default    # can reach internet (for external API calls, etc.)

volumes:
  postgres_data:

networks:
  internal:
    driver: bridge
    internal: true  # no internet — db is only reachable from web, not from outside
  default: {}       # standard bridge with internet access for web
```

**Key patterns:**
- Use `depends_on` with `condition: service_healthy` (not just `service_started`) to avoid race conditions
- Never hardcode secrets in `compose.yaml` — use `${VAR}` with `.env` file or `env_file`
- Use named volumes (not bind mounts) for database data — named volumes survive `compose down`
- `compose down` removes containers and networks but **not** volumes; add `--volumes` to also remove data

### Compose commands

```bash
docker compose up --detach          # start all services in background
docker compose up --detach --build  # rebuild images before starting
docker compose down                 # stop and remove containers + networks
docker compose down --volumes       # also remove named volumes (⚠ DESTROYS all volume data — irreversible)
docker compose logs -f web          # stream logs for a service
docker compose ps                   # list running services
docker compose exec db psql -U postgres  # shell into a running service
docker compose watch                # rebuild/sync on file changes (dev mode)
docker compose -f custom.yaml up    # use a non-default compose file
docker compose -p myproject ps      # target a project by name
```

For Docker daemon hardening (log rotation, storage, network subnets), see [`references/daemon-config.md`](references/daemon-config.md).

---

## Container Lifecycle (CLI Essentials)

```bash
# Run a stateful service (database) — no --rm, container survives stops
docker container run \
  --detach \
  --name postgres_db \
  --env POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \   # use env var — never hardcode; visible in docker inspect
  --volume postgres_data:/var/lib/postgresql/data \
  --publish 127.0.0.1:5432:5432 \   # bind to localhost only — 0.0.0.0 exposes to all interfaces
  postgres:17-bookworm

# Run an ephemeral one-off task — --rm auto-removes when done
docker container run --rm -it ubuntu:24.04 bash

# Inspect and debug
docker container logs -f <name>   # stream logs
docker container exec -it <name> /bin/bash  # interactive shell
docker container inspect <name>   # full JSON metadata
docker container stats <name>     # live CPU/memory/network metrics

# Lifecycle
docker container stop <name>      # SIGTERM → SIGKILL after timeout
docker container start <name>
docker container restart <name>
docker container rm <name>        # remove stopped container
docker container prune            # remove all stopped containers
```

**Expose vs publish:** `EXPOSE` in a Dockerfile is documentation only — it doesn't make the port accessible. `--publish` (or `-p`) at runtime maps a container port to the host. A service can be accessible without `EXPOSE` if you publish the port.

---

## Volumes and Networks

```bash
# Volumes
docker volume create postgres_data
docker volume inspect postgres_data
docker volume rm postgres_data
docker volume prune --all         # ⚠ removes ALL unused volumes on this host, across all projects

# Networks
docker network create --driver bridge --internal no_internet
docker network connect no_internet my_container
docker network disconnect no_internet my_container
docker network inspect no_internet
```

**User-defined bridge networks** (not the default `bridge`) enable DNS resolution by container name. Containers on the same user-defined network can reach each other at `http://container-name:port`. The default `bridge` network does not support this.

### Named Volumes with Remote Backends

Named volumes aren't limited to local disk. The `local` driver accepts `driver_opts` to mount NFS shares, CIFS/SMB shares, or tmpfs:

> **Host prerequisites:** NFS requires `nfs-common` (Debian/Ubuntu) or `nfs-utils` (RHEL/Alpine). CIFS requires `cifs-utils`. Without these, `docker compose up` fails with a cryptic mount error.

```yaml
volumes:
  # NFS share
  nfs_data:
    driver: local
    driver_opts:
      type: nfs
      o: "addr=192.168.1.30,nolock,hard,timeo=600,retrans=3,nfsvers=4"
      device: ":/volume1/appdata"

  # CIFS/SMB share
  smb_data:
    driver: local
    driver_opts:
      type: cifs
      o: "username=svc_user,password=${SMB_PASSWORD},uid=65534,gid=65534,vers=3.0"
      device: "//192.168.1.40/appdata"

  # tmpfs (in-memory, cleared on restart — good for scratch/cache)
  tmp_cache:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: "size=256m,uid=65534,gid=65534"
```

> **NFS mount modes:** Use `hard` (shown above) for stateful workloads — databases, write-ahead logs, anything using `fsync`. A `hard` mount retries indefinitely rather than returning errors on transient network blips. Use `soft` only for read-heavy or cache workloads where data loss is tolerable — a timed-out `soft` write may be partially committed, corrupting data.

> **CIFS credentials:** Credentials passed via `driver_opts` are stored in plaintext in Docker's volume metadata (visible via `docker volume inspect`). For production, use a credentials file with restricted permissions (`chmod 600`) mounted separately, rather than embedding the password in volume options.

Prefer named volumes over bind mounts. Docker manages creation, permissions, and quotas. Use bind mounts only when you need a specific host path (e.g., `/etc/localtime`, a hardware device, or a path managed by another tool).

---

## Building and Tagging Images

```bash
# Build
docker buildx build \
  --platform linux/amd64 \        # target platform (default: host arch)
  --tag registry.example.com/myapp:1.2.3 \
  --file path/to/Dockerfile \
  ./build-context/

# Tag format: <registry-host>/<namespace>/<repository>:<version>
# Avoid 'latest' — use semantic versions or git SHAs

# Inspect
docker image inspect myapp:1.2.3
docker image history myapp:1.2.3  # show layers and sizes
# Use 'dive' for interactive layer exploration

# Cleanup
docker image prune --all          # ⚠ removes ALL unused images — next start requires re-pulling from registry
```

---

## Container Registries

See [`references/registries.md`](references/registries.md) for registry-specific setup (AWS ECR, Scaleway, Docker Hub).

**Login pattern:**

```bash
# Generic (POSIX-portable)
echo "$TOKEN" | docker login --username <user> --password-stdin <registry-host>

# AWS ECR (token expires after 12 hours)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin \
    <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Push workflow
docker tag myapp:1.2.3 registry.example.com/ns/myapp:1.2.3
docker push registry.example.com/ns/myapp:1.2.3
```

**Tag immutability:** Enable it on private registries (AWS ECR supports this). Mutable tags mean two different images can share the same tag — a silent source of "works on my machine" bugs.

**Credentials** are stored in `~/.docker/config.json` (pointing to the OS keychain). View registered registries: `cat ~/.docker/config.json`. Log out: `docker logout <registry-host>`.
