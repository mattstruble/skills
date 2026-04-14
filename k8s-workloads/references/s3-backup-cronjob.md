# S3 Database Backup via CronJob

Step-by-step guide for backing up a PostgreSQL database to S3-compatible object storage using Kopia, pg_dump, and a Kubernetes CronJob.

**Stack:** `ubuntu:24.04` image, Bun (TypeScript runtime), Kopia (backup tool), pg_dump (PostgreSQL client), S3-compatible storage.

**Strategy:** Scripts are passed via ConfigMap volume (not baked into the image), secrets via a Kubernetes Secret. This lets you update scripts without rebuilding an image.

---

## Step 1: Create a Kopia Repository

Install Kopia locally (`brew install kopia` on macOS), create an S3 bucket and IAM user with Object Storage access, then initialize the repository.

> **Security:** Pass credentials via environment variables, not CLI flags — CLI args are visible in `ps` output and shell history. Set `KOPIA_PASSWORD`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY` before running, then omit those flags. Also add `backup.env` to `.gitignore` and delete it after creating the Kubernetes Secret.

```bash
# Set credentials as env vars (not as CLI flags)
export KOPIA_PASSWORD=YOUR_REPO_PASSWORD
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY

kopia repository create s3 \
  --bucket=my-backup-bucket \
  --endpoint=s3.your-provider.com \
  --region=your-region
```

Verify storage compatibility:
```bash
kopia repository verify
```

Enable compression globally (zstd balances ratio and speed):
```bash
kopia policy set --global --compression=zstd
```

**Default retention policy** (adjust as needed): 3 annual, 24 monthly, 4 weekly, 7 daily, 48 hourly, 10 latest snapshots.

---

## Step 2: Installation Script

`install.sh` — runs inside the container to install pg_dump, Kopia, and Bun:

> **Supply chain note:** Kopia and PostgreSQL are installed from signed apt repositories. Bun uses `curl | bash` with a pinned version — no cryptographic verification. For production, bake the install script into a custom image (see "Improvements to Consider") to eliminate this risk and reduce Job startup time from ~60s to ~5s.

> **`apt upgrade` risk:** Running `apt upgrade -y` on every Job execution means a breaking upstream package change (e.g., a new Kopia release that changes CLI flags) will silently break all future backup Jobs. Monitor Job failures actively, or build a custom image to pin all package versions.

```bash
#!/bin/bash
set -e   # required for standalone execution (bash install.sh); sourced execution inherits set -e from the calling shell

echo "Update the package list"
apt update && apt upgrade -y

echo "Install requirements"
apt install -y curl gnupg2 unzip ca-certificates lsb-release

echo "Install kopia"
curl -s https://kopia.io/signing-key | gpg --dearmor -o /etc/apt/keyrings/kopia-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kopia-keyring.gpg] http://packages.kopia.io/apt/ stable main" \
  > /etc/apt/sources.list.d/kopia.list
apt update && apt install -y kopia
kopia --version

echo "Install pg_dump (PostgreSQL 17 client)"
install -d /usr/share/postgresql-common/pgdg
curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
  https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
  > /etc/apt/sources.list.d/pgdg.list'
apt update && apt install -y postgresql-client-17
pg_dump --version

echo "Install Bun"
curl -fsSL https://bun.sh/install | bash -s "bun-v1.2.6"
export PATH="$HOME/.bun/bin:$PATH"
bun -v
```

**Why `source install.sh` (not `bash install.sh`):** Sourcing runs in the current shell, so `PATH` changes (like Bun's install dir) persist for subsequent commands. `install.sh` also includes its own `set -e` so it's safe to run standalone (`bash install.sh`) during development.

---

## Step 3: Backup Script

`backup.ts` — TypeScript script using Bun's shell API:

```typescript
import { $ } from "bun";

// Guard: fail fast on missing required env vars
const required = [
  "POSTGRES_PASSWORD",
  "REPOSITORY_ACCESS_KEY",
  "REPOSITORY_SECRET_ACCESS_KEY",
  "REPOSITORY_PASSWORD",
];
for (const key of required) {
  if (!process.env[key]) throw new Error(`${key} is not set`);
}

// Step 1: Dump the database
// Remove any stale dump directory from a previous run before starting
await $`rm -rf postgres0_backup`;
const backupArgs = [
  "--host=postgres0-postgresql.db.svc.cluster.local",
  "--username=postgres",
  "--format=directory",   // enables parallel restore and granular recovery
  "--compress=none",      // don't compress — let Kopia deduplicate first
  "--jobs=4",             // parallel dump (creates more DB load)
  "--file=postgres0_backup",
  "--verbose",
];
await $`pg_dump postgres ${backupArgs}`.env({
  ...process.env,
  PGPASSWORD: process.env.POSTGRES_PASSWORD,  // pg_dump reads $PGPASSWORD
});
// Verify dump is complete before snapshotting — directory format produces toc.dat on success
const tocCheck = await $`test -f postgres0_backup/toc.dat`.nothrow();
if (tocCheck.exitCode !== 0) throw new Error("pg_dump did not produce toc.dat — dump may be incomplete");

// Step 2: Connect to Kopia repository
// Pass credentials via env vars, not CLI flags (CLI args visible in ps/proc)
await $`kopia repository connect s3 \
  --bucket=my-backup-bucket \
  --endpoint=s3.your-provider.com \
  --region=your-region \
  --override-username=root \
  --override-hostname=host0`.env({
  // stable snapshot key regardless of container user/Pod name
  ...process.env,
  KOPIA_PASSWORD: process.env.REPOSITORY_PASSWORD,
  AWS_ACCESS_KEY_ID: process.env.REPOSITORY_ACCESS_KEY,
  AWS_SECRET_ACCESS_KEY: process.env.REPOSITORY_SECRET_ACCESS_KEY,
});

// Step 3: Create snapshot
// Kopia's atomic commit: a failed snapshot create leaves NO partial snapshot in the
// repository — the manifest is only written on success. Safe to retry.
console.log("step - create snapshot");
const createSnapshotArgs = [
  "./postgres0_backup/",
  "--override-source=/backups/postgres0_backup/postgres",  // meaningful key in repo
  "--parallel=4",
];
await $`kopia snapshot create ${createSnapshotArgs}`;

// Step 4: Expire old snapshots and run maintenance
// Note: kopia maintenance run --full acquires an exclusive lock.
// If a previous Job crashed mid-maintenance, the lock may be stale.
// --force bypasses the lock — only safe when no other Kopia process is running.
// With concurrencyPolicy: Forbid, only one Job runs at a time, so --force is safe here.
console.log("step - cleanup");
// This path must exactly match --override-source used in snapshot create above
await $`kopia snapshot expire /backups/postgres0_backup/postgres/`;
await $`kopia maintenance set --owner=me`;
await $`kopia maintenance run --full --force`;
```

**Key decisions:**
- `--format=directory` + `--compress=none`: Kopia's deduplication works best on uncompressed, consistently-ordered data. Pre-compressing with pg_dump defeats deduplication.
- `--override-username` + `--override-hostname`: Snapshot keys include username and hostname. Override them to stable values so snapshots from different Pods/containers are grouped together in the repository.
- Credentials via env vars: CLI flags are visible in `/proc/<pid>/cmdline` and `ps aux`. Always pass secrets as environment variables.
- `backoffLimit: 1` means a failed Job retries once — the retry re-runs the entire script including a fresh `pg_dump`, doubling DB load during an already-stressed period. Set `backoffLimit: 0` if DB load is a concern and rely on the next scheduled run instead.

---

## Step 4: Create Kubernetes Resources

```bash
# Create the Secret from an env file
# backup.env contents:
# POSTGRES_PASSWORD=your-db-password
# REPOSITORY_ACCESS_KEY=your-s3-key
# REPOSITORY_SECRET_ACCESS_KEY=your-s3-secret
# REPOSITORY_PASSWORD=your-kopia-password

kubectl create secret generic backup \
  -n db \
  --from-env-file=backup.env

# Delete the env file after creating the Secret — don't leave credentials on disk
rm backup.env

# Create the ConfigMap with --append-hash so updates trigger new rollouts
kubectl create configmap backup \
  -n db \
  --append-hash \
  --from-file=install.sh=install.sh \
  --from-file=backup.ts=backup.ts
# → configmap/backup-f2t9f89856 created
```

> **`--append-hash` warning:** The hash changes every time you recreate the ConfigMap. If you forget to update the ConfigMap name in the CronJob manifest, the CronJob silently continues running the old scripts — no error is raised. Verify after updating: `kubectl get cronjob backup -n db -o jsonpath='{.spec.jobTemplate.spec.template.spec.volumes}'`

---

## Step 5: CronJob Manifest

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
  namespace: db
spec:
  schedule: "0 */4 * * *"       # every 4 hours
  concurrencyPolicy: Forbid      # never run two backups simultaneously
  failedJobsHistoryLimit: 10     # retain 10 failed Jobs for inspection
  successfulJobsHistoryLimit: 3
  jobTemplate:
    spec:
      backoffLimit: 1
      template:
        spec:
          restartPolicy: Never
          containers:
            - name: ubuntu
              image: ubuntu:24.04
              volumeMounts:
                - name: scripts
                  mountPath: /etc/scripts   # read-only ConfigMap mount
              envFrom:
                - secretRef:
                    name: backup            # all Secret keys become env vars
              command: ["/bin/bash", "-c"]
              args:
                - |
                  set -e
                  cd /tmp
                  cp -v /etc/scripts/* .
                  source install.sh
                  bun run backup.ts
          volumes:
            - name: scripts
              configMap:
                name: backup-f2t9f89856   # update hash when ConfigMap changes
```

**Why `set -e` first:** `set -e` must be the first line so failures in `cd` or `cp` (e.g., missing ConfigMap mount) abort immediately with a clear error rather than silently proceeding.

**Why `cd /tmp && cp scripts`:** ConfigMap mounts are read-only. Bun and shell scripts may need to write temporary files in their working directory. Copy to `/tmp` first.

---

## Step 6: Deploy and Test

```bash
kubectl apply -f cronjob.yaml

# Test immediately without waiting for schedule
kubectl create job --from=cronjob/backup backup-now -n db

# Watch the Job
kubectl get jobs -n db -w

# Check logs
kubectl logs -l job-name=backup-now -n db

# Verify snapshots in Kopia (from local machine)
export KOPIA_PASSWORD=YOUR_REPO_PASSWORD
export AWS_ACCESS_KEY_ID=YOUR_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_SECRET_KEY
kopia repository connect s3 \
  --bucket=my-backup-bucket \
  --endpoint=s3.your-provider.com \
  --region=your-region
kopia snapshot list
```

**Verify the backup is restorable** — download and restore to a test database at least once before relying on it in production.

---

## Improvements to Consider

- **Custom image** (recommended for production) — bake the install script into a Dockerfile to eliminate the install phase from every run (reduces Job duration from ~60s to ~5s, removes internet dependency, eliminates `curl | bash` supply chain risk).
- **Parameterize** database name, bucket, and endpoint via environment variables instead of hardcoding in the script.
- **Notifications** — add `kopia notification` or a webhook (Slack/Discord) on completion or failure.
- **Restore test Job** — a separate Job that downloads the latest snapshot and restores it to a scratch database to validate integrity.
- **Table-level granularity** — use `pg_dump --table` for critical tables with higher backup frequency.
