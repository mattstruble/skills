# Cluster Hardening and Operational Tools

Operational best practices for self-hosted Kubernetes clusters: server hardening, ingress tuning, Ansible automation, maintenance procedures, and useful tools.

---

## Server Security

### Firewall with ufw

Enable ufw on every server node. It denies all incoming and routed traffic by default.

> **Before running `ufw enable`:** Verify the SSH rule is present and correct with `ufw status`. If connecting over SSH on a non-standard port, replace `22` with the actual port. Run `ufw enable` inside a `screen`/`tmux` session so you can recover if the session drops. On cloud providers, also verify that the provider-level security group allows port 22 — ufw and security groups are independent layers.

```bash
# Allow SSH from anywhere (fail2ban handles brute-force protection)
# Prefer: restrict to known management IPs when possible
# ufw allow from <mgmt-ip>/32 to any port 22 proto tcp comment "ssh - management only"
ufw allow from any to any port 22 proto tcp comment "ssh"

# Allow HTTP/HTTPS
ufw allow 80,443/tcp comment "http and https"

# Allow WireGuard from known IP range only
ufw allow from 91.93.0.0/16 to any port 51820 proto udp comment "wireguard"

# Allow all traffic from private network (cluster nodes)
# Scope to actual cluster subnet (e.g., 10.0.1.0/24) rather than entire RFC-1918 block
ufw allow from 10.0.0.0/8

# Allow routed traffic from WireGuard interface
ufw route allow in on wg0 comment "wireguard to internal"

ufw status    # verify SSH rule is present before enabling
ufw enable
ufw status numbered
```

### fail2ban

fail2ban reads service logs and bans IPs that exceed failure thresholds. Install and configure via Ansible (see below). Verify status:

```bash
fail2ban-client status          # list active jails
fail2ban-client status sshd     # show banned IPs and failure counts
```

**Default jail.local** (overrides built-in defaults):

```ini
[DEFAULT]
bantime = 3600    # ban for 1 hour (default: 10 min)
maxretry = 3      # ban after 3 failures
```

### SSH Hardening

- Disable password authentication: `PasswordAuthentication no` in `/etc/ssh/sshd_config`
- Use key-based auth only; store private keys in `~/.ssh/` with `chmod 600`
- Restrict SSH to known IP ranges via ufw when possible

### Automatic Security Updates

`unattended-upgrades` is installed and enabled by default on Ubuntu 24.04. It applies security-only updates daily. Check the log:

```bash
tail -f /var/log/unattended-upgrades/unattended-upgrades.log
```

For controlled updates across multiple servers, use Ansible instead (see below).

---

## Ansible Automation

Use Ansible for any task performed more than once across servers: updates, package installs, service configuration, and verification.

**Install on macOS:**

```bash
brew install ansible
```

**Inventory file** (`inventory.ini`):

```ini
[local]
localhost ansible_connection=local

[k3s_controlplane]
myserver.example.com ansible_host=myserver.example.com ansible_ssh_private_key_file=~/.ssh/id_rsa

[k3s_controlplane:vars]
ansible_user=deploy        # use a non-root user; add become: yes to tasks that need root
ansible_become=yes
ansible_become_method=sudo
```

> **Avoid `ansible_user=root`.** Running Ansible as root means every task executes with full system privileges. Use a non-root user with `become: yes` only on tasks that require it. This limits blast radius if the control machine or a task is compromised.

**Server update + fail2ban playbook:**

```yaml
# playbook.yml
- name: Update Server and Configure fail2ban
  hosts: k3s_controlplane
  serial: 1                    # one host at a time
  gather_facts: false          # skip fact collection for speed

  vars:
    url_to_test: myserver.example.com

  tasks:
    - name: apt update and upgrade
      ansible.builtin.apt:
        update_cache: yes
        cache_valid_time: 3600
        upgrade: yes
      register: apt_update
      become: yes

    - name: install fail2ban
      ansible.builtin.apt:
        pkg: [fail2ban]
        state: present          # use 'latest' to also upgrade
      become: yes

    - name: start and enable fail2ban
      ansible.builtin.service:
        name: fail2ban
        state: started
        enabled: yes
      become: yes

    - name: Configure fail2ban jail.local
      ansible.builtin.copy:
        content: |
          [DEFAULT]
          bantime = 3600
          maxretry = 3
        dest: /etc/fail2ban/jail.local
        backup: true            # renames existing file with timestamp suffix
      become: yes
      notify: reload fail2ban

    - name: Verify site is reachable
      ansible.builtin.uri:
        url: "https://{{ url_to_test }}"
        status_code: 200

  handlers:
    - name: reload fail2ban
      ansible.builtin.command: fail2ban-client reload
      become: yes
```

**Run:**

```bash
ansible-playbook --inventory inventory.ini playbook.yml
```

**Tips:**
- Use `serial: 1` to update nodes one at a time — prevents simultaneous reboots
- Check site health at both start and end of playbook to catch pre-existing issues
- Use `ansible.builtin.*` module names (not short forms) for readability
- Add `inventory.ini` to `.gitignore` — it contains hostnames and key paths
- Explore Ansible Galaxy for provider-specific modules (Hetzner, AWS, etc.)

---

## NGINX Ingress Controller Tuning

### Global ConfigMap (`ingress-nginx-controller`)

> **⚠️ Security warning (CVE-2021-25742):** `allow-snippet-annotations: "true"` with `annotations-risk-level: "Critical"` allows any principal with Ingress write access to inject arbitrary NGINX config, including directives that can exfiltrate service account tokens or bypass network policies. Only enable on single-tenant clusters where every Ingress author is fully trusted. In multi-tenant clusters, leave both settings at their defaults (`false` / `High`).

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ingress-nginx-controller
  namespace: ingress-nginx
data:
  allow-snippet-annotations: "true"
  annotations-risk-level: "Critical"   # single-tenant only — see security warning above

  # Compression
  use-gzip: "true"
  gzip-level: "4"
  enable-brotli: "true"
  brotli-level: "6"

  # Security
  hide-headers: X-Powered-By           # strip server fingerprinting headers

  # Buffering
  client-body-buffer-size: "4M"        # increase for file uploads; default 8k

  http-snippet: |
    # Proxy cache zone (stored in /tmp/cache0)
    proxy_cache_path /tmp/cache0
      levels=1 keys_zone=cache0:20M
      max_size=2000M inactive=1h use_temp_path=off;

    # VPN/internal allowlist — these IPs bypass rate limiting
    geo $allow_list {
      default     0;
      10.0.0.0/8  1;
    }

    # Map allowlist to rate limit key.
    # NGINX skips limit_req enforcement when the zone key is an empty string —
    # this is the intended bypass mechanism for allowlisted IPs.
    map $allow_list $request_limiting_zone_key {
      0 $binary_remote_addr;
      1 "";
    }

    # Rate limit zones
    limit_req_zone $request_limiting_zone_key zone=per_ip_per_second:8m rate=10r/s;
    limit_req_zone $request_limiting_zone_key zone=per_ip_per_minute:12m rate=240r/m;
```

**Compression notes:** nginx handles compression; upstream servers must NOT set `Content-Encoding` headers or nginx will skip compression. Tune `gzip-level` and `brotli-level` based on CPU headroom and content type.

**Cache zone notes:** `keys_zone=cache0:20M` stores ~50,000 cache keys in memory. `max_size=2000M` is the disk cap. `inactive=1h` deletes files not accessed within 1 hour.

### Per-Ingress Annotations

```yaml
kind: Ingress
metadata:
  name: my-app
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/proxy-buffering: "on"
    nginx.ingress.kubernetes.io/proxy-buffers-number: "16"  # 4k + 16×4k = 68k in-memory buffer
    nginx.ingress.kubernetes.io/proxy-body-size: 15m        # max upload size; 413 if exceeded

    nginx.ingress.kubernetes.io/configuration-snippet: |
      # Enable proxy cache for this location
      proxy_cache cache0;
      proxy_cache_methods GET HEAD;
      proxy_cache_key $scheme$request_method$host$request_uri;  # $request_uri already includes query string
      proxy_cache_valid 200 60m;
      proxy_cache_bypass $cookie_nocache $arg_nocache;
      add_header X-Cache-Hit $upstream_cache_status;

      # Cache static assets only; disable for dynamic paths
      set $disable_cache 1;
      if ($request_uri ~ ^/build)  { set $disable_cache 0; }
      if ($request_uri ~ ^/images) { set $disable_cache 0; }
      proxy_no_cache $disable_cache;

      # Apply rate limits (burst allows short spikes; nodelay processes burst immediately)
      # For auth endpoints, use 'delay=N' instead of 'nodelay' to prevent credential stuffing
      limit_req zone=per_ip_per_second burst=60 nodelay;
      limit_req zone=per_ip_per_minute burst=120 nodelay;
```

**`configuration-snippet` security note:** Requires `allow-snippet-annotations: "true"` in the ConfigMap. See the security warning above — only enable on single-tenant clusters.

---

## sshuttle — VPN Alternative

When you need cluster-internal DNS resolution or private network access without setting up WireGuard:

```bash
brew install sshuttle

sshuttle \
  --remote deploy@myserver.example.com \
  --ssh-cmd 'ssh -i ~/.ssh/id_rsa' \
  --dns --to-ns=10.43.0.10 \
  10.0.0.0/8
# ^ forwards DNS to cluster CoreDNS; tunnels entire private network range
# sshuttle does not require root on the remote host — any SSH user with routing access works
```

**Limitation:** ~10% of direct connection speed. Use WireGuard for persistent access; use sshuttle for one-off debugging sessions.

---

## Node Maintenance

### Drain Before Maintenance

Always drain a node before rebooting or performing maintenance. Draining evicts all pods and marks the node unschedulable.

```bash
# Drain node (evicts all pods except DaemonSets)
kubectl drain <node-name> \
  --delete-emptydir-data=true \
  --ignore-daemonsets \
  --timeout=360s

# Perform maintenance...

# Re-enable scheduling after maintenance
kubectl uncordon <node-name>
```

**`--ignore-daemonsets`** is required — DaemonSet pods cannot be moved and would block the drain otherwise.

**Single-node clusters:** Draining the only node evicts all pods including CoreDNS. Plan for brief DNS outage.

### Hosting Provider Services

Use these to reduce downtime during maintenance:

- **Floating IP** — reassign the public IP to a standby server during maintenance; no DNS TTL wait
- **Private Network** — internal nodes don't need public IPs; reduces attack surface and simplifies firewall rules
- **Storage Volumes** — attach/detach between servers; cheaper than upsizing when only disk space is needed

---

## Useful CLI Tools

| Tool | Purpose | Install |
|---|---|---|
| **k9s** | Terminal UI — dense resource view, keyboard-driven, fast log/event access | `brew install k9s` |
| **kubectx** | Switch between clusters | `brew install kubectx` |
| **kubens** | Switch between namespaces | included with kubectx |
| **krew** | kubectl plugin manager | [krew.sigs.k8s.io](https://krew.sigs.k8s.io) |
| **kustomize** | Template-free config management; built into `kubectl apply -k` | built-in |

**Useful krew plugins:**

```bash
kubectl krew install neat          # strip noise from kubectl output (resourceVersion, uid, etc.)
kubectl krew install node-shell    # root shell on node host OS
kubectl krew install popeye        # scan cluster for misconfigurations
kubectl krew install tree          # show resource ownership tree
kubectl krew install ingress-nginx # inspect ingress-nginx (conf, ingress, certificates)
```

---

## Dashboard Tools

For large clusters or when a graphical interface is needed:

| Tool | Type | Notes |
|---|---|---|
| **k9s** | Terminal UI | Best for daily ops; keyboard-driven |
| **Kubernetes Dashboard** | Web (in-cluster) | Official; requires RBAC setup |
| **Lens** | Desktop | Full-featured IDE for Kubernetes |
| **Portainer** | Web (in-cluster) | Works with both Kubernetes and Docker |
| **Kubesphere** | Web (in-cluster) | Includes monitoring, logging, CI/CD, App Store |

### Handy kubectl Commands

```bash
# Explain any field
kubectl explain ingress.spec.ingressClassName

# Shell into a running container
kubectl exec -it <pod> -c <container> -n <ns> -- /bin/bash

# Debug with a sidecar (doesn't require bash in the target container)
kubectl debug <pod> -n <ns> --target=<container> --image=ubuntu:24.04 --profile=sysadmin -it -- bash

# Run a temporary pod for network debugging
kubectl run -n misc -it --rm --image=ubuntu:24.04 --restart=Never debug -- bash

# Watch warnings cluster-wide
kubectl events --types=Warning --all-namespaces --watch

# Stream logs from all pods matching a selector
kubectl logs --selector app=my-app -n production --timestamps=true --follow

# Check resource usage
kubectl top pod -A
kubectl top node
```

---

## Operators for Production

Use operators instead of manual management for stateful services. Operators manage the full lifecycle via CRDs.

| Operator | Purpose |
|---|---|
| **CloudNativePG** | PostgreSQL HA clusters with replicas, WAL archiving, connection pooling |
| **Rook** | Converts cluster to Ceph storage; provides Block, Filesystem, and Object PVs |
| **prometheus-operator** | Deploys Prometheus + Grafana + AlertManager via simple CRDs |
| **opentelemetry-operator** | Deploys OTEL collectors; injects sidecars for metrics/traces/logs |
| **gpu-operator** (NVIDIA) | Manages GPU drivers, container runtimes, and device plugins |

Browse all operators at [operatorhub.io](https://operatorhub.io).
