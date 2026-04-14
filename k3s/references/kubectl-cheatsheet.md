# kubectl Quick Reference

## Getting Resources

```bash
# Generic pattern: kubectl get <resource> [name] [flags]
kubectl get pods
kubectl get pod my-pod                     # specific resource
kubectl get pods,services                  # multiple resource types
kubectl get all                            # pods, services, deployments, replicasets
kubectl get all -A                         # across all namespaces

# Output formats
kubectl get pods -o wide                   # extra columns (node, IP)
kubectl get pods -o yaml                   # full YAML spec
kubectl get pods -o json                   # full JSON
kubectl get pods -o jsonpath='{.items[*].metadata.name}'  # extract fields
kubectl get nodes --show-labels            # include labels

# Filtering
kubectl get pods -l app=web                # label selector
kubectl get pods --field-selector status.phase=Running
```

## Namespace Flags

```bash
kubectl get pods                           # current namespace (from context)
kubectl get pods -n kube-system            # specific namespace (-n or --namespace)
kubectl get pods -A                        # all namespaces (--all-namespaces)
kubectl get pods --all-namespaces          # same as -A

# Switch default namespace for current context
kubectl config set-context --current --namespace=production
kubectl config view --minify | grep namespace:   # confirm
```

## Describing and Inspecting

```bash
kubectl describe pod <name>                # detailed state, events, conditions
kubectl describe node <name>              # node capacity, conditions, pods
kubectl describe deployment <name>        # rollout status, events

# Events are often more useful than describe for troubleshooting
kubectl get events -A -w                  # watch all events (run in separate terminal)
kubectl get events -n production --sort-by='.lastTimestamp'
```

## Logs

```bash
kubectl logs <pod>                         # pod logs (last container if multiple)
kubectl logs <pod> -c <container>          # specific container
kubectl logs <pod> -f                      # stream (follow)
kubectl logs <pod> --previous             # logs from previous (crashed) container
kubectl logs <pod> --tail=100             # last 100 lines
kubectl logs <pod> --since=1h             # logs from last hour
kubectl logs -l app=web -f                # stream logs from all pods matching label
```

## Exec and Port-Forward

```bash
kubectl exec -it <pod> -- /bin/sh          # interactive shell
kubectl exec -it <pod> -c <container> -- bash  # specific container
kubectl exec <pod> -- env                  # run a command non-interactively

kubectl port-forward pod/<name> 8080:80    # local:pod
kubectl port-forward svc/<name> 8080:80    # forward to service
kubectl port-forward deployment/<name> 8080:80
```

## Apply, Create, Delete

```bash
kubectl apply -f manifest.yaml             # create or update (idempotent)
kubectl apply -f ./manifests/              # apply all files in directory
kubectl apply -f https://example.com/manifest.yaml

kubectl delete -f manifest.yaml            # delete resources from file
kubectl delete pod <name>                  # delete specific resource
kubectl delete pod <name> --grace-period=0 --force  # force delete (use sparingly)

# Create resources imperatively (useful for one-offs)
kubectl create namespace staging
kubectl create configmap app-config --from-literal=ENV=production
kubectl create secret generic db-creds --from-literal=password=secret
```

## Scaling and Rollouts

```bash
kubectl scale deployment <name> --replicas=3
kubectl rollout status deployment/<name>   # watch rollout progress
kubectl rollout history deployment/<name>  # revision history
kubectl rollout undo deployment/<name>     # rollback to previous revision
kubectl rollout undo deployment/<name> --to-revision=2
kubectl rollout restart deployment/<name>  # rolling restart (triggers new pods)
```

## Context and Config

```bash
kubectl config get-contexts               # list all contexts
kubectl config current-context            # show active context
kubectl config use-context <name>         # switch context
kubectl config view                       # show full kubeconfig
kubectl config view --minify              # show only active context config

# Update server address in kubeconfig
kubectl config set-cluster default --server=https://NEW_IP:6443
```

## Resource Abbreviations

| Full name | Short | Namespaced |
|---|---|---|
| pods | po | yes |
| services | svc | yes |
| deployments | deploy | yes |
| replicasets | rs | yes |
| statefulsets | sts | yes |
| configmaps | cm | yes |
| secrets | - | yes |
| namespaces | ns | no |
| nodes | no | no |
| persistentvolumes | pv | no |
| persistentvolumeclaims | pvc | yes |
| ingresses | ing | yes |

## Useful One-Liners

```bash
# Watch pod restarts in real time
kubectl get pods -A -w | grep -v Running

# Get all images running in the cluster
kubectl get pods -A -o jsonpath='{range .items[*]}{.spec.containers[*].image}{"\n"}{end}' | sort -u

# Find which node a pod is on
kubectl get pod <name> -o wide

# Get resource requests/limits for all pods
kubectl get pods -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,CPU_REQ:.spec.containers[*].resources.requests.cpu,MEM_REQ:.spec.containers[*].resources.requests.memory'

# Drain a node for maintenance
kubectl drain <node> --ignore-daemonsets --delete-emptydir-data

# Uncordon a node after maintenance
kubectl uncordon <node>

# Check API resources (useful for finding CRDs)
kubectl api-resources
kubectl api-resources --namespaced=false    # cluster-scoped only
```

## Plugins (via Krew)

Install Krew: https://krew.sigs.k8s.io/docs/user-guide/setup/install/

```bash
kubectl krew install stern    # tail logs from multiple pods simultaneously
kubectl krew install ctx      # fast context switching
kubectl krew install ns       # fast namespace switching

# Usage
kubectl stern web-app         # stream logs from all pods matching "web-app"
kubectl ctx production        # switch to production context
kubectl ns kube-system        # switch to kube-system namespace
```
