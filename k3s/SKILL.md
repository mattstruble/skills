---
name: k3s
description: Use when installing or managing a self-hosted Kubernetes cluster with k3s, setting up kubectl or kubeconfig, adding server or agent nodes, or choosing between single-node and multi-node topologies. Also trigger on embedded etcd vs SQLite datastore decisions, k3s systemd service configuration, or accessing a cluster remotely. NOT for workload resources like Deployments or Services (see k8s-workloads), networking and ingress (see k8s-networking), storage (see k8s-storage), Helm (see helm), or containerizing applications (see docker).
---

# k3s

Patterns and decisions for installing, configuring, and scaling k3s Kubernetes clusters in self-hosted environments.

---

## Distribution Decision

**Choose k3s when** self-hosting on VPS, homelab, Raspberry Pi, or edge — single binary (~65 MB), reasonable defaults, supports single-node through large clusters, CNCF-maintained, production-ready.

**Alternatives and when to prefer them:**
- **minikube / Docker Desktop / Orbstack embedded K8s** — local dev/learning only; not for production
- **k0s** — similar philosophy to k3s, less mature ecosystem
- **kubeadm** — full control over every component; only if you have specific requirements and operational expertise
- **Cloud-managed (EKS, GKE, AKS)** — when you don't want to manage the control plane; costs more but eliminates operational overhead
- **Docker Compose / Kamal** — single-host only, no self-healing or rolling updates; fine for simple apps that don't need cluster features

**k3s defaults you should know:**
- Container runtime: `containerd`
- CNI: Flannel (VXLAN)
- DNS: CoreDNS
- Ingress: Traefik (disabled in this guide — use ingress-nginx instead)
- Datastore: SQLite (single-node) or embedded etcd (HA, requires `--cluster-init`)
- Storage: Local Path Provisioner

---

## Core Concepts (Brief)

| Term | What it is |
|---|---|
| **Node** | Server running `kubelet`. Can be control-plane, worker, or both (k3s default) |
| **Pod** | Smallest deployable unit — one or more containers sharing context |
| **Deployment / StatefulSet** | Manages Pod lifecycle; use Deployment for stateless, StatefulSet for stateful (DBs) |
| **Service** | Stable endpoint for Pods; DNS-resolvable within the cluster |
| **Ingress** | Routes external HTTP/S traffic to Services |
| **Namespace** | Logical partition; scope for RBAC, resource quotas, and organization |
| **ConfigMap / Secret** | Runtime config injected as env vars or files; Secret for sensitive data |

**Control plane components** (run on server nodes): `etcd`, `kube-apiserver` (port 6443), `kube-scheduler`, `kube-controller-manager`

**Worker components** (run on all nodes): `kubelet`, `containerd`, `kube-proxy`

In k3s, server nodes run both by default. Control-plane-only nodes require taints or the experimental `--disable-agent` flag.

---

## Installation: Single-Node

```bash
# On the server (Ubuntu 24.04, as root)
apt install curl -y
# Pin the version — check https://github.com/k3s-io/k3s/releases for the latest stable
# Replace YOUR_PUBLIC_IP with the server's public IP
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.32.3+k3s1 sh -s - server \
  --disable=traefik \
  --cluster-init \
  --cluster-domain=cluster.local \
  --tls-san=YOUR_PUBLIC_IP

# Verify
k3s kubectl get nodes
# NAME              STATUS   ROLES                       AGE   VERSION
# node0.example.com Ready    control-plane,etcd,master   96s   v1.32.3+k3s1
```

**Flag decisions:**
- `INSTALL_K3S_VERSION` — always pin to a specific release; without it, the install script pulls the latest version, which may differ from what you tested or from what other nodes in your cluster are running; version skew between nodes causes instability
- `--disable=traefik` — remove the default ingress controller; install ingress-nginx separately for more control
- `--cluster-init` — use embedded etcd instead of SQLite; required if you ever want to add more control-plane nodes; enables automatic migration path
- `--cluster-domain` — set a custom cluster domain for CoreDNS; must match across all nodes; defaults to `cluster.local`
- `--tls-san` — add your server's public IP/hostname to the TLS certificate SAN list; required for remote kubectl access; without it, `kubectl` fails with an x509 certificate error when connecting via the public IP

> **If installation fails:** Run `/usr/local/bin/k3s-uninstall.sh` before retrying to ensure a clean state. The uninstall script removes all k3s data including etcd.

**Datastore choice:**
- **SQLite (default, no `--cluster-init`)** — simplest; fine for single-node that will never scale to HA; single file, easy to back up
- **Embedded etcd (`--cluster-init`)** — required for multi-server HA; adds ~100 MB RAM overhead; use this unless resources are extremely constrained
- **External DB (`--datastore-endpoint`)** — use if your team already manages PostgreSQL/MySQL; reduces control-plane node resource requirements

> **Static IP required.** Kubernetes needs a stable node IP. On DHCP networks, assign a static IP before installing.

---

## kubeconfig Setup

k3s auto-generates `/etc/rancher/k3s/k3s.yaml` on install. The server address defaults to `127.0.0.1:6443` — update it for remote access.

**Remote access (recommended pattern):**

```bash
# On the server: print the kubeconfig
cat /etc/rancher/k3s/k3s.yaml
```

Copy the output to your local machine, save as e.g. `~/clusters/mycluster.yaml`. Then open the file and change the `.clusters[0].cluster.server` value from `https://127.0.0.1:6443` to your server's actual public IP or hostname:

```yaml
# Before:
server: https://127.0.0.1:6443
# After:
server: https://YOUR_PUBLIC_IP:6443
```

```bash
# On local machine: export before each session
export KUBECONFIG=/Users/you/clusters/mycluster.yaml
kubectl get nodes
```

**Three ways to supply kubeconfig (in order of preference for self-hosting):**

1. `export KUBECONFIG=<absolute-path>` — most flexible; works with kubectl, helm, k9s, kubectx; set at the start of each shell session
2. `--kubeconfig <path>` flag — per-command; impractical for regular use
3. `~/.kube/config` — convenient for single-cluster local dev; not recommended when managing multiple clusters

> Store kubeconfig outside the project directory or add it to `.gitignore` and `.dockerignore`. It contains credentials and certificates.

**Certificate expiry:** The user cert expires after 365 days and is renewed automatically the next time k3s restarts (within 90 days of expiry). On long-running clusters, restart k3s before the cert expires: `systemctl restart k3s`. After renewal, re-copy the kubeconfig file. Check cert status: `k3s certificate check --output table`

> **If the k3s service fails to start after cert expiry** (cert expired while service was stopped): run `k3s certificate rotate` as root, then `systemctl restart k3s`.

---

## kubectl Essentials

```bash
# Cluster state
kubectl get nodes                          # list nodes with roles and status
kubectl get nodes --show-labels            # include node labels
kubectl cluster-info                       # control plane and DNS addresses
kubectl version                            # client and server versions

# Resources (works for any resource type)
kubectl get pods                           # pods in current namespace
kubectl get pods -n kube-system            # specific namespace
kubectl get pods -A                        # all namespaces
kubectl get pods -A -w                     # watch for changes
kubectl describe pod <name>                # detailed state + events
kubectl logs <pod> -f                      # stream logs
kubectl logs <pod> -c <container>          # specific container in multi-container pod

# Namespaces
kubectl get namespaces                     # list all
kubectl create namespace db
kubectl config set-context --current --namespace=db   # switch default namespace
kubectl config view --minify | grep namespace:        # confirm current namespace

# Apply / delete
kubectl apply -f manifest.yaml             # create or update
kubectl delete -f manifest.yaml            # delete resources defined in file
kubectl delete pod <name>                  # delete a specific resource

# Debugging
kubectl exec -it <pod> -- /bin/sh          # shell into a pod
kubectl port-forward pod/<name> 8080:80    # forward local port to pod
kubectl get events -A -w                   # watch all events (essential for troubleshooting)

# Context management
kubectl config get-contexts                # list all contexts
kubectl config use-context <name>          # switch context
kubectl config set-context --current --namespace=<ns>  # change namespace in current context
```

**Namespace-scoped vs cluster-scoped resources:**
- Namespace-scoped: Pods, Deployments, Services, ConfigMaps, Secrets — always specify `-n` or `-A` if not in the right namespace
- Cluster-scoped: Nodes, PersistentVolumes, StorageClasses, Namespaces — no `-n` flag needed

```bash
# List all cluster-scoped resources
kubectl api-resources --namespaced=false
```

For a full kubectl cheatsheet, see [`references/kubectl-cheatsheet.md`](references/kubectl-cheatsheet.md).

---

## Namespace Conventions

Four built-in namespaces: `default` (educational only), `kube-system` (system components), `kube-node-lease` (heartbeats), `kube-public` (public certs).

**Recommended starting namespaces for small clusters:**

```bash
kubectl create namespace db          # databases (PostgreSQL, Redis, etc.)
kubectl create namespace production  # production workloads
kubectl create namespace test        # test/staging workloads
kubectl create namespace misc        # anything that doesn't fit elsewhere
```

Never deploy production workloads to `default`. It has no RBAC boundaries and is a common source of accidental deletions.

---

## Single-Node vs Multi-Node Decision

```
Single node (server only)
├── Pros: simple, cheap, easy to manage
├── Cons: no HA — control plane loss = no cluster management (pods keep running)
└── Use when: dev/staging, low-traffic production, budget-constrained

2 nodes (1 server + 1 agent)
├── Pros: workload isolation from control plane
├── Cons: 1 etcd member, no fault tolerance — losing the server destroys cluster state
└── Avoid: worse than 1 or 3; not recommended

3 server nodes (recommended HA minimum)
├── Pros: quorum = 2, survives 1 node loss; full HA
├── Cons: 3x control-plane resource overhead
└── Use when: production requiring HA

3 server + N agent nodes
├── Pros: scales workload capacity without affecting quorum
└── Use when: workload demands exceed 3 server nodes' capacity
```

**Key rule:** Always use an odd number of server nodes (1, 3, 5, 7...). Even numbers don't improve fault tolerance and risk split-brain.

For the full clustering guide (adding server and agent nodes step-by-step), see [`references/clustering.md`](references/clustering.md).

---

## k3s Service Management

```bash
# Service control
systemctl status k3s            # check status
systemctl restart k3s           # restart (on server nodes)
systemctl restart k3s-agent     # restart (on agent nodes)

# View startup flags
cat /etc/systemd/system/k3s.service

# Logs
journalctl -u k3s -f            # stream k3s logs
journalctl -u k3s-agent -f      # stream agent logs

# Token (needed to add nodes)
cat /var/lib/rancher/k3s/server/token

# Built-in tools
k3s kubectl get nodes           # kubectl without separate kubeconfig
k3s etcd-snapshot               # backup etcd state
k3s token create                # generate a bootstrap token (expires 24h)
k3s certificate check --output table  # check cert expiry
```

---

## Required Ports (Firewall Rules)

| Port | Protocol | Direction | Purpose |
|---|---|---|---|
| 6443 | TCP | Agent nodes → server nodes | API server (kubectl + kubelet) |
| 2379-2380 | TCP | Server nodes ↔ server nodes | etcd client + peer (HA only) |
| 8472 | UDP | All nodes ↔ all nodes | Flannel VXLAN (pod networking) |
| 10250 | TCP | All nodes ↔ all nodes | kubelet metrics/logs |

Open these between nodes before adding them to the cluster. Missing ports are the most common cause of nodes stuck in `NotReady`.

> **Security:** Port 6443 must be accessible between cluster nodes and your workstation, but must **not** be open to the public internet (`0.0.0.0/0`). Restrict it to known source IPs in your cloud firewall. For remote access from dynamic IPs, use a VPN or SSH tunnel (`ssh -L 6443:localhost:6443 user@server`) rather than exposing the API server directly.
