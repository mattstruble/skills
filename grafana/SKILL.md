---
name: grafana
summary: Grafana dashboard authoring, template variables, IaC provisioning, and alerting
type: reference
description: "You MUST consult this skill when authoring Grafana dashboards, configuring panels or template variables, wiring datasources, or setting up alerting rules and contact points. Also trigger on GrafanaDashboard/GrafanaDatasource CRDs (Grafana Operator), file-based provisioning for Docker Compose, Discord/email alert routing, and drilldown dashboard design. NOT for PromQL query syntax (see promql), LogQL syntax (see logql), or deploying the monitoring stack (see homelab-monitoring)."
---

# Grafana

Homelab-focused Grafana skill covering dashboard authoring, template variables, IaC provisioning (Grafana Operator CRDs and file-based), and alerting.

**Two IaC paths:**
- **k3s**: Grafana Operator CRDs (`GrafanaDashboard`, `GrafanaDatasource`) — GitOps-friendly
- **Compose**: File-based provisioning — JSON dashboards + YAML provider configs mounted into the container

See [`references/crd-examples.md`](references/crd-examples.md) for full YAML examples of both paths.

---

## Dashboard JSON Model

Every dashboard is a JSON object. Key top-level fields:

```json
{
  "title": "Homelab Overview",
  "uid": "homelab-overview",
  "schemaVersion": 38,
  "time": { "from": "now-6h", "to": "now" },
  "refresh": "30s",
  "templating": { "list": [] },
  "annotations": { "list": [] },
  "panels": []
}
```

- `uid`: stable identifier — used in dashboard links and provisioning; keep it short and slug-like
- `schemaVersion`: use **38+** (current stable)
- `refresh`: omit or set `""` to disable auto-refresh; `"30s"` is a good homelab default

### Panel Structure

```json
{
  "type": "timeseries",
  "title": "Request Rate",
  "gridPos": { "x": 0, "y": 0, "w": 12, "h": 8 },
  "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
  "targets": [
    {
      "expr": "rate(http_requests_total{job=\"$service\"}[$__rate_interval])",
      "legendFormat": "{{method}} {{status}}"
    }
  ],
  "options": {},
  "fieldConfig": {
    "defaults": { "unit": "reqps" },
    "overrides": []
  }
}
```

- `gridPos`: 24-column grid; `w: 24` = full width, `w: 12` = half
- `datasource.uid`: use `${DS_PROMETHEUS}` or `${DS_LOKI}` so the dashboard is portable across instances
- `targets[].expr`: parameterize with variables like `$service`, `$container`

### Panel Type Decision Table

| Type | Use When |
|------|----------|
| `timeseries` | Values over time — CPU, memory, request rate, error rate |
| `stat` | Single current value — uptime status, current temp, active streams |
| `gauge` | Value within a bounded range — disk %, memory %, queue fill |
| `table` | Multi-column data — per-service breakdown, top-N lists |
| `logs` | Raw log lines from Loki |
| `barchart` | Categorical comparison — requests per service, errors by type |
| `row` | Collapsible section header — group panels by concern |

---

## Template Variables

Variables appear as dropdowns at the top of the dashboard. Every panel query that uses `$variable` syntax updates when the variable changes.

### Variable JSON (inside `templating.list`)

**Query variable** — values come from a datasource query:

```json
{
  "name": "service",
  "type": "query",
  "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
  "query": {
    "query": "label_values(up, job)",
    "refId": "StandardVariableQuery"
  },
  "refresh": 2,
  "sort": 1,
  "multi": false,
  "includeAll": true,
  "allValue": ".*",
  "label": "Service"
}
```

**Chained variable** — `$instance` options depend on `$service`:

```json
{
  "name": "instance",
  "type": "query",
  "query": {
    "query": "label_values(up{job=\"$service\"}, instance)"
  },
  "refresh": 2
}
```

When `$service` changes, Grafana re-queries the `$instance` options automatically.

**Container variable for Loki:**

```json
{
  "name": "container",
  "type": "query",
  "datasource": { "type": "loki", "uid": "${DS_LOKI}" },
  "query": { "label": "container", "stream": "{}" },
  "refresh": 2
}
```

> Note: Loki variables use `{"label": "...", "stream": "..."}` — not `label_values()` which is Prometheus-only.

### Using Variables in Queries

```promql
# Prometheus — filter by variable
rate(container_cpu_usage_seconds_total{container="$container"}[$__rate_interval])

# Loki — filter log stream
{container="$container"} |= "error"
```

### Built-in Variables

| Variable | Value |
|----------|-------|
| `$__interval` | Calculated step interval for the current time range |
| `$__rate_interval` | Safe interval for `rate()` — always ≥ 4× scrape interval |
| `$__range` | Duration of the selected time range (e.g., `6h`) |
| `$__from` / `$__to` | Time range as epoch milliseconds |

Use `$__rate_interval` instead of a hardcoded window in `rate()` — it adapts to zoom level.

---

## Datasource Configuration

### k3s Path — Grafana Operator CRDs

The Grafana Operator manages a `Grafana` custom resource (CR) in your cluster. Every `GrafanaDatasource` and `GrafanaDashboard` CRD must have an `instanceSelector` that matches the labels on that Grafana CR. The homelab standard is `dashboards: grafana`.

> **If datasources or dashboards don't appear:** Verify the Grafana CR has the matching label: `kubectl get grafana -n monitoring --show-labels`. The operator silently skips CRDs whose `instanceSelector` doesn't match — no error is emitted to the resource status.

```yaml
# Prometheus datasource
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDatasource
metadata:
  name: prometheus
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  datasource:
    name: Prometheus
    type: prometheus
    url: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
    access: proxy
    isDefault: true
    jsonData:
      timeInterval: "30s"
```

```yaml
# Loki datasource
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDatasource
metadata:
  name: loki
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  datasource:
    name: Loki
    type: loki
    url: http://loki.monitoring.svc:3100
    access: proxy
```

### Compose Path — File Provisioning

```yaml
# /etc/grafana/provisioning/datasources/datasources.yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
  - name: Loki
    type: loki
    url: http://loki:3100
    access: proxy
```

Mount this file into the Grafana container:
```yaml
volumes:
  - ./provisioning/datasources:/etc/grafana/provisioning/datasources:ro
```

---

## Dashboard Provisioning

### k3s — GrafanaDashboard CRD

```yaml
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDashboard
metadata:
  name: homelab-overview
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  json: |
    {
      "title": "Homelab Overview",
      "uid": "homelab-overview",
      "schemaVersion": 38,
      "panels": []
    }
```

Import from grafana.com instead of inline JSON:
```yaml
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  grafanaCom:
    id: 1860       # Node Exporter Full
    revision: 37
```

### Compose — File Provisioning

```yaml
# /etc/grafana/provisioning/dashboards/provider.yaml
apiVersion: 1
providers:
  - name: default
    folder: Homelab
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

Place dashboard JSON files alongside `provider.yaml`. Grafana polls the directory every `updateIntervalSeconds`.

---

## Alerting

### Alert Rule Structure

Grafana-managed alert rules live in evaluation groups. Each rule has:
- **Query/expression**: PromQL or LogQL that returns a value
- **Condition**: threshold that triggers the alert (e.g., `IS ABOVE 0`)
- **`for` duration**: how long the condition must hold before firing
- **Labels**: used for routing (e.g., `severity: critical`, `team: homelab`)
- **Annotations**: `summary` and `description` — support `{{ $labels.job }}` templating

**Example — container down alert (conceptual — see `references/crd-examples.md` for full CRD syntax):**
```yaml
# Grafana UI: Alerting → Alert rules → New alert rule
expr: up{job="sonarr"} == 0
for: 2m
labels:
  severity: critical
annotations:
  summary: "{{ $labels.job }} is down"
  description: "{{ $labels.job }} on {{ $labels.instance }} has been unreachable for 2 minutes"
```

### Contact Points

**Discord webhook** (most common homelab destination):

Get the webhook URL from Discord: **Server Settings → Integrations → Webhooks → New Webhook** (or via channel settings: Edit Channel → Integrations → Webhooks). Copy the URL — it looks like `https://discord.com/api/webhooks/<id>/<token>`.

> Treat the webhook URL as a secret — do not commit it to version control. For the CRD path, store it in a Kubernetes Secret and reference it via `secureSettings` in the contact point config.

```yaml
# Grafana UI: Alerting → Contact points → New contact point
# Type: Discord
# Webhook URL: https://discord.com/api/webhooks/<id>/<token>
# Message (optional custom template):
#   {{ range .Alerts }}
#   **{{ .Labels.alertname }}** — {{ .Annotations.summary }}
#   {{ end }}
```

**Email:**
Configure SMTP via environment variables (do not edit `grafana.ini` directly in containers — changes are lost on restart):
- **Compose**: set `GF_SMTP_ENABLED=true`, `GF_SMTP_HOST`, `GF_SMTP_USER`, `GF_SMTP_PASSWORD`, `GF_SMTP_FROM_ADDRESS` env vars (see `references/crd-examples.md` Compose snippet)
- **k3s**: set the same `GF_SMTP_*` env vars in the Grafana CR's `deployment.spec.template.spec.containers[].env`

Then create an Email contact point in the UI. Store `GF_SMTP_PASSWORD` in a Secret, not in plain config.

**Generic webhook:**
```yaml
# Type: Webhook
# URL: https://your-endpoint/alert
# HTTP Method: POST
# Sends Grafana's default JSON payload with alert state, labels, annotations
```

### Notification Policies

The routing tree determines which contact point receives which alert:

```
Default policy → discord-webhook
  └── severity=critical → discord-webhook + email
  └── team=homelab → discord-webhook
```

Configure at **Alerting → Notification policies**. The default policy catches everything not matched by a child policy.

> **Critical first step:** Before any alert can notify, set the default policy's contact point. Go to **Alerting → Notification policies**, click `...` on the default policy → Edit, and set Contact point to your Discord webhook. Without this, fired alerts go nowhere — the built-in default routes to email which requires SMTP.

---

## Dashboard Design Patterns

### Overview → Drilldown

Top-level dashboard shows aggregate health across all services. Use a `$service` variable and a `stat` panel per service showing `up` status. Link each stat panel to a per-service detail dashboard passing `$service` as a URL parameter.

```json
{
  "type": "stat",
  "title": "$service status",
  "links": [
    {
      "title": "Drilldown",
      "url": "/d/service-detail?var-service=${service}"
    }
  ]
}
```

### Row Organization

Group panels by concern using `row` panels:
1. **System Health** — CPU, memory, disk for the host
2. **Services** — per-service up/down, request rates
3. **Logs** — Loki log panels filtered by `$service`

Collapse rows by default (`collapsed: true`) to keep the dashboard scannable.

### Consistent Variable Usage

Every panel in a dashboard should use the same variables. If `$container` is defined, every Prometheus query should include `{container="$container"}` and every Loki query should include `{container="$container"}`. Panels that don't respect the variable create confusing mismatches when the user switches the dropdown.

---

## References

- [`references/crd-examples.md`](references/crd-examples.md) — Full GrafanaDashboard and GrafanaDatasource YAML, GrafanaAlertRuleGroup CRD, homelab service health dashboard JSON
