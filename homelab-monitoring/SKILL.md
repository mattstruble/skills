---
name: homelab-monitoring
summary: Deploying Loki, Prometheus, Grafana, and Alertmanager on k3s or Docker Compose
type: reference
description: "You MUST consult this skill when deploying or operating a monitoring stack (Loki, Prometheus, Grafana, Alertmanager) on a homelab — k3s or Docker Compose. Also trigger when choosing a log collection agent (Alloy, Fluent Bit, Docker log driver), configuring retention, setting up alerting contact points (Discord, email, webhook), or troubleshooting Loki not ingesting logs, Prometheus showing 0 targets, or containers hanging due to the Docker log driver. NOT for query syntax (see logql, promql), dashboard authoring (see grafana), or cloud/EKS deployments."
---

# Homelab Monitoring

Loki + Prometheus + Grafana + Alertmanager on k3s or Docker Compose. No cloud, no GPU, no multi-tenancy — just a single-node or small-cluster homelab running services like Plex, *arr stack, Home Assistant, and AdGuard.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Collection Layer                                        │
│  Alloy (DaemonSet/container) ──► Loki  (logs)           │
│  node-exporter + app /metrics ──► Prometheus (metrics)  │
└─────────────────────────────────────────────────────────┘
                    │                    │
                    ▼                    ▼
              ┌─────────┐         ┌───────────┐
              │  Loki   │         │ Prometheus │
              │ (fs)    │         │ (local PV) │
              └────┬────┘         └─────┬─────┘
                   └──────────┬─────────┘
                              ▼
                         ┌─────────┐     ┌──────────────┐
                         │ Grafana │────►│ Alertmanager │
                         └─────────┘     └──────────────┘
```

Both Loki and Prometheus use **local filesystem storage** — no MinIO, no S3, no object store needed at homelab scale.

## Platform Decision

**Running k3s?** → See [references/k3s-deploy.md](references/k3s-deploy.md) for Helm-based deployment with kube-prometheus-stack, Grafana Operator CRDs, and Alloy DaemonSet.

**Docker Compose only?** → See [references/compose-deploy.md](references/compose-deploy.md) for a full docker-compose.yml with file-based Grafana provisioning.

## Log Collection Agent Decision

| Agent | Best For | Caveat |
|-------|----------|--------|
| **Alloy** | Grafana-native, handles logs + metrics, resilient to Loki downtime | Slightly more config than the Docker driver |
| **Docker Loki log driver** | Simplest possible setup, zero extra containers | ⚠️ **Blocks container stdout if Loki is unreachable** — containers hang, stop logging, or fail to start. Never use in production. |
| **Fluent Bit** | Multiple output destinations, complex parsing, non-Grafana stacks | More moving parts; overkill for a single-destination homelab |

**Recommendation:** Use Alloy. It's the official Grafana agent (Promtail reached EOL March 2026), handles both log and metric collection, and buffers locally when Loki is down.

## Storage and Retention

### Loki (filesystem)

```yaml
# In Helm values (grafana/loki chart)
loki:
  auth_enabled: false
  storage:
    type: filesystem
  commonConfig:
    replication_factor: 1
  limits_config:
    retention_period: 720h   # 30 days
  compactor:
    retention_enabled: true
    compaction_interval: 10m
    retention_delete_delay: 2h
```

Filesystem storage path: `/var/loki` (mount a PV or bind-mount here).

### Prometheus (local PV)

```yaml
prometheus:
  prometheusSpec:
    retention: 30d
    retentionSize: 10GB   # whichever hits first
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: local-path  # k3s default
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 20Gi
```

**Sizing guide:** ~1–2 bytes/sample at 30s scrape interval.
- 10 containers × 200 series each × 2 bytes × 2880 samples/day ≈ **~11 MB/day**
- 10 containers with node-exporter + kube-state-metrics ≈ **~150 MB/day** total
- 20 GB covers ~4 months at typical homelab scale

### Label cardinality discipline (Loki)

Keep labels **static and low-cardinality**: `app`, `container`, `host`, `namespace`. Never use request IDs, trace IDs, or user IDs as labels — use filter expressions instead (`|= "requestId=abc123"`). High-cardinality labels fragment streams and degrade query performance.

## Alerting Infrastructure

Alertmanager handles routing, deduplication, and delivery. It receives alerts from Prometheus (and optionally Loki ruler) and routes them to contact points.

### Alertmanager config

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'job']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'discord'
  routes:
    - match:
        severity: critical
      receiver: 'discord'
    - match:
        severity: warning
      receiver: 'email'

receivers:
  - name: 'discord'
    discord_configs:
      - webhook_url: 'https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN'
        title: '{{ .GroupLabels.alertname }}'
        message: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

  - name: 'email'
    email_configs:
      - to: 'you@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.example.com:587'
        auth_username: 'you@example.com'
        auth_password: 'your-app-password'

  - name: 'webhook'
    webhook_configs:
      - url: 'http://your-service:8080/alerts'
```

> Alert rule expressions (PromQL/LogQL) belong in the **promql** and **logql** skills. This section covers only the routing infrastructure.

## Troubleshooting

### Quick-check table

| Symptom | First check | Fix |
|---------|-------------|-----|
| Loki not ingesting | `curl http://loki:3100/ready` | See below |
| Prometheus 0 targets | `serviceMonitorSelectorNilUsesHelmValues` | Set to `false` |
| Alloy not collecting | `alloy status` or pod logs | Check Loki URL, auth |
| Container hung/not logging | Docker log driver in use | Switch to Alloy |
| Grafana "No data" | Datasource URL wrong | Check service name |
| Alerts not firing | Alertmanager not reachable | Check `alertmanagerUrl` |

### Loki not ingesting logs

1. Check Loki is ready: `curl http://loki:3100/ready` → should return `ready`
2. Check Alloy logs: `kubectl logs -n monitoring -l app.kubernetes.io/name=alloy` or `docker logs alloy`
3. Verify the push URL in Alloy config matches Loki's service name/port
4. Check for label cardinality errors: look for `too many streams` in Loki logs
5. Verify filesystem permissions on the Loki data directory

### Prometheus showing 0 targets

**This is the #1 gotcha with kube-prometheus-stack.** By default, Prometheus only discovers ServiceMonitors that have the same Helm release labels. ServiceMonitors you create manually are silently ignored.

**Fix — set these in your Helm values:**

```yaml
prometheus:
  prometheusSpec:
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false
```

Without this, `kubectl get servicemonitor` shows your monitors exist, but Prometheus never scrapes them.

### Alloy not collecting

1. Check Alloy pod is running: `kubectl get pods -n monitoring -l app.kubernetes.io/name=alloy`
2. Inspect Alloy config: verify `loki.write` endpoint URL
3. Check RBAC: Alloy needs `get/list/watch` on pods and namespaces
4. Test Loki connectivity from Alloy pod: `kubectl exec -it alloy-xxx -- curl http://loki:3100/ready`

### Docker log driver blocking containers

The Docker Loki log driver sends logs **synchronously** to Loki. If Loki is unreachable (restarting, OOM, misconfigured), Docker blocks the container's stdout write, which can:
- Cause containers to hang indefinitely
- Prevent new containers from starting
- Cause cascading failures across your stack

**Immediate fix:** Remove the log driver from the affected container and restart it:
```yaml
# Remove this from docker-compose.yml:
logging:
  driver: loki
  options:
    loki-url: "http://loki:3100/loki/api/v1/push"
```

**Long-term fix:** Switch to Alloy for log collection. Alloy runs as a separate process, buffers locally, and never blocks your application containers.

## Security

Homelab doesn't mean insecure. Three rules:

1. **Never commit secrets.** Use `.env` files (Compose) or Kubernetes Secrets (k3s). Add `.env` to `.gitignore`.
2. **Bind internal services to localhost.** Loki, Prometheus, and Alertmanager don't need network exposure — only Grafana needs to be reachable. In Compose: `127.0.0.1:3100:3100`.
3. **Change defaults before first boot.** Generate passwords: `openssl rand -base64 24`. The reference files show `.env` patterns for this.

If you ever expose Loki or Grafana beyond your LAN (reverse proxy, VPN exit), enable `auth_enabled: true` on Loki and put an auth proxy in front.

## Upgrade Paths

These are one-line decisions — don't add them until you hit the specific need:

- **Tempo**: Add when you build custom instrumented services that call each other (distributed tracing)
- **Mimir**: Add when you need >90 days metrics retention or multiple Prometheus instances
- **OTEL Collector**: Add when you need a vendor-neutral pipeline or multiple telemetry backends

## Related Skills

- **logql** — LogQL query syntax for Loki log queries
- **promql** — PromQL query syntax for Prometheus metrics
- **k3s** — k3s cluster setup and management
- **docker** — Docker Compose and container configuration
