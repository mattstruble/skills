# WireGuard VPN for Cluster Access

Guide for creating a WireGuard VPN that gives developers and administrators direct access to cluster-internal services, pods, and DNS — without exposing ports publicly.

---

## When to Use This

WireGuard is the right choice when you need:
- Access to non-HTTP services (databases, Redis, etc.) from your local machine
- Cluster-internal DNS resolution (`my-svc.production.svc.cluster.local`)
- Multi-developer access to the same cluster without individual `kubectl port-forward` sessions
- Encrypted, authenticated tunnel with minimal setup

**Security note:** Once connected, all unprotected services in the cluster become accessible. Use NetworkPolicies to limit what VPN clients can reach (see `network-policies.md`).

---

## Architecture

```
[Your machine]  ←── WireGuard tunnel (UDP 51820) ───→  [Server node]
10.0.1.1/32                                             10.0.0.1/32
                                                              │
                                                    (iptables MASQUERADE)
                                                              │
                                              ┌───────────────┴──────────────┐
                                              │  Cluster network             │
                                              │  Pods:     10.42.0.0/16      │
                                              │  Services: 10.43.0.0/16      │
                                              └──────────────────────────────┘
```

**CIDR planning:**
- Server subnet: `10.0.0.0/24` (WireGuard server nodes)
- Client subnet: `10.0.1.0/24` (developers/admins)
- These must not overlap with cluster CIDR (`10.42.0.0/16`) or service CIDR (`10.43.0.0/16`)

Assign server node `10.0.0.1`, first client `10.0.1.1`, second client `10.0.1.2`, etc.

---

## Step 1: Install WireGuard on the Server Node

```bash
ssh root@your-server-ip
apt install wireguard -y
wg -v   # verify: wireguard-tools v1.0.x
```

---

## Step 2: Generate Key Pairs

**Security model:** Generate each key pair on the machine that will use it. Private keys must never leave the device that owns them. Only public keys are shared.

```bash
# On the SERVER — generate server keys only
wg genkey | tee server_privatekey | wg pubkey > server_publickey
cat server_privatekey   # copy this — goes in server [Interface] PrivateKey
cat server_publickey    # copy this — goes in each client's [Peer] PublicKey
rm server_privatekey server_publickey
```

```bash
# On each CLIENT MACHINE — generate client keys
wg genkey | tee client_privatekey | wg pubkey > client_publickey
cat client_privatekey   # stays on this machine — goes in client [Interface] PrivateKey
cat client_publickey    # copy this to the server — goes in server [Peer] PublicKey
rm client_privatekey client_publickey
```

Keys are 32-byte values base64-encoded to 44-character strings, always ending with `=`.

> **Key security:** Verify `/etc/wireguard/wg0.conf` is readable only by root: `ls -la /etc/wireguard/wg0.conf` (should show `-rw-------`). `wg-quick` sets this automatically, but confirm it. If you must transfer a public key, use an encrypted channel (e.g., `scp`).

---

## Step 3: Server Configuration

**Prerequisite: enable IP forwarding** (required for traffic to route from VPN clients to the cluster):

```bash
# On the server — enable and persist IP forwarding
echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.d/99-wireguard.conf
sysctl -p /etc/sysctl.d/99-wireguard.conf
# Verify:
sysctl net.ipv4.ip_forward   # should print: net.ipv4.ip_forward = 1
```

**Find your public interface name** (it may not be `eth0`):

```bash
ip route get 8.8.8.8 | awk '{print $5; exit}'
# Common values: eth0, ens3, ens5, enp3s0
```

Save to `/etc/wireguard/wg0.conf` on the server node (replace `eth0` with your interface name):

```ini
[Interface]
PrivateKey = <server-private-key>
Address = 10.0.0.1/32
ListenPort = 51820
PostUp   = iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer] # client0 - developer@example.com
PublicKey = <client0-public-key>
AllowedIPs = 10.0.1.1/32

# Add more [Peer] sections for additional clients
# [Peer] # client1 - another@example.com
# PublicKey = <client1-public-key>
# AllowedIPs = 10.0.1.2/32
```

**`PostUp`/`PostDown` MASQUERADE:** Enables NAT so VPN clients can route traffic through the server. `PostDown` removes the rule when the interface goes down — without it, duplicate rules accumulate on every restart.

**`AllowedIPs` on server:** The IP address(es) the client is allowed to use. Acts as both a routing rule and an access control — the server only accepts packets from a peer if the source IP is in `AllowedIPs`.

**If using `ufw` or `firewalld`:** Add a rule to allow traffic on the public interface before enabling WireGuard.

Start and enable:

```bash
wg-quick up wg0
wg show wg0              # verify interface is up, peer is listed
systemctl enable wg-quick@wg0.service
```

Open UDP port 51820 in your cloud firewall/security group.

---

## Step 4: Client Configuration

Install WireGuard on the client machine:
- **macOS:** `brew install wireguard-tools` or use the [WireGuard app](https://www.wireguard.com/install/)
- **Linux:** `apt install wireguard`
- **Windows/iOS/Android:** Official WireGuard app

Create the client config (save as `wg0.conf` or import into the WireGuard app):

```ini
[Interface]
PrivateKey = <client0-private-key>
Address = 10.0.1.1/32

[Peer]
PublicKey = <server-public-key>
Endpoint = <server-public-ip>:51820
PersistentKeepalive = 30
AllowedIPs = 10.0.0.0/8, <any-other-ips-to-route>
```

**`AllowedIPs` on client:** Traffic destined for these IPs is routed through the WireGuard tunnel. `10.0.0.0/8` covers the WireGuard network, cluster CIDR (`10.42.0.0/16`), and service CIDR (`10.43.0.0/16`) — all within the `10/8` private range.

> **`AllowedIPs` precision:** `10.0.0.0/8` routes *all* 10.x.x.x traffic through the tunnel. If your client is also connected to other 10.x.x.x networks (corporate VPN, home LAN), use more specific CIDRs to avoid routing conflicts:
> ```
> AllowedIPs = 10.0.0.0/24, 10.42.0.0/16, 10.43.0.0/16
> ```

**`PersistentKeepalive: 30`:** Sends a keepalive packet every 30 seconds to maintain the connection through NAT/firewalls. Required if your client is behind NAT (home router, etc.).

**Do NOT set `AllowedIPs = 0.0.0.0/0`** unless you want all internet traffic routed through the cluster. This causes slower DNS resolution and routes your traffic through the server's location.

Activate the tunnel:

```bash
# Linux
wg-quick up wg0

# macOS (wireguard-tools)
wg-quick up ./wg0.conf
```

---

## Step 5: Verify the Connection

```bash
# Ping the server's WireGuard interface
ping -c 1 10.0.0.1
# Expect: 64 bytes from 10.0.0.1: ...

# Ping a pod IP (get one with: kubectl get pods -n production -o wide)
ping -c 1 10.42.0.5

# Reach a service by ClusterIP
curl http://10.43.x.x:80

# Traceroute to a pod
traceroute 10.42.0.5
# Should show: 10.0.0.1 → 10.42.x.0 → 10.42.0.5
```

Check WireGuard status on the server:

```bash
wg show wg0
# Should show: latest handshake, transfer stats for the connected peer
```

---

## Step 6: Configure Local DNS for Cluster Services

With WireGuard connected, configure your machine to resolve cluster service names.

**macOS** — create `/etc/resolver/cluster.local`:

```
domain cluster.local
nameserver 10.43.0.10
timeout 5
```

```bash
sudo killall -HUP mDNSResponder
# Verify:
scutil --dns | grep -A5 "cluster.local"
```

**Ubuntu/Linux** — create `/etc/systemd/resolved.conf.d/cluster.conf`:

```ini
[Resolve]
DNS=10.43.0.10
Domains=cluster.local
```

```bash
sudo systemctl restart systemd-resolved
# Verify:
nslookup my-svc.production.svc.cluster.local
```

Replace `cluster.local` with your custom cluster domain if set.

Now you can reach services by name:

```bash
curl http://my-svc.production.svc.cluster.local
```

---

## Adding More Clients

On the server, add a new `[Peer]` section to `/etc/wireguard/wg0.conf`:

```ini
[Peer] # new-developer@example.com
PublicKey = <new-client-public-key>
AllowedIPs = 10.0.1.2/32
```

Apply without restarting (use `wg syncconf` — it performs a full sync including removals; `wg addconf` is append-only and cannot revoke access):

```bash
# Requires bash (uses process substitution)
wg syncconf wg0 <(wg-quick strip wg0)
```

Give the new client a config with `Address = 10.0.1.2/32` and the server's public key.

---

## Troubleshooting

**Can't ping server (10.0.0.1):**
- Check UDP 51820 is open in the cloud firewall
- Verify the server's `wg0` interface is up: `wg show wg0`
- Check the client has the correct server public key and endpoint IP

**Can reach server but not pods:**
- Verify `iptables MASQUERADE` is active: `iptables -t nat -L POSTROUTING`
- Check IP forwarding is enabled on the server: `sysctl net.ipv4.ip_forward` (should be 1)
  - Enable persistently: `echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.d/99-wireguard.conf && sysctl -p /etc/sysctl.d/99-wireguard.conf`

**DNS not resolving:**
- Confirm the WireGuard tunnel is up and `10.43.0.10` is reachable: `ping 10.43.0.10`
- On macOS, flush DNS cache: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`
- Use `dig @10.43.0.10 my-svc.production.svc.cluster.local` to test directly

**Handshake not completing:**
- ISPs sometimes block UDP — try from a different network
- Check the client's `AllowedIPs` includes the server's WireGuard IP (`10.0.0.0/8` covers it)
