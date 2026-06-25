# Docker Compose Deployment Reference

Full monitoring stack on Docker Compose. Uses file-based Grafana provisioning (no operator CRDs). Alloy collects logs from Docker containers and ships to Loki.

## Directory layout

```
monitoring/
├── docker-compose.yml
├── loki-config.yaml
├── prometheus.yml
├── alertmanager.yml
├── alloy-config.alloy
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── datasources.yaml
        └── dashboards/
            └── dashboards.yaml
```

## .env (secrets — add to .gitignore)

```bash
# Generate: openssl rand -base64 24
GRAFANA_ADMIN_PASSWORD=your-generated-password-here
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
SMTP_PASSWORD=your-app-password
```

Add to `.gitignore`:
```
.env
```

## docker-compose.yml

```yaml
networks:
  monitoring:
    driver: bridge

volumes:
  loki_data:
  prometheus_data:
  grafana_data:
  alertmanager_data:

# ⚠️ DATA LOSS WARNING: `docker compose down -v` deletes ALL monitoring data
# (Prometheus metrics, Loki logs, Grafana dashboards).
# Use `docker compose down` (no -v) to stop without data loss.

services:
  loki:
    image: grafana/loki:3.6.0
    container_name: loki
    ports:
      - "127.0.0.1:3100:3100"  # internal only — no network exposure needed
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml:ro
      - loki_data:/var/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:3100/ready || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  prometheus:
    image: prom/prometheus:v3.0.0
    container_name: prometheus
    ports:
      - "127.0.0.1:9090:9090"  # internal only — access via Grafana
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro  # needed for docker_sd_configs
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--storage.tsdb.retention.size=10GB'
      - '--web.enable-lifecycle'
    networks:
      - monitoring
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:9090/-/ready || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  grafana:
    image: grafana/grafana:11.0.0
    container_name: grafana
    ports:
      - "3000:3000"  # user-facing UI — keep accessible on LAN
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    networks:
      - monitoring
    restart: unless-stopped
    depends_on:
      prometheus:
        condition: service_healthy
      loki:
        condition: service_healthy

  alertmanager:
    image: prom/alertmanager:v0.27.0
    container_name: alertmanager
    ports:
      - "127.0.0.1:9093:9093"  # internal only
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    networks:
      - monitoring
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://localhost:9093/-/healthy || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    depends_on:
      prometheus:
        condition: service_healthy

  alloy:
    image: grafana/alloy:v1.8.0
    container_name: alloy
    volumes:
      - ./alloy-config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: run /etc/alloy/config.alloy
    networks:
      - monitoring
    restart: unless-stopped
    depends_on:
      loki:
        condition: service_healthy

  # Optional: node-exporter for host metrics
  node-exporter:
    image: prom/node-exporter:v1.8.0
    container_name: node-exporter
    pid: host
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - monitoring
    restart: unless-stopped
```

## loki-config.yaml

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /var/loki
  storage:
    filesystem:
      chunks_directory: /var/loki/chunks
      rules_directory: /var/loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-04-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: 720h   # 30 days
  allow_structured_metadata: true

compactor:
  retention_enabled: true
  compaction_interval: 10m
  retention_delete_delay: 2h
  working_directory: /var/loki/compactor
```

## prometheus.yml

```yaml
global:
  scrape_interval: 30s
  evaluation_interval: 30s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Host metrics
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  # Loki self-monitoring
  - job_name: 'loki'
    static_configs:
      - targets: ['loki:3100']
    metrics_path: /metrics

  # Docker service discovery — scrapes containers with prometheus.scrape=true label
  - job_name: 'docker-services'
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        filters:
          - name: label
            values: ["prometheus.scrape=true"]
    relabel_configs:
      - source_labels: [__meta_docker_container_label_prometheus_job]
        target_label: job
      # prometheus.address must be "host:port" (e.g., "sonarr-exporter:9707")
      - source_labels: [__meta_docker_container_label_prometheus_address]
        target_label: __address__
        replacement: '${1}'
      - source_labels: [__meta_docker_container_name]
        target_label: container
        regex: '/?(.*)'

  # Static targets for apps without Docker labels
  # Add your *arr apps here if they expose /metrics
  - job_name: 'sonarr'
    static_configs:
      - targets: ['sonarr:8989']
    metrics_path: /metrics
    # Sonarr requires an API key header if using exportarr
```

> For *arr apps (Sonarr, Radarr, etc.), use [exportarr](https://github.com/onedr0p/exportarr) as a sidecar to expose Prometheus metrics. Add `prometheus.scrape=true` and `prometheus.address=<container-name>:9707` labels to the exportarr container.

## alertmanager.yml

> **Never commit secrets.** Use environment variables for webhook URLs and passwords.
> Alertmanager supports `$ENV_VAR` substitution natively in its config file.

```yaml
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
      - webhook_url: '$DISCORD_WEBHOOK_URL'
        title: '{{ .GroupLabels.alertname }}'
        message: '{{ range .Alerts }}{{ .Annotations.summary }}{{ "\n" }}{{ end }}'

  - name: 'email'
    email_configs:
      - to: 'you@example.com'
        from: 'alertmanager@example.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'you@example.com'
        auth_password: '$SMTP_PASSWORD'
        require_tls: true
```

## alloy-config.alloy

Collects logs from all Docker containers on the host.

```alloy
// Discover Docker containers
discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

// Relabel: extract container name and compose service as labels
discovery.relabel "containers" {
  targets = discovery.docker.containers.targets

  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/?(.*)"
    target_label  = "container"
  }

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "service"
  }

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_project"]
    target_label  = "compose_project"
  }
}

// Collect logs from discovered containers
loki.source.docker "containers" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.containers.output
  forward_to = [loki.write.default.receiver]
}

// Write to Loki
loki.write "default" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

## Grafana provisioning

### grafana/provisioning/datasources/datasources.yaml

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    jsonData:
      timeInterval: "30s"

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
```

### grafana/provisioning/dashboards/dashboards.yaml

```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/provisioning/dashboards
```

Place dashboard JSON files in `grafana/provisioning/dashboards/`. Export from Grafana UI or download from [grafana.com/dashboards](https://grafana.com/grafana/dashboards/):
- Node Exporter Full: ID 1860
- Loki Dashboard: ID 14055
- Docker Monitoring: ID 193

## Start the stack

```bash
cd monitoring/
docker compose up -d

# Verify all containers are healthy
docker compose ps

# Check Loki is ready
curl http://localhost:3100/ready

# Open Grafana
open http://localhost:3000   # admin / changeme
```

## Add prometheus.scrape labels to your app containers

To enable Docker service discovery scraping, add labels to your app containers:

```yaml
# In your app's docker-compose.yml
services:
  sonarr-exporter:
    image: ghcr.io/onedr0p/exportarr:latest
    command: sonarr
    environment:
      PORT: "9707"
      URL: "http://sonarr:8989"
      APIKEY: "your-sonarr-api-key"
    labels:
      prometheus.scrape: "true"
      prometheus.address: "sonarr-exporter:9707"  # must be "host:port"
      prometheus.job: "sonarr"
    networks:
      - monitoring
      - your-media-network
```
