# Clustering Guide: Adding Nodes to a k3s Cluster

This guide adds 5 nodes to an existing single-server cluster, resulting in 3 server (control-plane + worker) nodes and 3 agent (worker-only) nodes.

**Prerequisites:**
- Existing k3s cluster initialized with `--cluster-init` (embedded etcd)
- All new nodes: unique hostnames, Ubuntu 24.04, root access, packages updated
- **Clock synchronization:** verify NTP is running on all nodes: `timedatectl status` must show `System clock synchronized: yes`. etcd rejects writes when clock skew exceeds 5 minutes.
- Firewall ports open between all nodes: 6443 TCP, 2379-2380 TCP, 8472 UDP, 10250 TCP

---

## Step 1: Get Server Node Information

Log into the existing server node and collect what you need:

```bash
# root@node0

# Check current cluster state and note the k3s version
kubectl get nodes
# NAME    STATUS   ROLES                       AGE   VERSION
# node0   Ready    control-plane,etcd,master   20m   v1.32.3+k3s1

# Check the flags used to start k3s (you must replicate these on new server nodes)
cat /etc/systemd/system/k3s.service
# ExecStart=/usr/local/bin/k3s \
#   server \
#     '--disable=traefik' \
#     '--cluster-init' \
#     '--cluster-domain=cluster.example.com'

# Get the server token (used to join server nodes)
cat /var/lib/rancher/k3s/server/token
# K105a41e16fd8dcf24cc6fcb98e8da22ce01664d24a6d8d89ab66acfb8f71daf693::server:...
```

**What to record:**
- k3s version (e.g., `v1.32.3+k3s1`)
- All flags from `k3s.service` — new server nodes must use the same `--cluster-domain`, `--disable`, etc.
- Server token from `/var/lib/rancher/k3s/server/token`
- IP address of the existing server node (e.g., `128.140.38.89`)

---

## Step 2: Add Server Nodes (Control Plane + Worker)

> **`--cluster-init` must only appear on the first server node.** Do NOT include it when joining additional server nodes — it causes the joining node to bootstrap a new independent cluster instead of joining the existing one. Use `--server` instead.

> **`--server` is a single point of failure during joins.** The IP you specify must be reachable at join time. If that node is down, the join fails even if other server nodes are healthy. For production, use a load balancer address as `--server` so joins are resilient to individual node failures.

Run this on each new server node. Repeat for node1, node2, etc.

```bash
# root@node1

curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION=v1.32.3+k3s1 \
  K3S_TOKEN="K105a41e16fd8dcf24cc6fcb98e8da22ce01664d24a6d8d89ab66acfb8f71daf693::server:..." \
  sh -s - server \
    --disable=traefik \
    --cluster-domain=cluster.example.com \
    --server https://128.140.38.89:6443 \
    --with-node-id
```

**Flag explanations:**
- `INSTALL_K3S_VERSION` — pin to the same version as the existing cluster; mismatched versions can cause instability
- `K3S_TOKEN` — pass the server token as an environment variable, not `--token`; CLI arguments are visible in `ps aux` during install
- `sh -s - server` — the `-s -` reads from stdin; `server` tells k3s to run as a server node (control plane + worker)
- `--disable=traefik` and `--cluster-domain` — must match the existing server node exactly; mismatched cluster domains break CoreDNS
- `--server` — URL of any existing server node's API server; the new node uses this to join and then discovers the rest
- `--with-node-id` — appends a random suffix to the hostname (e.g., `node1-1d0f0cb8`); prevents join failures if you forget to set a unique hostname

> **Server token security:** The server token never expires and grants full cluster join access — treat it like a root password. Never log it, paste it into chat, or store it in version control.

After the command completes, the new node downloads the k3s binary, joins the etcd cluster, and starts the systemd service.

**Verify after adding each server node:**

```bash
kubectl get nodes
# NAME            STATUS  ROLES                       AGE   VERSION
# node0           Ready   control-plane,etcd,master   76m   v1.32.3+k3s1
# node1-1d0f0cb8  Ready   control-plane,etcd,master   74m   v1.32.3+k3s1
# node2-cb027f33  Ready   control-plane,etcd,master   73m   v1.32.3+k3s1
```

Wait for `STATUS=Ready` before adding the next node — adding nodes too quickly can cause etcd quorum issues. If a node is not `Ready` within 5 minutes, stop and check logs before proceeding (see Troubleshooting below).

---

## Step 3: Create a Bootstrap Token for Agent Nodes

After adding server nodes, create a short-lived token for agent nodes. This limits blast radius if the token is compromised.

```bash
# Run on any server node
k3s token create
# K105a41e..........71daf693::fjbqh0.ds4qixqahd34o3yh
```

This token expires after 24 hours. Use the server token (`/var/lib/rancher/k3s/server/token`) if you need a permanent token, but prefer bootstrap tokens for agent joins.

---

## Step 4: Add Agent Nodes (Worker-Only)

> **`--server` is a single point of failure during joins.** Use a load balancer address in production so agent joins are resilient to individual server node failures.

Run this on each agent node. Agent nodes do not run control-plane components and don't affect etcd quorum.

```bash
# root@node3

curl -sfL https://get.k3s.io | \
  INSTALL_K3S_VERSION=v1.32.3+k3s1 \
  K3S_TOKEN="K105a41e..........71daf693::fjbqh0.ds4qixqahd34o3yh" \
  sh -s - agent \
    --server https://128.140.38.89:6443 \
    --with-node-id
```

**Differences from server join:**
- `sh -s - agent` — installs worker components only (`kubelet`, `containerd`); no etcd, no API server
- No `--disable`, `--cluster-domain`, or other control-plane flags needed
- Creates `k3s-agent.service` (not `k3s.service`)
- Agent nodes appear with `ROLES=<none>` in `kubectl get nodes`

**Mixed architecture is supported.** You can join ARM64 nodes to an x86-64 cluster. k3s detects the architecture and downloads the correct binary. The `INSTALL_K3S_VERSION` must match the version string (same version, different arch binary is downloaded automatically).

---

## Step 5: Verify the Full Cluster

```bash
kubectl get nodes
# NAME             STATUS  ROLES                       AGE   VERSION
# node0            Ready   control-plane,etcd,master   94m   v1.32.3+k3s1
# node1-1d0f0cb8   Ready   control-plane,etcd,master   34m   v1.32.3+k3s1
# node2-cb027f33   Ready   control-plane,etcd,master   92m   v1.32.3+k3s1
# node3-27428e58   Ready   <none>                      90m   v1.32.3+k3s1
# node4-69e8bfaa   Ready   <none>                      89m   v1.32.3+k3s1
# node5-484b6be2   Ready   <none>                      85m   v1.32.3+k3s1
```

Server nodes: `ROLES=control-plane,etcd,master`
Agent nodes: `ROLES=<none>`

**After adding server nodes:** Update the kubeconfig to point to any server node's IP — they all serve the API identically. For production, put a load balancer in front of the server nodes and point the kubeconfig at the load balancer.

---

## Token Reference

| Token type | Location | Joins | Expires |
|---|---|---|---|
| Server token | `/var/lib/rancher/k3s/server/token` | server + agent | Never |
| Agent token | Same as server token by default | agent only | Never |
| Bootstrap token | `k3s token create` | agent only | 24h (default) |

**Token formats:**
- Short: `K105a41e...` (20-40 chars) — credentials only
- Long: `K105a41e...::fjbqh0.ds4qixqahd34o3yh` (~90-110 chars) — includes CA hash for certificate verification

Use the long format when possible: if the CA hash doesn't match, the join fails before credentials are transmitted.

---

## Troubleshooting Node Joins

**Node stuck in `NotReady`:**
```bash
# On the stuck node
journalctl -u k3s -f          # server node logs
journalctl -u k3s-agent -f    # agent node logs

# Common causes:
# - Firewall blocking port 6443, 8472, or 10250
# - Clock skew > 5 minutes between nodes (etcd is sensitive to time drift)
# - Mismatched --cluster-domain between server nodes
# - Duplicate hostname (use --with-node-id to avoid)
```

**Remove a node from the cluster:**

> **Quorum warning (server nodes):** Removing a server node from a 3-node cluster leaves 2 nodes — quorum is maintained but you lose all fault tolerance. Do not remove a second server node without first adding a replacement.

```bash
# Drain workloads off the node first
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Delete the node object
kubectl delete node <node-name>

# On the node itself, uninstall k3s
# WARNING: k3s-uninstall.sh is destructive and irreversible — removes the k3s binary,
# all configuration, container images, and local volumes. For server nodes, also removes etcd data.
/usr/local/bin/k3s-uninstall.sh        # server nodes
/usr/local/bin/k3s-agent-uninstall.sh  # agent nodes
```
