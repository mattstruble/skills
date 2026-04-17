# Docker Daemon Configuration

Docker daemon settings live in `/etc/docker/daemon.json`. Changes require a daemon restart: `sudo systemctl restart docker`.

---

## Log Rotation

Without configuration, container logs grow unbounded and can fill the host disk. The default `json-file` driver has no size limit.

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

This caps each container's log at 30 MB total (3 files × 10 MB). Applies to all new containers; existing containers keep their current log driver until recreated.

**Alternatives:**
- `"log-driver": "syslog"` — forward to the host syslog (journald, rsyslog)
- `"log-driver": "fluentd"` — forward to a Fluentd/Fluent Bit aggregator for centralized logging

---

## Storage Location

By default Docker stores images, containers, and volumes under `/var/lib/docker`. On systems where `/var` is on the root partition, large images can exhaust disk space.

```json
{
  "data-root": "/opt/docker"
}
```

Move `data-root` to a dedicated volume before pulling any images. Migrating after the fact requires stopping Docker, copying `/var/lib/docker` to the new path, and updating `daemon.json`.

**Filesystem recommendation:** XFS is preferred for the `overlay2` storage driver because it supports project quotas, enabling per-container disk limits. ext4 works but lacks quota support.

---

## Network Address Pools

Docker's default bridge network uses `172.17.0.0/16`. This range frequently collides with corporate VPN subnets, causing routing failures when the VPN is active.

```json
{
  "bip": "169.254.1.1/24",
  "fixed-cidr": "169.254.1.0/24",
  "default-address-pools": [
    {
      "base": "169.254.0.0/16",
      "size": 28
    }
  ],
  "mtu": 1500
}
```

`169.254.0.0/16` is link-local (RFC 3927) — non-routable and not assigned to any corporate network. Each Compose project gets a `/28` subnet (14 usable addresses), supporting up to 4,096 projects from the pool.

**Caveats:**
- Some P2P and VPN applications ignore or filter link-local interfaces. Test your specific VPN client.
- `mtu`: Set to `9000` for jumbo frames if your switch/NIC supports it. Must match the physical network MTU — mismatches cause silent packet fragmentation. Default `1500` is safe for most environments.

---

## Registry Mirrors

A local registry mirror reduces Docker Hub rate limits (100 pulls/6h for unauthenticated, 200/6h for free accounts) and enables air-gapped hosts to pull images.

```json
{
  "registry-mirrors": [
    "https://mirror.example.internal"
  ]
}
```

The mirror must implement the Docker Registry HTTP API V2. Common options: [Harbor](https://goharbor.io/), [Nexus Repository](https://www.sonatype.com/products/nexus-repository), or a pull-through cache in AWS ECR.

---

## User Namespace Remapping (userns-remap)

User namespace remapping is a kernel-level feature that maps UID 0 inside the container to an unprivileged UID on the host. Even if a process escapes the container, it runs as an unprivileged user on the host.

```json
{
  "userns-remap": "default"
}
```

`"default"` creates a `dockremap` user and configures subordinate UID/GID ranges automatically.

**Trade-offs:**

| Concern | Detail |
|---|---|
| Volume permissions | Host-mounted volumes need ownership adjusted to the remapped UID (e.g., `chown 100000:100000 /host/path`) |
| Image compatibility | Some images (especially those using `--privileged` or specific UIDs) break with remapping enabled |
| `--privileged` incompatible | Cannot combine `userns-remap` with `--privileged` containers |
| Performance | Slight overhead from UID translation in the kernel |

**Recommendation:** For most self-hosted setups, `USER` + `no-new-privileges=true` in the Dockerfile/Compose provides adequate isolation without the compatibility headaches of `userns-remap`. Reserve `userns-remap` for high-security environments running untrusted images.

---

## Complete Example

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "data-root": "/opt/docker",
  "bip": "169.254.1.1/24",
  "fixed-cidr": "169.254.1.0/24",
  "default-address-pools": [
    {
      "base": "169.254.0.0/16",
      "size": 28
    }
  ],
  "mtu": 1500,
  "registry-mirrors": []
}
```
