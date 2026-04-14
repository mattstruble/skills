---
name: k8s-operations
description: Use when configuring health probes (liveness, readiness, startup), choosing or tuning rollout strategies, writing deployment automation scripts or CI/CD pipelines, hardening a self-hosted cluster, tuning the NGINX Ingress controller for caching/compression/rate limiting, setting resource limits, or maintaining nodes. Also trigger on server security (fail2ban, ufw, SSH hardening), Ansible automation for server management, or kubectl operational commands (drain, debug, events). NOT for cluster setup (see k3s), workload resource definitions (see k8s-workloads), networking/TLS (see k8s-networking), storage/config (see k8s-storage), or Helm (see helm).
---

# k8s-operations

Day-2 operations for self-hosted Kubernetes: probes, rollouts, deployment automation, and cluster hardening.

---

## Probe Decision

| Probe | Purpose | Failure action | Use when |
|---|---|---|---|
| **startupProbe** | Container started successfully | Restart container; blocks liveness/readiness | App takes >30s to initialize (slow JVM, model loading) |
| **livenessProbe** | Container is still healthy | Restart container | Deadlocks, memory leaks, stuck processes |
| **readinessProbe** | Container is ready to serve traffic | Remove from Service endpoints (no restart) | Always — prevents traffic to unready pods |

**Recommendation:** Always define both `readinessProbe` and `livenessProbe`. Use `startupProbe` only for slow-starting containers. Never use `livenessProbe` alone — without `readinessProbe`, traffic routes to pods that aren't ready.

**Probe interaction:** `readinessProbe` and `livenessProbe` run independently. A pod can be restarted (liveness failure) while still passing readiness, or removed from endpoints (readiness failure) while liveness succeeds. Set `livenessProbe.failureThreshold` higher than `readinessProbe.failureThreshold` to give the pod a chance to recover before restarting.

### Probe Configuration Patterns

**Standard web app (readiness + liveness, same endpoint):**

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 3000
  initialDelaySeconds: 10     # wait before first check (pseudo-startupProbe)
  timeoutSeconds: 10
  periodSeconds: 30
  failureThreshold: 3         # restart after 3 consecutive failures (90s window)

readinessProbe:
  httpGet:
    path: /healthz
    port: 3000
  initialDelaySeconds: 15
  timeoutSeconds: 3
  failureThreshold: 1         # remove from endpoints immediately on failure
  successThreshold: 1
  periodSeconds: 15
```

**Slow-starting container (startup + liveness):**

```yaml
startupProbe:
  httpGet:
    path: /healthz
    port: 8080
  failureThreshold: 30        # allows up to 5 minutes (30 × 10s) to start
  periodSeconds: 10

livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  failureThreshold: 1
  periodSeconds: 10
```

**Health check endpoint** — check all dependencies (DB, cache, self-render):

```typescript
// /healthz — checks Postgres, Redis, and self-render
export const loader: LoaderFunction = async ({ request }) => {
  await dataSource.getRepository(User).count();           // DB reachable
  const key = `healthcheck:${Math.random()}`;
  await redisClient.set(key, "1", "EX", 30);
  if (await redisClient.get(key) !== "1") throw Error("Redis read failed");
  // Use localhost — do NOT use request host header (SSRF risk via X-Forwarded-Host)
  const port = process.env.PORT ?? 3000;
  const res = await fetch(`http://localhost:${port}/`, { method: "HEAD" });
  if (!res.ok) throw Error("Self-render failed");
  return new Response("OK");
};
```

---

## Rollout Strategy Decision

| Strategy | Downtime | Resources | Use when |
|---|---|---|---|
| **RollingUpdate** (default) | None | +`maxSurge` pods | Standard deployments; always prefer this |
| **Recreate** | Yes | No extra | App cannot run two versions simultaneously (exclusive DB schema) |
| **Blue/Green** | None | 2× | Atomic cutover needed; requires double resources at rollout time |
| **Canary** | None | Small % extra | Large deployments with monitoring; needs metrics to gate progression |

**Recommendation:** Use `RollingUpdate` with `maxUnavailable: 0` for zero-downtime. Do not use `maxUnavailable: 1` — with 3 replicas, that drops capacity to 2/3 during rollout and risks downtime if another pod fails simultaneously. `maxUnavailable: 0` ensures replica count never drops below the desired value. Blue/Green and Canary require additional tooling (Argo Rollouts, Flagger) for production use.

### Production Deployment Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: production
  annotations:
    kubernetes.io/change-cause: v0.0.2    # visible in rollout history
spec:
  replicas: 3
  revisionHistoryLimit: 10
  minReadySeconds: 60                     # pod must stay Ready 60s before old pod is deleted
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%                       # ceil(25% × 3) = 1 extra pod during rollout
      maxUnavailable: 0                   # ZERO, not 1 — never drop below replica count; use maxSurge to add capacity instead
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      terminationGracePeriodSeconds: 120  # time to finish in-flight requests
      imagePullSecrets:
        - name: registry-credentials
      containers:
        - name: my-app
          image: registry.example.com/my-app:0.0.2
          env:
            - name: APP_VERSION
              value: "0.0.2"
          ports:
            - containerPort: 3000
              protocol: TCP
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
          livenessProbe:
            httpGet:
              path: /healthz
              port: 3000
            initialDelaySeconds: 10
            timeoutSeconds: 10
            periodSeconds: 30
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /healthz
              port: 3000
            initialDelaySeconds: 15
            timeoutSeconds: 3
            failureThreshold: 1
            successThreshold: 1
            periodSeconds: 15
```

### Rollout Commands

```bash
kubectl rollout status deployment/my-app -n production    # watch until complete
kubectl rollout history deployment/my-app -n production   # view change-cause log
kubectl rollout undo deployment/my-app -n production      # roll back to previous
kubectl rollout undo deployment/my-app -n production --to-revision=3    # roll back to specific revision
kubectl rollout pause deployment/my-app -n production     # halt mid-rollout
kubectl rollout resume deployment/my-app -n production    # resume paused rollout
```

**Rollout hang with `maxUnavailable: 0`:** If the new pod never becomes Ready, the rollout stalls indefinitely — old pods stay up but the rollout never completes. Set `progressDeadlineSeconds` (default: 600s) and define a `readinessProbe` with bounded `failureThreshold × periodSeconds` so the rollout eventually fails and can be undone.

---

## Resource Limits

Always set resource limits on all pods. Without them, a single pod can exhaust node resources and affect the entire cluster.

```yaml
resources:
  requests:
    cpu: "100m"       # reserved for scheduling; 100m = 0.1 CPU core
    memory: "128Mi"
  limits:
    cpu: "500m"       # hard cap; CPU is throttled (not killed) when exceeded
    memory: "512Mi"   # hard cap; pod is OOMKilled when exceeded
```

**Layered resource management:**
1. **ResourceQuota** per namespace — caps total CPU/memory for all pods in a namespace; start at 50% of cluster total
2. **LimitRange** per namespace — sets default requests/limits for pods that don't specify them; critical in multi-tenant clusters
3. **Per-pod limits** — set based on observed usage (`kubectl top pod -A`) plus a safety margin

**Autoscaling:** Use `HorizontalPodAutoscaler` (HPA) with CPU/memory targets for stateless workloads. CoreDNS is the first component to scale under cluster-wide load. For event-driven scaling, use KEDA.

---

## Key Best Practices Summary

- **Never use `:latest` tag** — pin to a specific semver or build-stamped tag (e.g., `1.2.3` or `20260414-143022`)
- **Set `terminationGracePeriodSeconds`** to at least the longest expected request duration (default 30s is often too short)
- **Put related resources in one YAML file** separated by `---` — easier to manage and apply atomically
- **Watch events first** when debugging: `kubectl events --types=Warning --all-namespaces --watch`
- **Drain nodes before maintenance**: `kubectl drain <node> --delete-emptydir-data=true --ignore-daemonsets --timeout=360s`
- **Enable automatic security updates** via `unattended-upgrades` (default on Ubuntu 24.04)
- **Use operators** for stateful services in production: CloudNativePG (Postgres), Rook (storage), prometheus-operator (monitoring)

For deployment automation (build → push → rollout → auto-rollback script + GitHub Actions), see [`references/deployment-automation.md`](references/deployment-automation.md).

For server hardening, ingress tuning, Ansible automation, and operational tools, see [`references/best-practices.md`](references/best-practices.md).
