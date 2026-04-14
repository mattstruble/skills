---
name: k8s-storage
description: Use when working with Kubernetes ConfigMaps, Secrets, PersistentVolumes, PersistentVolumeClaims, or StorageClasses. Also trigger on volume mounts vs env vars decisions, handling ConfigMap/Secret updates (rollout restart, hash-based naming), access mode selection (RWO/ROX/RWX), choosing between Deployment+PVC and StatefulSet+volumeClaimTemplates, dynamic provisioning, or planning backup strategies for cluster state and persistent data. NOT for cluster setup (see k3s), Deployments/Services (see k8s-workloads), networking/ingress (see k8s-networking), Helm (see helm), or rollout strategies (see k8s-operations).
---

# k8s-storage

Patterns and decisions for ConfigMaps, Secrets, and persistent storage in self-hosted Kubernetes clusters.

---

## ConfigMap vs Secret

| Situation | Use |
|---|---|
| Non-sensitive config (ports, feature flags, proxy settings) | ConfigMap |
| Anything sensitive (passwords, API keys, tokens, TLS certs, DB connection strings) | Secret |
| Binary data (font files, BSON files, compiled templates) | ConfigMap `binaryData` or Secret (auto-base64) |
| Shared config file content (nginx.conf, app.yaml) | ConfigMap `data` with multiline `\|` block |

**Rule:** When in doubt, use a Secret. Secrets can be encrypted at rest; ConfigMaps cannot. The only cost is base64 encoding, which is trivial.

---

## ConfigMap YAML

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: chlabs-io-config
data:
  PORT: "12345"                  # numbers must be quoted — data field is strings only
  MULTILINE_DATA: |
    Hello World!
    This is a multiline data.
binaryData:
  HELLO_WORLD: SGVsbG8sIFdvcmxkIQ==   # base64-encoded binary; decoded automatically when volume-mounted
```

**Limits:** Total size < 1 MB (keys + values). Name ≤ 253 chars, lowercase alphanumeric + `-` + `.`.

---

## Secret YAML (Opaque)

```bash
# Create from .env file (most common)
kubectl create secret generic app.secret.env \
  --from-env-file=.env \
  --namespace=production
secret/app.secret.env created

# Inspect without revealing values
kubectl describe secret app.secret.env -n production

# Decode a specific key
kubectl get secret app.secret.env -n production -o json \
  | jq '.data | map_values(@base64d)'
```

Secret types: `Opaque` (generic), `kubernetes.io/tls` (TLS certs), `kubernetes.io/dockerconfigjson` (registry auth), `kubernetes.io/ssh-auth`, `kubernetes.io/basic-auth`.

> **Warning:** Secrets are stored unencrypted in etcd by default. Enable [encryption at rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/) for production clusters. Any user who can create a Pod in a namespace can read all Secrets in that namespace.

---

## Env Vars vs Volume Mounts

| Approach | Use when | Caveat |
|---|---|---|
| `envFrom` (ConfigMap) | Simple key=value config, app reads env vars | Values not updated at runtime; binaryData arrives base64-encoded |
| `envFrom` (Secret) | Convenient but less secure | Env vars visible in crash dumps, `/proc`, and `docker inspect` |
| Volume mount (Secret) | Files, multi-line data, TLS certs, SSH keys | More secure; each key becomes a file at `mountPath/KEY` |
| Volume mount (ConfigMap) | Config files (nginx.conf, app.yaml) | binaryData decoded automatically when mounted as file |

**Recommendation:** Mount Secrets as volumes (`readOnly: true`). Use `envFrom` for ConfigMaps only when the app is designed to read env vars.

### Pod consuming both (canonical pattern)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: cm-secret-tester
spec:
  volumes:
    - name: secrets
      secret:
        secretName: app.secret.env
  containers:
    - name: app
      image: registry.k8s.io/busybox
      volumeMounts:
        - name: secrets
          readOnly: true
          mountPath: "/etc/secrets"   # each Secret key → /etc/secrets/<KEY>
      envFrom:
        - configMapRef:
            name: app.configmap       # all ConfigMap keys → env vars
      command: ["/bin/sh"]
      args: ["-c", "ls /etc/secrets && printenv"]
```

**Selective keys:** To mount only specific keys (or rename them), use `items:` under the `secret:` or `configMap:` volume definition.

---

## Handling ConfigMap and Secret Updates

When a ConfigMap or Secret changes, running Pods do **not** automatically pick up the new values:
- `envFrom` — never updates; env vars are set at container start
- Volume mounts — files *do* update eventually (kubelet sync period, ~1 min), but most apps don't re-read files at runtime

**Update strategies (pick one):**

| Strategy | When to use |
|---|---|
| `kubectl rollout restart deployment/<name>` | Small clusters, infrequent changes; simplest |
| [Reloader](https://github.com/stakater/Reloader) controller | Mid-size clusters; watches resources and triggers rolling restarts automatically |
| Hash-based naming (`--append-hash`) | Large/complex clusters; forces workload update when config changes |
| Checksum annotation (Helm pattern) | Helm-managed workloads; add `checksum/config` annotation to pod template |

**Hash-based naming:**
```bash
# Creates configmap/app-config-<hash> — name changes when data changes
kubectl create configmap app-config --from-env-file=app.env --append-hash
# Update the Deployment to reference the new name → Pods restart automatically
```

**Immutable resources** (prevent accidental changes):
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-v3
immutable: true   # prevents updates; must delete and recreate to change
data:
  KEY: value
```

---

## StorageClass

A `StorageClass` is cluster-scoped and defines the provisioner, reclaim policy, and binding mode. Installed by the CSI driver.

```yaml
# k3s default (local-path) — inspect with:
kubectl get storageclass local-path -o yaml
```

**Key fields:**

| Field | Options | Notes |
|---|---|---|
| `provisioner` | `rancher.io/local-path`, `csi.hetzner.cloud`, `driver.longhorn.io` | Set by CSI driver install |
| `reclaimPolicy` | `Delete` (default), `Retain` | Default is `Delete` — **set `Retain` explicitly in production** to prevent data loss when PVCs are deleted |
| `volumeBindingMode` | `WaitForFirstConsumer`, `Immediate` | **Always use `WaitForFirstConsumer`** — respects affinity/resource constraints |
| `allowVolumeExpansion` | `true`, `false` | Set `true` for cloud volumes that support resize |

**Default StorageClass:** Only one should have `storageclass.kubernetes.io/is-default-class: "true"`. When a CSI driver installs its own StorageClass, verify it doesn't accidentally become the default.

### Storage option comparison (self-hosted)

| Option | IOPS | Fault tolerance | Snapshots | RWX | Notes |
|---|---|---|---|---|---|
| `local-path` (k3s default) | Highest (NVMe direct) | None (node-local) | No | No | Good for dev, small DBs |
| Hetzner Cloud Volumes | ~70% of local | Node-level (reattaches) | Yes (CSI VolumeSnapshot) | No | ~$5/TB/mo; needs `podAffinity` for RWO multi-pod |
| Longhorn | ~50% write, ~90% read | Multi-node replicas | Yes | Yes | Best for bare metal; needs 10 Gbps+ for good perf |

---

## Access Modes

| Mode | Abbreviation | Meaning |
|---|---|---|
| `ReadWriteOnce` | RWO | Read-write by Pods on **one node** |
| `ReadOnlyMany` | ROX | Read-only by Pods on **many nodes** |
| `ReadWriteMany` | RWX | Read-write by Pods on **many nodes** simultaneously |
| `ReadWriteOncePod` | RWOP | Read-write by **one Pod** only (stricter than RWO) |

**Most cloud block storage (EBS, Hetzner Cloud Volumes) only supports RWO.** If you need multiple Pods on different nodes to share a volume, use Longhorn (RWX) or co-locate Pods with `podAffinity`.

---

## PVC: Standalone (Deployment pattern)

Use when multiple Pods share the same volume. Requires `podAffinity` if the StorageClass only supports RWO.

```yaml
# 1. Create the PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pvc.hcloud-volumes
  namespace: misc
spec:
  storageClassName: hcloud-volumes
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

```yaml
# 2. Deployment referencing the PVC — podAffinity co-locates Pods on same node (required for RWO)
# Use preferredDuringScheduling (soft) not requiredDuringScheduling (hard) to avoid first-deploy deadlock:
# hard self-referential affinity deadlocks — no node has an app=cache Pod yet, so all Pods stay Pending
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cache
  namespace: misc
spec:
  replicas: 5
  selector: { matchLabels: { app: cache } }
  template:
    metadata: { labels: { app: cache } }
    spec:
      affinity:
        podAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values: [cache]
                topologyKey: kubernetes.io/hostname   # prefer same node
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: pvc.hcloud-volumes
      containers:
        - name: app
          image: ubuntu:24.04
          volumeMounts:
            - name: data
              mountPath: /etc/data
```

> **Tip:** If your StorageClass supports RWX (e.g., Longhorn), drop the `podAffinity` rule and Pods can spread across nodes for better fault tolerance.

---

## PVC: StatefulSet with volumeClaimTemplates

Use when each Pod needs its own independent volume (databases, per-instance state). Each Pod gets a dedicated PVC named `<template-name>-<statefulset-name>-<ordinal>` (e.g., `data-cache-0`, `data-cache-1`).

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: cache
  namespace: misc
spec:
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: hcloud-volumes
        resources: { requests: { storage: 10Gi } }
  selector: { matchLabels: { app: cache } }
  template:
    metadata: { labels: { app: cache } }
    spec:
      containers:
        - name: app
          image: ubuntu:24.04
          volumeMounts:
            - name: data
              mountPath: /etc/data
```

**No `podAffinity` needed** — each Pod has its own PVC, so they can schedule independently on different nodes.

### Deployment+PVC vs StatefulSet+volumeClaimTemplates

| | Deployment + PVC | StatefulSet + volumeClaimTemplates |
|---|---|---|
| Volume sharing | All Pods share one volume | Each Pod gets its own volume |
| Scheduling | Must co-locate (RWO) or use RWX | Pods can spread across nodes |
| Identity | Pods are interchangeable | Pods have stable names (`cache-0`, `cache-1`) |
| Use case | Shared cache, shared uploads | Databases, per-instance state |
| PVC lifecycle | Manual; survives Deployment delete | Auto-created; **not** auto-deleted with StatefulSet |

> **PVC cleanup:** `kubectl delete statefulset cache` does **not** delete the PVCs. Delete them explicitly after verifying:
> ```bash
> kubectl get pvc -n misc | grep cache   # verify which PVCs will be deleted
> kubectl delete pvc data-cache-0 data-cache-1 data-cache-2 -n misc   # delete by name, not label
> ```
> Avoid `kubectl delete pvc -l app=cache` — label-based bulk delete affects all PVCs with that label across all StatefulSets in the namespace.

---

## kubectl Storage Commands

```bash
# PVCs (namespaced)
kubectl get pvc -n <namespace>
kubectl describe pvc <name> -n <namespace>
kubectl delete pvc <name> -n <namespace>   # WARNING: irreversible if reclaimPolicy=Delete — verify with kubectl get pv first

# PVs (cluster-scoped)
kubectl get pv
kubectl describe pv <name>

# StorageClasses (cluster-scoped)
kubectl get storageclass
kubectl get storageclass <name> -o yaml

# Expand a PVC (StorageClass must have allowVolumeExpansion: true)
kubectl patch pvc <name> -n <namespace> \
  -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

---

## Backup Strategy

Two categories require backup: **cluster datastore** and **PersistentVolume data**.

### Cluster datastore (k3s)

| Datastore | Backup approach |
|---|---|
| SQLite (single-node default) | Stop k3s first (`systemctl stop k3s`), then copy `/var/lib/rancher/k3s/server/db/` — live copies of SQLite WAL files may be corrupt. Or use `sqlite3 state.db ".backup /tmp/k3s-backup.db"` for online backup. |
| External DB (PostgreSQL/MySQL) | Standard DB backup procedures |
| Embedded etcd (recommended) | `k3s etcd-snapshot` — auto-runs daily at 00:00 and 12:00, retains 5 snapshots (~2.5 days); increase `--etcd-snapshot-retention` (e.g., 14–30) and enable S3 upload for production |

```bash
# On-demand etcd snapshot
k3s etcd-snapshot save --name manual-$(date +%Y%m%d)

# Upload to S3 automatically (add to k3s server flags)
--etcd-s3 --etcd-s3-bucket=my-backup-bucket --etcd-s3-region=us-east-1
```

> **Critical:** Save `/var/lib/rancher/k3s/server/token` — etcd data is encrypted with this token. Without it, snapshots cannot be restored.

### PersistentVolume data

| Strategy | Use when |
|---|---|
| App-level dump (`pg_dump`, `tar`, `rsync`) | Need application-consistent or format-specific backup (e.g., `pg_dump` for PostgreSQL version upgrades); or when storage snapshots are unavailable |
| Storage system snapshots (Longhorn, AWS EBS) | General-purpose data; automate via storage UI or CronJob |
| [Velero](https://velero.io) | Full cluster backup + PV data; supports migration and disaster recovery |

**General recommendation:** Use Velero writing to S3-compatible storage. Store backups on a **different system** than the source data (different provider or region). Periodically test restores — untested backups are not backups.

```bash
# Velero backup (after installation)
velero backup create my-backup --include-namespaces production
velero restore create --from-backup my-backup
```
