# Deployment Automation

End-to-end deployment script and GitHub Actions workflow for Kubernetes rollouts.

---

## Deployment Script (Bun + Commander)

The script follows this sequence:
1. Parse CLI args → verify cluster connectivity (fail fast before building)
2. Build Docker image → push to registry
3. Fetch live Deployment YAML → patch image + version annotation → apply
4. Watch rollout status with timeout → auto-rollback on failure

### Step 1: CLI Arguments + Cluster Check

```typescript
// 23.02.rollout.ts
import { $ } from "bun";
import { program, Option } from "commander";
import { parseDocument } from "yaml";

program
  .addOption(new Option("--trigger <value>").choices(["local", "gha"]))
  .addOption(new Option("--verbose").default(false))
  .addOption(new Option("--version <value>").default("0.0.1"))
  .addOption(new Option("--build <value>"))
  .addOption(new Option("--override-dockerfilePath <value>"))
  .addOption(new Option("--override-buildContext <value>"));

program.parse();
const opts = program.opts();

// Fail fast: verify cluster connectivity before building the image
const clusterCheck = await $`kubectl cluster-info`.nothrow();
if (clusterCheck.exitCode !== 0) {
  console.error("Cluster unreachable — check KUBECONFIG");
  process.exit(1);
}
```

**`--trigger`** — `local` or `gha`; controls cache backend and other CI-specific behavior  
**`--verbose`** — disables build cache, enables `--progress=plain` for detailed logs  
**`--version` + `--build`** — combined into `0.0.4b001` style tags  

### Step 2: Build and Push

```typescript
let versionTag = opts.version;
if (opts.build) versionTag = `${versionTag}b${opts.build}`;
const fullTag = `rg.fr-par.scw.cloud/my-org/web-app:${versionTag}`;

const DockerfilePath = opts.overrideDockerfilePath ?? "./Dockerfile";
const buildContext = opts.overrideBuildContext ?? ".";
const buildArgs = [
  `--tag=${fullTag}`,
  "--platform=linux/amd64",
  "--output=type=docker",    // send to local daemon; use type=registry to push directly
  `--file=${DockerfilePath}`,
  buildContext,
];

if (opts.verbose) buildArgs.push("--no-cache", "--progress=plain");
if (opts.trigger === "gha" && !opts.verbose) {
  buildArgs.push("--cache-from=type=gha");
  buildArgs.push("--cache-to=type=gha,mode=max");
}

const buildResult = await $`docker buildx build ${buildArgs}`.nothrow();
if (buildResult.exitCode !== 0) {
  console.error("Image build failed — check Dockerfile and build context");
  process.exit(1);
}
const pushResult = await $`docker image push ${fullTag}`.nothrow();
if (pushResult.exitCode !== 0) {
  console.error("Image push failed — check registry credentials and network");
  process.exit(1);
}
```

**Use `docker buildx build`**, not `docker build` — aliases pass different arguments to the builder and can yield unexpected results in CI.

### Step 3: Patch Deployment and Apply

```typescript
await $`kubectl config set-context --current --namespace=${
  process.env.DEFAULT_NAMESPACE ?? "default"
}`;

// Capture to variable — file redirect would create an empty file on error
const getResult = await $`kubectl get deployment/my-app -o yaml`.nothrow();
if (getResult.exitCode !== 0) {
  console.error("Failed to fetch Deployment — check namespace and name");
  process.exit(1);
}

const doc = parseDocument(getResult.stdout.toString());

// Look up container and env var by name — never by index (order may change)
const containers = doc.getIn(["spec", "template", "spec", "containers"]) as any[];
const containerIdx = containers.findIndex((c: any) => c.get("name") === "my-app");
if (containerIdx === -1) throw new Error("Container 'my-app' not found in Deployment");
const envVars = doc.getIn(["spec", "template", "spec", "containers", containerIdx, "env"]) as any[];
const envIdx = envVars?.findIndex((e: any) => e.get("name") === "APP_VERSION") ?? -1;

// Update image tag
doc.setIn(["spec", "template", "spec", "containers", containerIdx, "image"], fullTag);
// Update version env var (for logs/metrics tracing)
if (envIdx !== -1) {
  doc.setIn(["spec", "template", "spec", "containers", containerIdx, "env", envIdx, "value"], versionTag);
}
// Update change-cause annotation (visible in rollout history)
doc.setIn(["metadata", "annotations", "kubernetes.io/change-cause"], versionTag);
// Remove resourceVersion to avoid conflicts with concurrent updates
doc.deleteIn(["metadata", "resourceVersion"]);

// Write to a uniquely named temp file to avoid conflicts with concurrent runs
const deployFile = `deployment-${versionTag}-${Date.now()}.yaml`;
await Bun.write(deployFile, doc.toString());
try {
  await $`kubectl apply -f ${deployFile}`;
} finally {
  await Bun.file(deployFile).delete?.();  // clean up regardless of apply result
}
```

**Why delete `resourceVersion`:** This field is the cluster's optimistic concurrency token. Keeping it causes `apply` to fail if the resource was modified between read and write (e.g., by an autoscaler). Deleting it makes the apply unconditional — acceptable for single-writer CI pipelines.

**Alternative:** Keep `resourceVersion` to detect concurrent modifications and fail explicitly, then retry the read-patch-apply loop. Required if GitOps (ArgoCD, Flux) or HPA is active — unconditional apply can cause a reconciliation fight.

### Step 4: Watch Rollout + Auto-Rollback

```typescript
const rolloutStatusArgs = ["--timeout=300s", "--watch", "deployment/my-app"];
const { exitCode } = await $`kubectl rollout status ${rolloutStatusArgs}`.nothrow();
if (exitCode !== 0) {
  console.error("Rollout failed or timed out — rolling back");
  // Guard: check revision count before attempting undo (fails on first-ever deploy)
  const historyResult = await $`kubectl rollout history deployment/my-app`.nothrow();
  const revisionCount = (historyResult.stdout.toString().match(/^\d+/gm) ?? []).length;
  if (revisionCount <= 1) {
    console.error("No previous revision to roll back to — manual intervention required");
    process.exit(1);
  }
  const undoResult = await $`kubectl rollout undo deployment/my-app`.nothrow();
  if (undoResult.exitCode !== 0) {
    console.error("Rollback also failed — cluster may be in an unknown state");
  }
  process.exit(1);
}
```

**Timeout vs failure:** `kubectl rollout status --timeout` returns exit code 1 for both a genuine rollout failure *and* a timeout (rollout still in progress). Rolling back a timed-out-but-still-progressing rollout is destructive. Set `progressDeadlineSeconds` in the Deployment spec to distinguish the two — a `ProgressDeadlineExceeded` condition indicates the rollout is truly stuck, not just slow.

### Running Locally

```bash
export KUBECONFIG=$HOME/clusters/mycluster.yaml
export DEFAULT_NAMESPACE=production

bun run rollout.ts \
  --verbose \
  --version 0.0.4 \
  --build 001 \
  --override-dockerfilePath ./Dockerfile \
  --override-buildContext ./app
```

---

## GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: 🚀 Deploy Web App

on:
  workflow_dispatch:
    inputs:
      verbose:
        type: boolean

jobs:
  build_and_deploy:
    runs-on: ubuntu-24.04
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install kubectl
        uses: azure/setup-kubectl@v4
        with:
          version: "v1.31.6"    # pin to match cluster version

      - name: Install Bun
        uses: oven-sh/setup-bun@v2
        with:
          bun-version: 1.2.8

      - name: Set KubeConfig
        run: |
          mkdir -p $HOME/.kube/
          echo "${{ secrets.KUBE_CONFIG }}" | base64 -d > $HOME/.kube/config
          chmod 600 $HOME/.kube/config

      - uses: docker/setup-qemu-action@v3     # required for multi-arch builds
      - uses: docker/setup-buildx-action@v3
      - uses: crazy-max/ghaction-github-runtime@v3  # exposes GHA cache to buildx

      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: rg.fr-par.scw.cloud/my-org
          username: nologin
          password: ${{ secrets.REGISTRY_PASSWORD }}

      - name: Deploy
        # Assign inputs to env vars first — never interpolate github.event.inputs.*
        # directly into run: scripts (expression injection risk via REST API callers)
        run: |
          VERBOSE_FLAG=""
          if [ "$VERBOSE_INPUT" = "true" ]; then VERBOSE_FLAG="--verbose"; fi
          bun run rollout.ts \
            --trigger gha \
            $VERBOSE_FLAG \
            --version "$RUN_NUMBER"
        env:
          VERBOSE_INPUT: ${{ github.event.inputs.verbose }}
          RUN_NUMBER: ${{ github.run_number }}
          DEFAULT_NAMESPACE: production
```

**Secrets required:**
- `KUBE_CONFIG` — base64-encoded kubeconfig (`cat ~/.kube/config | base64`)
- `REGISTRY_PASSWORD` — container registry password/token

**Why `workflow_dispatch`:** Manual trigger gives control over when deployments happen. Add `push` trigger with branch/path filters for automatic deploys on merge to main.

**Why `crazy-max/ghaction-github-runtime`:** Exposes the GHA cache API to Docker Buildx, enabling `--cache-from=type=gha` and `--cache-to=type=gha,mode=max` for fast layer caching between runs.

**Action version pinning:** The workflow above uses mutable version tags (e.g., `@v4`). For production pipelines, pin to full commit SHAs and use Dependabot to manage updates:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
```

---

## Enhancements to Consider

- **Read version from source** — parse `package.json` or `pyproject.toml` instead of passing `--version`
- **Vulnerability scanning** — run `trivy image --exit-code 1 --severity HIGH,CRITICAL ${fullTag}` between build and push
- **Richer change-cause** — include git commit hash, branch, and changelog entry
- **Pre/post-deploy tests** — run smoke tests before and after rollout
- **Notifications** — Slack/email on success or failure
- **Observability** — emit OpenTelemetry spans for each step to track build/push/rollout duration over time
