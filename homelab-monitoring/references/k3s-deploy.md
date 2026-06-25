# k3s Deployment Reference

Helm-based deployment of the full monitoring stack on k3s. Uses kube-prometheus-stack for Prometheus + Grafana + Alertmanager, the `grafana/loki` chart for Loki, and Alloy as a DaemonSet for log collection.

## Prerequisites

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
```

## 1. kube-prometheus-stack (Prometheus + Grafana + Alertmanager)

```yaml
# kube-prometheus-stack-values.yaml
prometheus:
  prometheusSpec:
    # ⚠️ CRITICAL: without these, Prometheus silently ignores your ServiceMonitors
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
    ruleSelectorNilUsesHelmValues: false

    retention: 30d
    retentionSize: 10GB
    storageSpec:
      volumeClaimTemplate:
        spec:
          storageClassName: local-path   # k3s built-in
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 20Gi

grafana:
  persistence:
    enabled: true
    storageClassName: local-path
    size: 5Gi
  sidecar:
    dashboards:
      enabled: true
      searchNamespace: ALL
    datasources:
      enabled: true
  # Admin password from pre-created Secret (never store in values.yaml):
  #   kubectl create secret generic grafana-admin \
  #     --from-literal=admin-password="$(openssl rand -base64 24)" -n monitoring
  admin:
    existingSecret: grafana-admin
    userKey: admin-user
    passwordKey: admin-password

alertmanager:
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          storageClassName: local-path
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 2Gi
  config:
    global:
      resolve_timeout: 5m
    route:
      group_by: ['alertname']
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 4h
      receiver: 'discord'
    receivers:
      - name: 'discord'
        discord_configs:
          - webhook_url_file: '/etc/alertmanager/secrets/discord-webhook-url'
          # Create the Secret:
          #   kubectl create secret generic alertmanager-discord \
          #     --from-literal=discord-webhook-url="https://discord.com/api/webhooks/..." -n monitoring
          # Mount via alertmanagerSpec.secrets: ['alertmanager-discord']

# Disable GPU-specific components not needed for homelab
kubeEtcd:
  enabled: false   # k3s uses SQLite by default, not etcd
```

```bash
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  -f kube-prometheus-stack-values.yaml
```

## 2. Loki (monolithic / SingleBinary mode)

```yaml
# loki-values.yaml
deploymentMode: SingleBinary

singleBinary:
  replicas: 1
  persistence:
    enabled: true
    storageClass: local-path
    size: 20Gi

loki:
  auth_enabled: false  # single-user homelab; set true + auth proxy if exposing externally
  commonConfig:
    replication_factor: 1
  storage:
    type: filesystem
  schemaConfig:
    configs:
      - from: "2024-04-01"
        store: tsdb
        object_store: filesystem
        schema: v13
        index:
          prefix: loki_index_
          period: 24h
  limits_config:
    retention_period: 720h   # 30 days
    allow_structured_metadata: true
  compactor:
    retention_enabled: true
    compaction_interval: 10m
    retention_delete_delay: 2h

# Disable components not needed for single-binary
read:
  replicas: 0
write:
  replicas: 0
backend:
  replicas: 0
```

```bash
helm install loki grafana/loki \
  -n monitoring \
  -f loki-values.yaml
```

## 3. Alloy (log collection DaemonSet)

Alloy collects pod logs from all nodes and ships them to Loki.

```yaml
# alloy-values.yaml
alloy:
  configMap:
    content: |
      // Discover all pods on this node
      discovery.kubernetes "pods" {
        role = "pod"
      }

      // Relabel: extract useful labels from pod metadata
      discovery.relabel "pods" {
        targets = discovery.kubernetes.pods.targets
        rule {
          source_labels = ["__meta_kubernetes_namespace"]
          target_label  = "namespace"
        }
        rule {
          source_labels = ["__meta_kubernetes_pod_name"]
          target_label  = "pod"
        }
        rule {
          source_labels = ["__meta_kubernetes_pod_container_name"]
          target_label  = "container"
        }
        rule {
          source_labels = ["__meta_kubernetes_pod_label_app"]
          target_label  = "app"
        }
        // Only collect logs from this node
        rule {
          source_labels = ["__meta_kubernetes_pod_node_name"]
          target_label  = "__host__"
        }
      }

      // Collect pod logs
      loki.source.kubernetes "pods" {
        targets    = discovery.relabel.pods.output
        forward_to = [loki.write.default.receiver]
      }

      // Write to Loki
      loki.write "default" {
        endpoint {
          url = "http://loki.monitoring.svc:3100/loki/api/v1/push"
        }
      }

controller:
  type: daemonset

rbac:
  create: true
```

```bash
helm install alloy grafana/alloy \
  -n monitoring \
  -f alloy-values.yaml
```

## 4. ServiceMonitor for homelab apps

Apps that expose Prometheus metrics (e.g., Tautulli, Sonarr with exporters) need a ServiceMonitor:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: sonarr
  namespace: monitoring
spec:
  namespaceSelector:
    matchNames: ["media"]
  selector:
    matchLabels:
      app: sonarr
  endpoints:
    - port: metrics
      interval: 60s
      path: /metrics
```

> Remember: `serviceMonitorSelectorNilUsesHelmValues: false` must be set or this ServiceMonitor will be ignored.

## 5. Grafana Operator (optional, IaC-first approach)

If you prefer managing Grafana resources as Kubernetes CRDs instead of Helm values:

```bash
helm install grafana-operator grafana/grafana-operator \
  -n monitoring
```

### GrafanaDatasource CRDs

```yaml
# prometheus-datasource.yaml
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
    access: proxy
    url: http://kube-prometheus-stack-prometheus.monitoring.svc:9090
    isDefault: true
    jsonData:
      timeInterval: "30s"
---
# loki-datasource.yaml
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
    access: proxy
    url: http://loki.monitoring.svc:3100
```

### GrafanaDashboard CRD (import from grafana.com)

```yaml
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDashboard
metadata:
  name: node-exporter
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  grafanaCom:
    id: 1860        # Node Exporter Full dashboard
    revision: 37
```

### GrafanaDashboard CRD (inline JSON)

```yaml
apiVersion: grafana.integreatly.org/v1beta1
kind: GrafanaDashboard
metadata:
  name: my-dashboard
  namespace: monitoring
spec:
  instanceSelector:
    matchLabels:
      dashboards: grafana
  json: |
    {
      "title": "My Dashboard",
      "panels": [],
      "schemaVersion": 38
    }
```

## Verify the stack

```bash
# Check all pods are running
kubectl get pods -n monitoring

# Verify Prometheus targets (should not be 0)
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
# Open http://localhost:9090/targets

# Verify Loki is ready
kubectl port-forward -n monitoring svc/loki 3100:3100
curl http://localhost:3100/ready

# Open Grafana
kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80
# Open http://localhost:3000 (admin / changeme)
```
