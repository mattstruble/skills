# Grafana CRD Examples

Full YAML examples for Grafana Operator CRDs and homelab dashboard JSON.

## GrafanaDatasource CRDs

### Prometheus

```yaml
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
    uid: prometheus   # set explicit uid so alert rules can reference it deterministically
    url: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
    access: proxy
    isDefault: true
    jsonData:
      timeInterval: "30s"
      httpMethod: POST
```

### Loki

```yaml
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
    jsonData:
      maxLines: 1000
```

---

## GrafanaDashboard CRDs

### Import from grafana.com

```yaml
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDashboard
metadata:
  name: node-exporter-full
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  grafanaCom:
    id: 1860        # Node Exporter Full
    revision: 37
```

### Inline JSON — Homelab Service Health

```yaml
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDashboard
metadata:
  name: homelab-service-health
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  json: |
    {
      "title": "Homelab Service Health",
      "uid": "homelab-health",
      "schemaVersion": 38,
      "time": { "from": "now-1h", "to": "now" },
      "refresh": "30s",
      "templating": {
        "list": [
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
        ]
      },
      "panels": [
        {
          "type": "row",
          "title": "Service Status",
          "gridPos": { "x": 0, "y": 0, "w": 24, "h": 1 },
          "collapsed": false
        },
        {
          "type": "stat",
          "title": "Sonarr",
          "gridPos": { "x": 0, "y": 1, "w": 4, "h": 4 },
          "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
          "targets": [
            {
              "expr": "up{job=\"sonarr\"}",
              "legendFormat": "Sonarr"
            }
          ],
          "options": {
            "colorMode": "background",
            "graphMode": "none",
            "reduceOptions": { "calcs": ["lastNotNull"] }
          },
          "fieldConfig": {
            "defaults": {
              "mappings": [
                { "type": "value", "options": { "0": { "text": "DOWN", "color": "red" }, "1": { "text": "UP", "color": "green" } } }
              ]
            }
          }
        },
        {
          "type": "stat",
          "title": "Radarr",
          "gridPos": { "x": 4, "y": 1, "w": 4, "h": 4 },
          "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
          "targets": [
            { "expr": "up{job=\"radarr\"}", "legendFormat": "Radarr" }
          ],
          "options": {
            "colorMode": "background",
            "graphMode": "none",
            "reduceOptions": { "calcs": ["lastNotNull"] }
          },
          "fieldConfig": {
            "defaults": {
              "mappings": [
                { "type": "value", "options": { "0": { "text": "DOWN", "color": "red" }, "1": { "text": "UP", "color": "green" } } }
              ]
            }
          }
        },
        {
          "type": "stat",
          "title": "Plex",
          "gridPos": { "x": 8, "y": 1, "w": 4, "h": 4 },
          "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
          "targets": [
            { "expr": "up{job=\"plex\"}", "legendFormat": "Plex" }
          ],
          "options": {
            "colorMode": "background",
            "graphMode": "none",
            "reduceOptions": { "calcs": ["lastNotNull"] }
          },
          "fieldConfig": {
            "defaults": {
              "mappings": [
                { "type": "value", "options": { "0": { "text": "DOWN", "color": "red" }, "1": { "text": "UP", "color": "green" } } }
              ]
            }
          }
        },
        {
          "type": "stat",
          "title": "Home Assistant",
          "gridPos": { "x": 12, "y": 1, "w": 4, "h": 4 },
          "datasource": { "type": "prometheus", "uid": "${DS_PROMETHEUS}" },
          "targets": [
            { "expr": "up{job=\"homeassistant\"}", "legendFormat": "Home Assistant" }
          ],
          "options": {
            "colorMode": "background",
            "graphMode": "none",
            "reduceOptions": { "calcs": ["lastNotNull"] }
          },
          "fieldConfig": {
            "defaults": {
              "mappings": [
                { "type": "value", "options": { "0": { "text": "DOWN", "color": "red" }, "1": { "text": "UP", "color": "green" } } }
              ]
            }
          }
        },
        {
          "type": "row",
          "title": "Logs",
          "gridPos": { "x": 0, "y": 5, "w": 24, "h": 1 },
          "collapsed": true
        },
        {
          "type": "logs",
          "title": "Service Logs",
          "gridPos": { "x": 0, "y": 6, "w": 24, "h": 8 },
          "datasource": { "type": "loki", "uid": "${DS_LOKI}" },
          "targets": [
            {
              "expr": "{job=\"$service\"} |= \"\"",
              "legendFormat": ""
            }
          ],
          "options": {
            "showTime": true,
            "sortOrder": "Descending",
            "wrapLogMessage": false
          }
        }
      ]
    }
```

---

## GrafanaAlertRuleGroup CRD

The `GrafanaAlertRuleGroup` requires a `GrafanaFolder` to exist first. Create the folder CRD before applying the alert rule group.

```yaml
# Step 1: Create the folder
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaFolder
metadata:
  name: homelab-alerts-folder
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  title: Homelab Alerts
```

```yaml
# Step 2: Create the alert rule group
# Note: datasourceUid must match the uid field in your GrafanaDatasource spec.
# Add `uid: prometheus` to your GrafanaDatasource to make it deterministic (see above).
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaAlertRuleGroup
metadata:
  name: homelab-alerts
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  folderRef: homelab-alerts-folder   # must match GrafanaFolder metadata.name above
  interval: 1m
  rules:
    - uid: sonarr-down
      title: Sonarr Down
      condition: C   # alert fires when expression C evaluates to true
      for: 2m
      labels:
        severity: critical
        service: sonarr
      annotations:
        summary: "Sonarr is unreachable"
        description: "Sonarr has been down for more than 2 minutes"
      data:
        # refId A: raw Prometheus query
        - refId: A
          datasourceUid: prometheus   # must match GrafanaDatasource uid field
          model:
            refId: A
            expr: up{job="sonarr"}
            intervalMs: 1000
            maxDataPoints: 43200
        # refId C: threshold expression — fires when A < 1 (i.e., up == 0)
        - refId: C
          datasourceUid: __expr__
          model:
            refId: C
            type: threshold
            expression: "A"   # references refId A above
            conditions:
              - evaluator:
                  params: [1]
                  type: lt
                operator: { type: and }
                reducer: { type: last }
                query: { params: ["C"] }

    - uid: radarr-down
      title: Radarr Down
      condition: C
      for: 2m
      labels:
        severity: critical
        service: radarr
      annotations:
        summary: "Radarr is unreachable"
        description: "Radarr has been down for more than 2 minutes"
      data:
        - refId: A
          datasourceUid: prometheus
          model:
            refId: A
            expr: up{job="radarr"}
            intervalMs: 1000
            maxDataPoints: 43200
        - refId: C
          datasourceUid: __expr__
          model:
            refId: C
            type: threshold
            expression: "A"
            conditions:
              - evaluator: { params: [1], type: lt }
                operator: { type: and }
                reducer: { type: last }
                query: { params: ["C"] }
```

---

## Compose File Provisioning

### docker-compose.yml snippet

```yaml
services:
  grafana:
    # Pin to a specific version — check https://github.com/grafana/grafana/releases
    image: grafana/grafana:11.6.0
    volumes:
      - ./provisioning/datasources:/etc/grafana/provisioning/datasources:ro
      - ./provisioning/dashboards:/etc/grafana/provisioning/dashboards:ro
      - grafana-data:/var/lib/grafana
    environment:
      # Store GF_ADMIN_PASSWORD in a .env file — never commit real credentials
      - GF_SECURITY_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD:?GF_ADMIN_PASSWORD must be set}
      - GF_SMTP_ENABLED=true
      - GF_SMTP_HOST=smtp.gmail.com:587
      - GF_SMTP_USER=you@gmail.com
      - GF_SMTP_PASSWORD=${GF_SMTP_PASSWORD:?GF_SMTP_PASSWORD must be set}
      - GF_SMTP_FROM_ADDRESS=you@gmail.com
```

### provisioning/dashboards/provider.yaml

```yaml
apiVersion: 1
providers:
  - name: homelab
    folder: Homelab
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: false
    options:
      path: /etc/grafana/provisioning/dashboards
```

### provisioning/datasources/datasources.yaml

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
    jsonData:
      timeInterval: "30s"
  - name: Loki
    type: loki
    url: http://loki:3100
    access: proxy
    jsonData:
      maxLines: 1000
```
