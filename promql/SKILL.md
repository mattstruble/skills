---
name: promql
summary: PromQL query syntax for Prometheus: rates, histograms, alerting, and capacity planning
type: reference
description: You MUST consult this skill when writing or debugging PromQL queries for Prometheus — dashboards, alerting rules, recording rules, or ad-hoc metric exploration. Also trigger on rate vs irate decisions, histogram quantiles, predict_linear for capacity planning, absent() for uptime alerts, or vector matching errors. NOT for Prometheus server deployment (see homelab-monitoring), Loki log queries (see logql), or Grafana datasource configuration.
---

# PromQL

PromQL is Prometheus's functional query language. This skill covers homelab usage with node-exporter, cAdvisor/Docker metrics, and app-specific exporters (Plex, Sonarr, Radarr, Prowlarr, Home Assistant, AdGuard Home).

## Data Types

| Type | Description | When you have it |
|------|-------------|-----------------|
| **Instant vector** | One sample per series at current time | Bare metric name or `{}` selector |
| **Range vector** | Multiple samples over a window | Metric with `[5m]` appended |
| **Scalar** | Single number | `scalar()`, arithmetic on instant vectors |
| **String** | Unused in practice | — |

Range vectors can only be passed to functions (`rate`, `avg_over_time`, etc.) — they can't be graphed directly.

## Selectors

```promql
node_cpu_seconds_total{mode="idle", instance="homelab:9100"}   # exact match
container_memory_usage_bytes{name=~"sonarr|radarr"}            # regex match
up{job="plex"}[5m]                                             # range vector
up offset 1h                                                   # 1h ago
```

Label matchers:
- `=` exact, `!=` not equal
- `=~` regex (RE2, **fully anchored** — `sonarr` matches only `sonarr`, use `.*sonarr.*` for substring)
- `!~` negated regex

## Operators

**Arithmetic:** `+`, `-`, `*`, `/`, `%`, `^`

**Comparison:** `==`, `!=`, `>`, `<`, `>=`, `<=`
- Add `bool` modifier for 0/1 output instead of filtering: `up == bool 1`

**Logical:** `and`, `or`, `unless`

## Vector Matching

When combining two metrics, Prometheus matches on all shared labels by default. Mismatches cause empty results or errors.

```promql
a / on(job, instance) b          # match only on these labels
a / ignoring(status_code) b      # match on all labels except these
a / on(job) group_left() b       # many-to-one: left side has more series
a / on(job) group_right() b      # one-to-many: right side has more series
```

Diagnose mismatches: `count by (instance) (metric_a)` vs `count by (instance) (metric_b)` — labels must align.

## Aggregation

```promql
sum by (instance) (rate(node_cpu_seconds_total[5m]))     # keep instance, drop rest
avg without (cpu) (rate(node_cpu_seconds_total[5m]))     # drop cpu, keep rest
topk(5, rate(container_cpu_usage_seconds_total[5m]))     # top 5 containers by CPU
```

Operators: `sum`, `avg`, `min`, `max`, `count`, `topk`, `bottomk`, `stddev`, `stdvar`, `quantile`, `group`.

## Rate Functions — Decision Table

| Function | Input | Use When |
|----------|-------|----------|
| `rate(v[d])` | Counter range | **Default for counters** (`_total`) — handles resets, good for alerting |
| `irate(v[d])` | Counter range | High-resolution spikes — **not for alerting** (too volatile) |
| `increase(v[d])` | Counter range | Total increase over window (e.g., requests in last hour) |
| `delta(v[d])` | Gauge range | Change in a gauge over window |
| `deriv(v[d])` | Gauge range | Rate of change for gauges (linear regression) |

**Range window rule:** use >= 4× scrape interval. With 15s scrape: use `[60s]` minimum, `[5m]` is typical.

## Aggregation Over Time

For smoothing or summarizing a metric over a window without `rate`:

```promql
avg_over_time(node_load1[30m])          # 30-min average of load
max_over_time(container_memory_usage_bytes{name="plex"}[1h])
```

Functions: `avg_over_time`, `min_over_time`, `max_over_time`, `sum_over_time`, `count_over_time`, `quantile_over_time`, `last_over_time`.

## Histograms

Classic histograms (most exporters): preserve the `le` label when aggregating.

```promql
# 95th percentile request latency
histogram_quantile(0.95,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

If you aggregate across jobs/instances and want per-job quantiles:
```promql
histogram_quantile(0.95,
  sum by (le, job) (rate(http_request_duration_seconds_bucket[5m]))
)
```

## Subqueries

Run an instant query over a range — useful for `max_over_time` of a derived metric:

```promql
max_over_time(rate(container_cpu_usage_seconds_total[5m])[1h:1m])
# reads as: "max of the 5m rate, sampled every 1m, over the past 1h"
```

## Label Functions

```promql
label_replace(metric, "dst_label", "$1", "src_label", "(.*)")
label_join(metric, "dst_label", "/", "src1", "src2")
```

## Prediction (Homelab Killer Feature)

`predict_linear` fits a linear regression and extrapolates forward:

```promql
predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 24*3600) < 0
```

- First arg: range vector — the **window** determines regression accuracy. Use 6h–24h for disk (slow trends). Too short = noisy; too long = misses recent changes.
- Second arg: seconds to project ahead (`24*3600` = 24 hours)
- Result `< 0` means "disk will be full within 24h"

## Existence / Uptime Checks

```promql
absent(up{job="sonarr"})                   # fires when sonarr disappears from scrape
absent_over_time(up{job="plex"}[5m])       # fires when plex has been down 5+ minutes
```

`absent` returns a 1-element vector when the selector matches nothing. Use in alerting rules to detect services that stopped reporting.

**Important caveats:**
- `absent(up{job="sonarr"})` only fires when the *entire job* disappears. With multiple instances, it won't fire if one instance is down but others are up. For per-instance alerting, use `up{job="sonarr"} == 0` with `for: 5m` instead.
- `absent_over_time` detects *missing scrape data* (exporter unreachable), not `up == 0` (service down but exporter running). For "service down", use `up{job="plex"} == 0`.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `rate(node_memory_MemAvailable_bytes[5m])` | Memory is a gauge — use it directly: `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes` |
| `sum(http_requests_total)` without rate | Wrap in `rate()` first: `sum(rate(http_requests_total[5m]))` |
| `sum(rate(http_request_duration_seconds_bucket[5m]))` | Missing `by (le)` — histogram quantile needs `le` label |
| `rate(metric[15s])` with 15s scrape interval | Range must be >= 4× scrape: use `[60s]` minimum |
| `irate()` in alerting rules | Use `rate()` — irate is too volatile for reliable alerts |
| Regex `{name="sonarr"}` matching nothing | RE2 is fully anchored; use `{name=~".*sonarr.*"}` for substring or exact `{name="sonarr"}` |

## Recording Rules Naming

Convention: `level:metric:operations`

```yaml
groups:
  - name: homelab.rules
    rules:
      - record: instance:node_cpu:rate5m
        expr: 1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
```

## Homelab Examples

**CPU usage % per node:**
```promql
1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))
```

**Memory pressure:**
```promql
1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)
```

**Disk filling prediction (alert when full within 24h):**
```promql
predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 24*3600) < 0
```

**Container down alert** (single instance — exporter unreachable):
```promql
absent(up{job="sonarr", instance="homelab:8989"})
```

**Container down alert** (service down, exporter still running):
```promql
up{job="sonarr"} == 0
```

**Error rate %** (returns no result — not 0% — when there is no traffic):
```promql
sum by (job) (rate(http_requests_total{status=~"5.."}[5m]))
/ sum by (job) (rate(http_requests_total[5m])) * 100
```

**Top 5 containers by memory:**
```promql
topk(5, container_memory_usage_bytes{name!=""})
```

**Alerting rule example:**
```yaml
groups:
  - name: homelab.alerts
    rules:
      - alert: DiskFillingSoon
        expr: predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 24*3600) < 0
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Disk on {{ $labels.instance }} fills within 24h"
```

Note: keep `for:` much shorter than the prediction horizon. `for: 1h` with a 24h prediction means the alert only fires after the condition has been true for 1 hour — by then you may have less than 23h of lead time.
