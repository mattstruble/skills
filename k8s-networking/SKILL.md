---
name: k8s-networking
description: Use when configuring DNS records for a self-hosted domain, installing or configuring the NGINX Ingress controller, setting up TLS/SSL certificates with cert-manager and Let's Encrypt, writing NetworkPolicy resources, or creating a WireGuard VPN for cluster access. Also trigger on Flannel CNI configuration, exposing services externally, or debugging ingress routing. NOT for cluster setup (see k3s), workload resources (see k8s-workloads), storage/ConfigMaps/Secrets (see k8s-storage), Helm charts (see helm), or rollout strategies (see k8s-operations).
---

# k8s-networking

Patterns and decisions for DNS, Ingress, TLS, network policies, and VPN access in self-hosted Kubernetes clusters.

---

## DNS Record Quick Reference

| Record | Use when |
|---|---|
| **A** | Map domain/subdomain → IPv4 address. Use for your server's public IP. |
| **AAAA** | Map domain/subdomain → IPv6 address. Use when your server has a public IPv6. |
| **CNAME** | Delegate a subdomain to another hostname (e.g., `www.example.com` → `example.com`). Cannot be used at the apex (`@`). |
| **MX** | Specify the mail server for a domain. |
| **TXT** | Arbitrary data: domain ownership verification, SPF, DKIM. |
| **NS** | Delegate a zone to specific name servers. Set by your registrar. |

**Self-hosting setup:** Create an `A` record pointing your domain apex (`@`) to your server's public IP. For `www` redirect to work with NGINX Ingress, also create an `A` record for `www` (or a wildcard `*.example.com`).

**TTL guidance:** Use 300s (5 min) when making changes; raise to 3600s (1 hr) once stable. Values over a few days are often ignored by resolvers.

**Wildcard records:** `*.example.com` matches all first-level subdomains. Does not match second-level (`*.sub.example.com` needs a separate record). Most DNS providers do not support wildcards for ALIAS records.

---

## Flannel CNI (k3s default)

k3s ships with Flannel using the **VXLAN** backend by default. Flannel assigns a `/24` subnet per node from the cluster CIDR (`10.42.0.0/16` by default), supporting up to 255 nodes and ~254 pods per node.

**Backend options:**

| Backend | Use when | Notes |
|---|---|---|
| `vxlan` (default) | Most clusters | In-kernel, UDP port 8472, 50-byte overhead (MTU 1450) |
| `host-gw` | All nodes on same L2 switch | Fastest, no encapsulation; requires L2 adjacency |
| `wireguard` / `wireguard-native` | Encrypted inter-node traffic | ~90% native performance; kernel module preferred |

**k3s defaults to know:**
- Cluster CIDR: `10.42.0.0/16` (pods)
- Service CIDR: `10.43.0.0/16` (services)
- Cluster DNS: `10.43.0.10` (CoreDNS)
- NodePort range: `30000–32767`

Flannel itself does not enforce NetworkPolicies. k3s embeds the kube-router network policy controller internally (it does not run as a visible pod) to translate NetworkPolicy resources into iptables rules.

---

## Ingress NGINX Controller

**Why NGINX over Traefik:** More mature, larger community, better HTTP/2 and compression support, lower memory footprint under load. k3s ships Traefik by default — disable it at install time with `--disable=traefik`.

### Install

```bash
# Check https://github.com/kubernetes/ingress-nginx/releases for the current version
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/cloud/deploy.yaml
```

Use the **cloud** static manifest for k3s (creates a `LoadBalancer` service; k3s's Klipper handles the actual load balancing). Use **bare metal** only if you need a `NodePort` service instead.

After install, verify:

```bash
kubectl get pods -n ingress-nginx
kubectl get svc -n ingress-nginx  # ingress-nginx-controller should show EXTERNAL-IP
curl http://<your-server-ip>      # expect 404 (no Ingress rules yet)
```

### Basic Ingress (HTTP only)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  namespace: production
  annotations:
    nginx.ingress.kubernetes.io/from-to-www-redirect: "true"
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
spec:
  ingressClassName: nginx
  rules:
    - host: example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app-svc
                port:
                  number: 80
```

**Key rules:**
- `namespace` must match the target Service's namespace — cross-namespace routing returns 404.
- `ingressClassName: nginx` is required even with a single controller.
- `from-to-www-redirect: "true"` redirects `www.example.com` → `example.com` (or vice versa, depending on which host is in `rules`). Requires a DNS record for `www` to exist.

### Useful annotations

| Annotation | Purpose |
|---|---|
| `nginx.ingress.kubernetes.io/ssl-redirect: "true"` | Redirect HTTP → HTTPS (308) |
| `nginx.ingress.kubernetes.io/force-ssl-redirect: "true"` | Force HTTPS even behind an external TLS terminator |
| `nginx.ingress.kubernetes.io/from-to-www-redirect: "true"` | www ↔ apex redirect |
| `nginx.ingress.kubernetes.io/rewrite-target: /` | Strip path prefix before forwarding |
| `nginx.ingress.kubernetes.io/configuration-snippet: ...` | Inject raw nginx config into the `location` block. **⚠ Disabled by default since NGINX Ingress v1.9 (CVE-2021-25742). Enable only if all Ingress authors are trusted; never in multi-tenant clusters.** |
| `cert-manager.io/cluster-issuer: letsencrypt-production` | Trigger cert-manager to issue a certificate |

---

## TLS with cert-manager + Let's Encrypt

**Recommended approach:** cert-manager + Let's Encrypt production issuer + HTTP-01 challenge. Free, automated, renews at 2/3 of validity (every ~60 days of a 90-day cert).

**Staging vs production:**
- **Staging** (`acme-staging-v02.api.letsencrypt.org`): Higher rate limits, untrusted root — use to test your setup before going live. Always test with staging first.
- **Production** (`acme-v02.api.letsencrypt.org`): Trusted by all browsers; rate-limited (50 new certs/domain/week, renewals don't count). Switch to production after staging confirms your setup works.

For the full TLS setup guide, see [`references/tls-setup.md`](references/tls-setup.md).

### Quick reference: Ingress with TLS

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  namespace: production
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-production
    nginx.ingress.kubernetes.io/from-to-www-redirect: "true"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - example.com
        - www.example.com
      secretName: example-com-tls
  rules:
    - host: example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app-svc
                port:
                  number: 80
```

**Certificate issuance takes 10 seconds to a few minutes.** During this window, NGINX will redirect HTTP → HTTPS but the cert isn't ready yet — brief TLS errors are expected. Monitor with:

```bash
kubectl get certificaterequests -A
kubectl describe certificate example-com-tls -n production
```

---

## Network Policies

> **⚠ Flannel alone does not enforce NetworkPolicies.** k3s embeds the kube-router network policy controller to handle enforcement via iptables — this runs internally, not as a visible pod. If you replaced the default CNI or disabled kube-router, install a policy-capable CNI (Calico, Cilium) before creating NetworkPolicy resources, or they will be silently ignored.

**Default behavior:** Without any NetworkPolicy, all pods can reach all other pods and the internet ("default allow").

**When a NetworkPolicy is applied:** It switches the selected pods to "deny all" for the specified direction (Ingress, Egress, or both). Rules then selectively allow traffic. Multiple rules within a policy are OR'd — any matching rule allows the traffic.

**Recommended strategy: deny-all-then-allow.** Define both `Ingress` and `Egress` in `policyTypes`, then explicitly allow only what's needed. This limits blast radius if a pod is compromised.

### Selector types

| Selector | Matches |
|---|---|
| `podSelector` | Pods with matching labels in the same namespace |
| `namespaceSelector` | All pods in namespaces with matching labels |
| `ipBlock` | IP address ranges (CIDR), with optional `except` list |

Combine selectors within a single `from`/`to` entry for AND logic; use separate entries for OR logic.

### Allow all traffic (escape hatch)

```yaml
egress:
  - {}   # empty rule = allow everything
```

For the full NetworkPolicy patterns guide with examples, see [`references/network-policies.md`](references/network-policies.md).

---

## Accessing the Cluster from Outside

| Method | Best for | Limitation |
|---|---|---|
| **Ingress** | HTTP/HTTPS services | Not suitable for non-HTTP protocols |
| **NodePort** | Single non-HTTP service (e.g., a database for dev) | Exposes port on all nodes; security risk at scale |
| **`kubectl port-forward`** | Local dev/debug | Requires API server access; no UDP |
| **WireGuard VPN** | Dev teams, admin access, non-HTTP services | Security: all unprotected services become accessible |
| **Gateway API** | Multi-tenant, many services | Complex to set up |

**Recommendation:** Use Ingress for all HTTP/HTTPS traffic. Use WireGuard for developer/admin access to non-HTTP services and internal cluster DNS. Avoid NodePort for anything beyond temporary debugging.

For the WireGuard VPN setup guide, see [`references/wireguard.md`](references/wireguard.md).

---

## Local DNS for Cluster Services

To resolve cluster-internal service names (e.g., `my-svc.production.svc.cluster.local`) from your local machine via WireGuard, configure per-domain DNS forwarding.

**macOS** — create `/etc/resolver/cluster.local`:

```
domain cluster.local
nameserver 10.43.0.10
timeout 5
```

```bash
sudo killall -HUP mDNSResponder
```

**Ubuntu/Linux** — create `/etc/systemd/resolved.conf.d/cluster.conf`:

```ini
[Resolve]
DNS=10.43.0.10
Domains=cluster.local
```

```bash
sudo systemctl restart systemd-resolved
```

Replace `cluster.local` with your custom cluster domain if you set `--cluster-domain` at k3s install time.
