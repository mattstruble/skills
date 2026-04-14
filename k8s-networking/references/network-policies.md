# NetworkPolicy Patterns

Reference guide for Kubernetes NetworkPolicy resources — strategies, selector patterns, and working examples.

---

## How NetworkPolicies Work

**Default state (no policies):** All pods can communicate with all other pods and the internet.

**When a NetworkPolicy selects a pod:** That pod switches to "deny all" for the specified `policyTypes`. Rules then selectively allow traffic. This is per-direction — defining only `Ingress` leaves `Egress` unrestricted.

**Rules are OR'd:** Multiple entries in `from`/`to` are OR conditions — any matching rule allows the traffic. There is no "deny" rule; you can only allow.

**Existing connections:** NetworkPolicy enforcement behavior for existing connections depends on the CNI implementation. With iptables-based enforcement (k3s/kube-router), existing TCP connections may be dropped when policies change because iptables rules update immediately. Do not rely on connection persistence across policy updates — restart pods to force re-evaluation if needed.

**Flannel + k3s:** Flannel itself doesn't enforce NetworkPolicies. k3s embeds the kube-router network policy controller internally (not visible as a pod) to translate policies into iptables rules. This works well for small/medium clusters; for large multi-tenant clusters, consider Calico or Cilium for better performance.

---

## Strategy: Deny-All-Then-Allow

Define both `Ingress` and `Egress` in `policyTypes` with no rules — this denies everything. Then add explicit allow rules.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all
  namespace: production
spec:
  podSelector: {}   # applies to ALL pods in the namespace
  policyTypes:
    - Ingress
    - Egress
  # No ingress/egress rules = deny all traffic
```

Apply this first, then add per-app policies that allow what's needed.

**Alternative:** Apply deny-all per-app by using `podSelector.matchLabels` instead of `{}`.

---

## Selector Reference

### podSelector

Selects pods by label within the same namespace as the policy:

```yaml
spec:
  podSelector:
    matchLabels:
      app: my-app
```

Empty `podSelector: {}` selects all pods in the namespace.

### namespaceSelector

Selects all pods in namespaces with matching labels. Kubernetes automatically adds `kubernetes.io/metadata.name: <namespace-name>` to all namespaces:

```yaml
from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: ingress-nginx
```

### ipBlock

Selects IP ranges, with optional exclusions:

```yaml
from:
  - ipBlock:
      cidr: 10.0.1.0/24
      except:
        - 10.0.1.100/32
```

### Combining selectors (AND vs OR)

**OR:** Separate entries in `from`/`to` — any match allows:

```yaml
from:
  - namespaceSelector:
      matchLabels:
        kubernetes.io/metadata.name: ingress-nginx
  - podSelector:
      matchLabels:
        purpose: monitoring
```

**AND:** Both selectors in the same entry — both must match:

```yaml
from:
  - namespaceSelector:
      matchLabels:
        env: production
    podSelector:
      matchLabels:
        app: prometheus
```

---

## Example: Web App Policy

Allow ingress from the NGINX controller, specific pods, and a VPN subnet. Allow egress to the internet on ports 80/443 only.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: web-app-policy
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
        - podSelector:
            matchLabels:
              purpose: misc
            # Caution: a bare podSelector without namespaceSelector matches pods
            # in the *same namespace as this policy* (production), not cluster-wide.
            # To allow pods from a different namespace, combine namespaceSelector
            # + podSelector in the same entry (AND logic — see Selector Reference).
        - ipBlock:
            cidr: 10.0.1.0/24   # WireGuard client subnet
  egress:
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
            except:
              - 3.0.0.0/8       # exclude AWS IP range (example)
      ports:
        - port: 80
          protocol: TCP
        - port: 443
          protocol: TCP
```

---

## Example: Allow All Egress

When you want to restrict ingress but leave egress unrestricted:

```yaml
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
  egress:
    - {}   # empty rule = allow all egress
```

---

## Example: Database Policy

Allow ingress only from the application namespace; deny all egress (databases shouldn't initiate outbound connections):

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: postgres-policy
  namespace: db
spec:
  podSelector:
    matchLabels:
      app: postgres
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: production
          podSelector:
            matchLabels:
              app: my-app
      ports:
        - port: 5432
          protocol: TCP
  # No egress rules = deny all egress (including DNS).
  # Safe for a single-instance Postgres with IP-only pg_hba.conf.
  # If your database uses hostname-based pg_hba.conf rules, logical
  # replication targets, or any extension making outbound connections,
  # add a DNS egress rule — see "Allow DNS Egress" example below.
```

---

## Example: Allow DNS Egress

Pods need to resolve DNS (port 53 UDP/TCP) to function. If you lock down egress, always add a DNS allow rule. Use the tighter AND selector to target only CoreDNS pods (not all kube-system pods):

```yaml
egress:
  - to:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: kube-system
        podSelector:
          matchLabels:
            k8s-app: kube-dns   # targets CoreDNS only, not all kube-system pods
    ports:
      - port: 53
        protocol: UDP
      - port: 53
        protocol: TCP
  # ... other egress rules
```

Or allow DNS by IP (CoreDNS service IP in k3s — more specific, no namespace selector needed):

```yaml
egress:
  - to:
      - ipBlock:
          cidr: 10.43.0.10/32
    ports:
      - port: 53
        protocol: UDP
      - port: 53
        protocol: TCP
```

---

## Debugging NetworkPolicies

```bash
# List all policies in a namespace
kubectl get networkpolicies -n production

# See full policy spec
kubectl describe networkpolicy web-app-policy -n production

# Test connectivity from a pod
kubectl exec -it <pod-name> -n production -- curl -v http://other-service.other-ns.svc.cluster.local

# Check if kube-router is enforcing policies (k3s)
# Note: kube-router is embedded in k3s — it does NOT appear as a pod.
# Check k3s logs instead:
journalctl -u k3s | grep -i netpol

# Force policy re-evaluation (close existing connections)
kubectl delete pod <pod-name> -n production
```

**Cilium Network Policy Editor:** If you're using Cilium as your CNI, use the [Cilium Network Policy editor](https://editor.cilium.io/) to visually create and validate policies. It supports both standard Kubernetes NetworkPolicy and Cilium-specific policies.

---

## Common Pitfalls

**Forgot DNS egress:** Locking down egress without allowing port 53 breaks all DNS resolution in the pod. Symptoms: connection refused to service names, but direct IP connections work.

**Namespace label not set:** `namespaceSelector` requires the namespace to have the label you're matching. Kubernetes auto-sets `kubernetes.io/metadata.name` for all namespaces, but custom labels must be set manually.

**Wrong namespace for policy:** NetworkPolicies are namespace-scoped. A policy in `production` only affects pods in `production`.

**Ingress controller blocked:** If you add a deny-all policy without allowing the `ingress-nginx` namespace, the NGINX controller can't reach your pods — all ingress traffic returns 502.

**Existing connections may be dropped:** With iptables-based enforcement (k3s/kube-router), updating a policy can drop existing TCP connections immediately because iptables rules change at the kernel level. Restart pods to force re-evaluation with the new policy.
