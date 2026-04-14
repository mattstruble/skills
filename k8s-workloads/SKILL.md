---
name: k8s-workloads
description: Use when creating or configuring Kubernetes workload resources — Deployments, StatefulSets, DaemonSets, Services, Jobs, or CronJobs. Also trigger when choosing between workload resource types, configuring rolling update strategies, setting up scheduled tasks, or wiring Services to Deployments. NOT for cluster setup (see k3s), networking/ingress (see k8s-networking), storage/ConfigMaps/Secrets (see k8s-storage), Helm charts (see helm), or advanced rollout strategies and probes (see k8s-operations).
---

# k8s-workloads

Patterns and decisions for Kubernetes workload resources in self-hosted environments.

---

## Workload Resource Decision

| Resource | Use when | Key trait |
|---|---|---|
| **Deployment** | Stateless apps (web servers, APIs) | Random Pod names, shared volumes, non-ordered updates |
| **StatefulSet** | Stateful apps (databases, queues) | Stable ordinal names (`db-0`, `db-1`), per-Pod PVCs, ordered updates |
| **DaemonSet** | One Pod per node (log agents, monitoring, storage managers) | Tied to node lifecycle; use `hostPath` volumes |
| **ReplicaSet** | Rarely used directly — Deployment manages it | Lower-level; only if you need custom Pod selection without rollout |
| **Job** | One-time tasks (migrations, load tests) | Runs to completion; retries on failure |
| **CronJob** | Recurring tasks (backups, reports) | Generates Jobs on a schedule |

**Default choice:** Deployment for anything stateless. StatefulSet for databases. CronJob for scheduled tasks.

---

## Deployment

### Minimal Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      imagePullSecrets:
        - name: registry-credentials
      containers:
        - name: my-app
          image: registry.example.com/my-app:1.0.0
          ports:
            - containerPort: 3000
              protocol: TCP
```

**Label/selector rule:** `spec.selector.matchLabels` must exactly match `spec.template.metadata.labels`. Mismatches cause the Deployment to reject the Pod template.

**Avoid dots in Deployment names** — they propagate to Pod names, which must be valid DNS labels. Use `my-app` not `my.app`.

### Production Deployment (with rolling update + liveness probe)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
  annotations:
    kubernetes.io/change-cause: v1.0.0   # shows in rollout history
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  minReadySeconds: 15   # wait 15s after container ready before marking Pod available
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0   # never drop below replica count during rollout
      # maxSurge defaults to 25% — allows one extra Pod to be created
  template:
    metadata:
      labels:
        app: my-app
    spec:
      imagePullSecrets:
        - name: registry-credentials
      containers:
        - name: my-app
          image: registry.example.com/my-app:1.0.0
          ports:
            - containerPort: 3000
          livenessProbe:
            initialDelaySeconds: 15   # delay before first check (acts as pseudo-startupProbe)
            periodSeconds: 20
            timeoutSeconds: 5
            failureThreshold: 3       # default; use 1 only for apps that must fail fast
            httpGet:
              path: /
              port: 3000
```

### Rolling Update Strategy

| Setting | Default | Recommendation |
|---|---|---|
| `maxUnavailable` | 25% | Set to `0` for zero-downtime — never fewer Pods than `replicas` |
| `maxSurge` | 25% | Leave at default (25%) unless you need to limit extra capacity |
| `minReadySeconds` | 0 | Set to 10–30s when no `readinessProbe` is defined |

> **Always define a `readinessProbe` for production Deployments.** Without one, traffic is routed to Pods that have started but may not yet be serving requests. `minReadySeconds` reduces (but does not eliminate) this window.

> **`maxUnavailable: 0` rollout hang:** If the new Pod never becomes ready (crash loop, failed probe), the rollout hangs indefinitely — old Pods stay up but the rollout never completes. Set `progressDeadlineSeconds` (default: 600s) to detect this and mark the Deployment as failed, then use `kubectl rollout undo` to recover. Note: `progressDeadlineSeconds` resets whenever any Pod transitions state — a Pod stuck in `Running` but never `Ready` (readiness probe always failing) can stall a rollout indefinitely even with this set. Define a `readinessProbe` with a bounded `failureThreshold × periodSeconds` to ensure the rollout eventually fails.

**`Recreate` strategy** — kills all Pods before creating new ones. Causes downtime. Only use when the app cannot run two versions simultaneously (e.g., exclusive DB schema migrations).

### Rollout commands

```bash
kubectl rollout status deployment/my-app -n production   # wait for completion
kubectl rollout history deployment/my-app -n production  # view change-cause annotations
kubectl rollout undo deployment/my-app -n production     # roll back to previous revision
kubectl set image deployment/my-app my-app=registry.example.com/my-app:1.1.0 -n production
```

Kubernetes keeps the last 10 revisions by default (`spec.revisionHistoryLimit`).

---

## Service

### Service Type Decision

| Type | Accessible from | Use when |
|---|---|---|
| **ClusterIP** (default) | Inside cluster only | Internal service-to-service communication — use this 90% of the time |
| **Headless** (`clusterIP: None`) | Inside cluster, returns Pod IPs | StatefulSet Pods that need direct addressing; custom load balancing |
| **NodePort** | Outside cluster via `<NodeIP>:<port>` | Custom external access without a load balancer; port range 30000–32767 |
| **LoadBalancer** | Outside cluster via external IP | HTTP/HTTPS ingress; k3s uses ServiceLB (Klipper) by default |
| **ExternalName** | Inside cluster → external DNS | Map a cluster-internal name to an external domain (CNAME redirect) |

**Default choice:** ClusterIP for everything internal. Use an Ingress controller (not LoadBalancer Services directly) for HTTP/HTTPS external traffic.

> **NodePort security:** NodePort binds on every node's IP, including public-facing interfaces. It bypasses Ingress-layer TLS and authentication. Restrict NodePort access at the cloud/host firewall to known source IPs.

### ClusterIP Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-app          # must be a valid RFC 1035 label: lowercase, alphanumeric, dashes only
  namespace: production
spec:
  type: ClusterIP
  selector:
    app: my-app         # must match Deployment's pod template labels
  ports:
    - protocol: TCP
      port: 80          # Service port (what callers use)
      targetPort: 3000  # Pod port (what the container listens on)
```

**DNS format:** `<service-name>.<namespace>.svc.<cluster-domain>` — e.g., `my-app.production.svc.cluster.local`

**Selector scope:** The Service selects every Pod with matching labels in the same namespace. Use specific label combinations (e.g., `app: my-app` + `tier: web`) to avoid accidentally routing to unrelated Pods.

---

## Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate
  namespace: production
spec:
  backoffLimit: 1              # retry once on failure (default: 6)
  completions: 1               # total successful completions required
  parallelism: 1               # max concurrent Pods
  completionMode: Indexed      # each Pod gets a unique index (0..N-1); use NonIndexed (default) for tasks where any completion counts
  ttlSecondsAfterFinished: 3600  # auto-delete after 1 hour (default: never)
  template:
    spec:
      restartPolicy: Never     # Never or OnFailure; not Always (that's for Deployments)
      containers:
        - name: migrate
          image: my-app:1.0.0
          command: ["/bin/sh", "-c"]
          args:
            - |
              set -e
              bun run migrate
```

**`restartPolicy: Never` vs `OnFailure`:**
- `Never` — failed Pod stays for log inspection; Job creates a new Pod for retries. Use this.
- `OnFailure` — container restarts in-place; logs may be overwritten.

**`ttlSecondsAfterFinished`** — always set this. Without it, completed Jobs and their Pods accumulate until manually deleted.

---

## CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
  namespace: db
spec:
  schedule: "0 */4 * * *"       # every 4 hours; use crontab.guru to verify
  concurrencyPolicy: Forbid      # Allow | Forbid | Replace
  failedJobsHistoryLimit: 10     # default: 1 — increase to retain failure logs
  successfulJobsHistoryLimit: 3  # default: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: worker
              image: ubuntu:24.04
              envFrom:
                - secretRef:
                    name: my-secrets
              volumeMounts:
                - name: scripts
                  mountPath: /etc/scripts
              command: ["/bin/bash", "-c"]
              args:
                - |
                  set -e
                  cd /tmp &&
                  cp -v /etc/scripts/* . &&
                  source install.sh &&
                  bun run task.ts
          volumes:
            - name: scripts
              configMap:
                name: my-scripts-abc123  # use --append-hash when creating
```

### CronJob concurrencyPolicy

| Value | Behavior | Use when |
|---|---|---|
| `Allow` (default) | New Job runs alongside previous | Queue processing, idempotent tasks |
| `Forbid` | Skip new Job if previous still running | Backups, file syncs — must not overlap |
| `Replace` | Kill previous Job, start new one | Tasks that must always run fresh |

**Test a CronJob immediately** without waiting for the schedule:

```bash
kubectl create job --from=cronjob/backup backup-now -n db
kubectl logs -f -l job-name=backup-now -n db
```

**Pass scripts via ConfigMap volume** (not baked into the image) when scripts change frequently. Use `--append-hash` when creating the ConfigMap so rollouts pick up script changes:

```bash
kubectl create configmap my-scripts \
  --from-file=install.sh \
  --from-file=task.ts \
  --append-hash \
  -n db
```

**Pass secrets via `envFrom.secretRef`** — loads all keys from the Secret as environment variables. Create from an env file:

```bash
kubectl create secret generic my-secrets \
  --from-env-file=.env \
  -n db
```

> **`.env` file hygiene:** Add `.env` to `.gitignore` before creating it. Delete the file after creating the Secret. Never commit a `.env` file containing real credentials.

For the complete S3 database backup guide (Kopia repository setup, pg_dump script, ConfigMap/Secret wiring, and testing), see [`references/s3-backup-cronjob.md`](references/s3-backup-cronjob.md).

---

## Label Conventions

Kubernetes recommends these standard labels on all resources:

```yaml
metadata:
  labels:
    app.kubernetes.io/name: my-app
    app.kubernetes.io/version: "1.0.0"
    app.kubernetes.io/part-of: my-platform
```

For Services selecting Pods, use multiple labels to avoid accidentally selecting unrelated Pods:

```yaml
selector:
  app: my-app
  tier: web
```
