# TLS Setup: cert-manager + Let's Encrypt

Complete guide for obtaining and managing free SSL/TLS certificates for Kubernetes Ingress resources using cert-manager and Let's Encrypt.

---

## Prerequisites

- NGINX Ingress controller installed (see main SKILL.md)
- Domain's A record pointing to your server's public IP
- Port 80 accessible from the internet (required for HTTP-01 challenge)

---

## Step 1: Install cert-manager

Check for an existing installation first — re-applying over an existing cert-manager without following the upgrade path can corrupt CRD state:

```bash
kubectl get pods -n cert-manager 2>/dev/null
# If pods are already Running, follow the official upgrade guide instead
```

Install (pin to a specific version — check [cert-manager releases](https://github.com/cert-manager/cert-manager/releases) for the latest):

```bash
# Replace v1.16.3 with the current stable version
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.3/cert-manager.yaml
```

Wait for all pods to be running:

```bash
kubectl get pods -n cert-manager
# cert-manager, cert-manager-cainjector, cert-manager-webhook should all be Running
```

This installs cert-manager CRDs: `Certificate`, `CertificateRequest`, `ClusterIssuer`, `Issuer`, `Challenge`, `Order`.

---

## Step 2: Create a ClusterIssuer

`ClusterIssuer` is cluster-scoped (works from any namespace). Use it over namespace-scoped `Issuer` for most setups.

### Staging (test first)

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef:
      name: letsencrypt-staging-id
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

### Production

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-production
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: you@example.com
    privateKeySecretRef:
      name: letsencrypt-production-id
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

```bash
kubectl apply -f issuer.yaml
kubectl describe clusterissuer letsencrypt-production
# Status should show: Ready: True
```

**`email`:** Use a real address — Let's Encrypt sends security alerts here. cert-manager auto-renews certs, but you want to know if renewal fails.

**`privateKeySecretRef`:** cert-manager creates this secret automatically in the `cert-manager` namespace. It's your ACME account identity — don't delete it.

---

## Step 3: Update Ingress to Use TLS

Add the `cert-manager.io/cluster-issuer` annotation and a `tls` block:

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

**`secretName`:** cert-manager creates this Secret in the same namespace as the Ingress. It contains the TLS certificate and private key. Name it something meaningful like `<domain>-tls`.

**Multiple SANs:** Listing multiple hosts in `tls[].hosts` results in a single certificate with multiple Subject Alternative Names (SANs). Let's Encrypt allows up to 100 SANs per certificate.

**www + apex:** Include both `example.com` and `www.example.com` in `tls[].hosts` so the redirect from `http://www.example.com` → `https://www.example.com` → `https://example.com` works over a valid certificate at each step.

---

## Step 4: Monitor Certificate Issuance

```bash
# Watch the certificate request lifecycle
kubectl get certificaterequests -A
kubectl get certificates -n production

# Detailed status (shows challenge progress)
kubectl describe certificate example-com-tls -n production
kubectl describe certificaterequest -n production

# Challenge resources (created during HTTP-01 challenge)
kubectl get challenges -A
```

**Certificate request states:**
- `Pending` — challenge in progress or issuer not ready
- `Failed` — challenge failed or CA rejected the request (check `kubectl describe`)
- `Denied` — rejected by a cert-manager approver policy (rare in default installs; not the same as a CA rejection)
- `Approved` → `Issued` — success

**Typical issuance time:** 10 seconds to 2 minutes for HTTP-01.

**During issuance:** NGINX immediately starts redirecting HTTP → HTTPS, but the cert isn't ready yet. Expect brief TLS errors (< 30 seconds normally). This is expected behavior.

---

## Verify the Certificate

```bash
# Check HTTP redirect
curl --head http://example.com
# Expect: HTTP/1.1 308 Permanent Redirect, Location: https://example.com

# Check HTTPS response
curl --head https://example.com
# Expect: HTTP/2 200

# Inspect certificate details
curl -v --cert-status https://example.com 2>&1 | grep -E "issuer|subject|SSL"
# issuer should show: Let's Encrypt

# Full TLS handshake details
openssl s_client -connect example.com:443 -showcerts
```

Use [Qualys SSL Labs](https://www.ssllabs.com/ssltest/) for a comprehensive TLS configuration audit. A properly configured setup should score A or A+.

---

## Automatic Renewal

cert-manager automatically renews certificates after 2/3 of their validity period (Let's Encrypt issues 90-day certs, so renewal starts at ~60 days). No manual action needed.

If renewal fails, cert-manager retries. You'll receive an email from Let's Encrypt before expiry if cert-manager can't renew.

Monitor certificate expiry:

```bash
kubectl get certificates -A
# Check the READY column and EXPIRY
```

---

## Troubleshooting

**Challenge failing (HTTP-01):**
- Port 80 must be reachable from the internet — check cloud firewall rules
- The domain's A record must resolve to your server's IP
- The NGINX Ingress controller must be running

```bash
# Check if the challenge endpoint is reachable
curl http://example.com/.well-known/acme-challenge/test
# Should return 404 (not connection refused)
```

**Bootstrap deadlock: `ssl-redirect: "true"` set before cert is issued:**
If `ssl-redirect: "true"` is set and the certificate is stuck in `Pending`, Let's Encrypt's HTTP-01 challenge request to `http://example.com/.well-known/acme-challenge/<token>` may be getting redirected to HTTPS (308) before the cert exists, causing the challenge to fail. Fix:
```bash
# Temporarily disable ssl-redirect in the Ingress annotation, then:
kubectl delete certificaterequest -n production --all
# Re-apply the Ingress with ssl-redirect: "false", wait for cert issuance, then re-enable
```

**cert-manager webhook not ready (immediately after install):**
If `kubectl apply -f issuer.yaml` returns a webhook error right after installation, the cert-manager webhook pod may not be ready yet. Wait 60 seconds and retry:
```bash
kubectl get pods -n cert-manager  # all three pods must be Running
```

**Certificate stuck in Pending:**
```bash
kubectl describe challenge -n production
# Look for "Reason" field — usually DNS not propagated or port 80 blocked
```

**Wrong namespace:**
- The Ingress, Certificate, and target Service must all be in the same namespace
- ClusterIssuer is cluster-scoped (no namespace needed)
- The TLS secret is created in the Ingress's namespace

**Rate limits:** Let's Encrypt production allows 50 *new* certificates per registered domain per week. Renewals of existing certificates (same hostname set) do not count against this limit. Use staging to test. If you hit the limit, wait or use a subdomain.

---

## Staging → Production Migration

1. Test with `letsencrypt-staging` first — verify the challenge completes and a cert is issued (it will show as untrusted in browsers, which is expected)
2. Delete the staging certificate and secret:
   ```bash
   kubectl delete certificate example-com-tls -n production
   kubectl delete secret example-com-tls -n production
   ```
3. Update the Ingress annotation to `letsencrypt-production`
4. Apply and monitor issuance as above
