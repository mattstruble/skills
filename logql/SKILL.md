---
name: logql
description: "You MUST consult this skill when writing or debugging LogQL queries for Grafana Loki. Also trigger when building Grafana dashboard panels backed by Loki, creating log-based alerting rules, diagnosing empty results or parser errors, extracting metrics from logs with rate/count_over_time/unwrap, or correlating logs across multiple services. NOT for Loki deployment or configuration (see grafana-loki), Prometheus metrics (see promql), or PromQL dashboards."
---

# LogQL Reference

LogQL is Grafana Loki's query language for selecting, filtering, parsing, and aggregating log streams. Two query types: **log queries** (return log lines) and **metric queries** (return numeric values). Syntax is inspired by PromQL.

## Query Structure

```
{stream selector} | pipeline stage | pipeline stage | ...
```

The stream selector is mandatory. Pipeline stages are optional and execute left-to-right.

## Stream Selectors

Narrow as much as possible — this is the primary index lookup.

| Operator | Meaning |
|----------|---------|
| `=` | Exact match |
| `!=` | Not equal |
| `=~` | Regex match (RE2, fully anchored) |
| `!~` | Regex not match |

Always include at least one exact-match label for performance.

```logql
{container="sonarr"}
{compose_service="radarr", host="homelab"}
{container=~"sonarr|radarr|prowlarr"}
```

## Pipeline Stages

### 1. Line Filters — place BEFORE parsers

Distributed grep — cheapest filter. Run these first to reduce data before parsing.

| Operator | Meaning |
|----------|---------|
| `\|=` | Contains string |
| `!=` | Does not contain |
| `\|~` | Regex match (substring, NOT anchored) |
| `!~` | Regex not match |

> **Note:** `|~` and `!~` are **not** fully anchored — they match substrings. Only stream selector `=~`/`!~` are fully anchored (must match the entire label value). `container=~"sonarr"` matches only `sonarr`; use `container=~"sonarr.*"` for prefix.

```logql
{container="sonarr"} |= "error"
{container="plex"} != "healthcheck"
{container="adguard"} |~ "(?i)filtered"       # case-insensitive substring match
{container="sonarr"} |= "error" != "timeout"  # chains are AND
```

Backtick quoting avoids double-escaping: `` |~ `status=\d{3}` ``

### 2. Parsers — extract labels from log content

Choose by speed (fastest first):

| Parser | Syntax | Best For |
|--------|--------|----------|
| `pattern` | `\| pattern \`<ip> - <_> "<method> <path> <_>" <status>\`` | Fixed-format logs (fastest) |
| `logfmt` | `\| logfmt` | key=value logs |
| `json` | `\| json` or `\| json field="path"` | JSON logs |
| `regexp` | `\| regexp \`(?P<name>regex)\`` | Complex formats (slowest) |

Extract only needed fields — `| json status, duration` not `| json`.

> **Parser failure:** Lines that fail to parse produce `__error__` labels and are excluded from downstream label filters. If results are unexpectedly empty after a parser, check `| __error__ != ""` to see failing lines. Common cause: mixed log formats (startup banners mixed with JSON).

```logql
# Sonarr JSON logs — extract only what you need
{container="sonarr"} | json level, message

# Home Assistant logfmt
{container="homeassistant"} | logfmt domain, message

# Nginx access log with pattern
{container="nginx"} | pattern `<ip> - <_> "<method> <path> <_>" <status> <_>`

# Tautulli with regexp fallback
{container="tautulli"} | regexp `(?P<user>\w+) played (?P<title>.+)`
```

### 3. Label Filters — after parsing

Typed comparisons on extracted labels:

```logql
{container="sonarr"} | json | level = "error"
{container="nginx"} | pattern `... <status> <_>` | status >= 500
{container="homeassistant"} | logfmt | duration > 10s
{container="plex"} | json | bytes > 5MB
```

Supports: string (`=`, `!=`, `=~`), numeric (`>`, `>=`, `<`, `<=`), duration (`> 10s`), bytes (`> 5MB`), IP (`= ip("192.168.0.0/24")`).

### 4. Format Expressions

```logql
{container="sonarr"} | json | line_format "{{.level}} {{.message}}"
{container="nginx"} | json | label_format method=request_method
```

## Metric Queries

### Range Aggregations (no unwrap)

```logql
rate({container="sonarr"} |= "error" [5m])                    # entries/second
count_over_time({container="adguard"} |= "filtered" [5m])      # total entries
bytes_rate({container="plex"} [5m])                            # bytes/second
absent_over_time({container="sonarr"} [5m])                    # 1 if no entries (alerting)
```

### Unwrapped Range Aggregations

Extract a numeric label, then aggregate over time:

```logql
# Average Plex transcode speed
avg_over_time(
  {container="plex"} | logfmt | unwrap transcode_speed [5m]
)

# P99 Sonarr API response time
quantile_over_time(0.99,
  {container="sonarr"} | json | unwrap response_time [5m]
)
```

Functions: `sum_over_time`, `avg_over_time`, `min_over_time`, `max_over_time`, `quantile_over_time(φ, ...)`, `rate_counter`, `stddev_over_time`.

Use `unwrap duration_seconds(label)` or `unwrap bytes(label)` for automatic unit conversion.

### Aggregation Operators

Same as PromQL: `sum`, `avg`, `min`, `max`, `count`, `topk`, `bottomk`. Group with `by()` or `without()`.

```logql
# AdGuard blocked DNS queries per minute
# AdGuard Home logs blocked queries with "filtered" in the line (text) or
# Reason field containing "Filtered*" (JSON). Check your log format first.
sum by (client) (
  rate({container="adguard"} |= "filtered" [1m])
)

# Top 5 containers by error rate
topk(5,
  sum by (container) (rate({host="homelab"} |= "error" [5m]))
)
```

## Cross-Service Correlation

Off-the-shelf containers (Sonarr, Radarr, Prowlarr, qBittorrent) can't inject trace IDs into their logs — there's no OpenTelemetry instrumentation. The homelab substitute for distributed tracing is correlating by shared domain identifiers that naturally appear across services: TMDB IDs, TVDB IDs, download hashes, NZB IDs. This is the homelab equivalent of a distributed trace query.

```logql
# All activity around a specific TMDB ID across *arr services
{container=~"sonarr|radarr|prowlarr"} |= "tmdbId=12345"

# Correlate by download hash across Sonarr and download client
{container=~"sonarr|qbittorrent"} |= "abc123hash"

# Find all Radarr + Prowlarr activity for a movie title
{container=~"radarr|prowlarr"} |~ "(?i)inception"

# Track a specific download from indexer search to completion
{container=~"prowlarr|sonarr|qbittorrent"} |= "NZB-ID-or-hash-here"
```

## Log-Based Alerting

```yaml
groups:
  - name: homelab_alerts
    rules:
      - alert: SonarrErrors
        expr: |
          sum(rate({container="sonarr"} |= "error" [5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Sonarr error rate elevated"

      - alert: AdGuardDown
        expr: absent_over_time({container="adguard"}[5m])
        for: 2m
        labels:
          severity: critical
```

## Optimization

| Technique | Impact |
|-----------|--------|
| Narrow stream selector with exact-match labels | High |
| Line filter before parser | High |
| Recording rules for dashboard panels | High |
| Extract only needed fields (`\| json status`) | Medium |
| Shorter time ranges | Medium |
| `pattern` / `logfmt` faster than `json`; `regexp` slowest | Medium |
| Avoid `by(high-cardinality-label)` (IPs, user IDs, request IDs) — use `topk` or filter to specific values | High |

## Troubleshooting

| Problem | Cause & Fix |
|---------|-------------|
| Empty results | Stream selector matches nothing — test `{container="x"}` alone first; check exact label name/value in Loki |
| `__error__` labels appear | Parser failed on some lines. Debug: `\| __error__ != ""` to see failing lines. Drop them: `\| __error__ = ""`. For JSON: add `\|= "{"` before `\| json`. For pattern: verify pattern matches actual log format. |
| Query timeout | Causes: `regexp` parser on high-volume stream, `\|~` regex filter without a preceding `\|=` string filter, long time range with unwrap aggregations. Fixes: add exact-match labels, place `\|=` before `\|~`, reduce time range. Recording rules require Loki ruler (see grafana-loki skill). |

## LogQL vs PromQL

| Feature | PromQL | LogQL |
|---------|--------|-------|
| Data source | Metrics (time series) | Logs (text streams) |
| Selectors | `metric{label="value"}` | `{label="value"}` (no metric name) |
| Parsing | N/A (structured) | json, logfmt, pattern, regexp |
| Line filtering | N/A | `\|=`, `!=`, `\|~`, `!~` |
| Unwrap | N/A | Extract numeric values from logs |
| Aggregations | Same operators | Same operators |

Use PromQL for metrics from Prometheus exporters. Use LogQL when the data lives in log lines.
