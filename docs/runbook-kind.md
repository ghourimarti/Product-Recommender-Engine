# Runbook: P2 on kind (local Kubernetes)

kind runs Kubernetes nodes as Docker containers on one machine. The API server, scheduler,
kubelets, NetworkPolicies, HPAs and operators behave as on a real cluster, so the chart, the
platform add-ons and the failure drills can be practised for $0. It is not production: one
machine, no real load balancer, no cloud disks, no HA, and performance numbers measure the laptop.
The same chart deploys to DOKS and EKS with a different values file (Phases 7 and 8).

## What you get

| Layer | On kind |
|---|---|
| Cluster | 1 control plane + 2 workers, `kindest/node` v1.36.1 pinned by digest (`infra/kind/kind-config.yaml`) |
| Front door | Envoy Gateway 1.9.2 (Gateway API): `http://app.localhost` and `https://app.localhost` (local CA from cert-manager) |
| App | api ×2 (HPA 2–4), web ×2, Qdrant + Redis (StatefulSets on PVCs), DynamoDB-local; Pod Security `restricted` |
| Monitoring | kube-prometheus-stack: Prometheus, Alertmanager (to a local log sink), Grafana with the P2 dashboard |
| GitOps | Argo CD 3.5 (app-of-apps) syncing from an in-cluster git server, auto-sync + self-heal |

Pinned versions live in `infra/kind/addons/versions.env`.

## Prerequisites

- Docker Desktop with **8 GB** for its VM. The compose stack and kind don't fit together: `make down` first.
- kind 0.32, kubectl 1.36, **Helm 4** (4.1.4), uv, k6 (drills only).
- A filled-in `.env` (OpenAI, Clerk; SerpApi optional). Only an allow-list of keys reaches the
  cluster (`infra/kind/kind_secret.py`); values are never printed.

Windows notes:
- GNU make run from PowerShell executes recipes in **cmd.exe**. The kind targets are written to
  work there. Older targets (`wait-api`, `urls`, `upv`) need Git Bash.
- Python, .NET and k6 don't resolve `*.localhost`; curl.exe and browsers do. Scripts connect to
  `127.0.0.1` and send `Host: app.localhost`.
- curl.exe (Schannel) with the local CA: `curl.exe --cacert p2-local-ca.crt --ssl-revoke-best-effort https://app.localhost/`.

## From zero

```bash
make kind-all      # cluster → add-ons → images → Secret → Helm install → smoke test
make kind-argocd   # Argo CD + git server; hands the release from Helm to GitOps (no downtime)
```

`kind-all` is `kind-up kind-addons kind-images kind-secret kind-deploy kind-smoke`. Each step
re-runs safely on its own. Measured on 2026-10-07 from no cluster (app images already built):
`make kind-all` 595 s, then `make kind-argocd` 97 s, so about 11.5 minutes to a GitOps-managed app.
Most of it is pulling images onto the new nodes.

Then open http://app.localhost and sign in with Clerk.

## Day to day

| Task | Command |
|---|---|
| Deploy a code change (GitOps) | `make kind-images kind-gitops` (build, load, commit the new tag; Argo CD rolls it out) |
| Smoke test | `make kind-smoke` (`PROFILE=devauth` when the API runs dev auth; `AGGREGATE=1` spends one SerpApi search) |
| Switch auth | `make kind-secret PROFILE=clerk` (browser) or `PROFILE=devauth` (minted HS256 tokens, for k6); restarts the api |
| Alert rules | `make alerts-test` (promtool, via Docker) |
| Delete everything | `make kind-down` |

After `make kind-argocd`, don't use `make kind-deploy`: Helm and Argo CD would fight over the
same objects. Image tags are the commit SHA, plus a content hash when the tree is dirty
(`infra/kind/image_tag.py`), so every rebuild rolls out.

UIs (kubectl port-forward):

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80          # read-only anonymous; admin password: Secret monitoring/kube-prometheus-stack-grafana
kubectl -n monitoring port-forward svc/kube-prometheus-stack-prometheus 9090:9090
kubectl -n monitoring port-forward svc/kube-prometheus-stack-alertmanager 9093:9093
kubectl -n argocd port-forward svc/argocd-server 8080:80                             # read-only anonymous; admin password: Secret argocd/argocd-initial-admin-secret
kubectl -n monitoring logs deploy/alert-sink                                          # every alert Alertmanager sent
```

## Drills (2026-10-07)

Load: `ops/load/k6-drill.js`, a constant rate through the Gateway that fails on any non-200
(`MODE=cold` makes every query miss the caches). Drills that change the cluster by hand need Argo
CD's auto-sync paused (remove `spec.syncPolicy.automated` from the `root` app, then the `p2` app);
re-applying `ops/argocd/kind/root.yaml` restores it, and self-heal puts git's state back.

| Drill | Result |
|---|---|
| Rollout of a new tag via git, 10 req/s | 1800/1800 OK; applied 6 s after the commit, rolled in 10 s |
| Broken tag, then a git rollback | 0 errors (old pods kept serving); the rollback applied itself once the stuck sync timed out |
| Delete an api pod | 901/901 OK; replaced in 31 s |
| Stop a worker node for 6 min | 0.27% errors, all in the first ~50 s; 43% before the gateway fixes below |
| Qdrant pod deleted / Qdrant down 60 s | back in 4.5 s with its data; 297/297 OK via the popularity fallback |
| Redis down 60 s | 301/301 OK, median 0.26 s (fails fast; rate limits fail open meanwhile) |
| HPA at 200 req/s | 2 → 4 replicas, back to 2 after the 5-min window; 48,001/48,001 OK |
| api memory limit 128Mi | `OOMKilled` (exit 137); old pods kept serving; self-heal restored the limit |
| NetworkPolicies | 10/10 paths as designed (web can't reach Redis, Qdrant or the api directly) |
| ApiDown alert | scaled to 0 → fired after its 2 min → Alertmanager → sink; resolved after restore |

## Things that bit, and the fixes

| Symptom | Cause | Fix (in this repo) |
|---|---|---|
| web never Ready; Next.js on port 3000 | the Service `web` injects `WEB_PORT=tcp://…` (service links) | `enableServiceLinks: false` everywhere; `WEB_PORT` set from `web.port` |
| first request on a new pod takes 20+ s | BM25 model and tokenizer downloaded at first use | baked into the api image; `HF_HUB_OFFLINE=1` |
| `ApiDown` never fires with 0 replicas | no targets means no `up` series | `absent(up{job="p2-api"} == 1)`; promtool tests |
| Grafana pins every CPU core | Grafana 13.2.3 (chart default) busy-loops on SQLite leases | Grafana 12.4.12 + a CPU limit |
| Argo CD OutOfSync after every sync | client-side diff of server-defaulted fields | `controller.diff.server.side: "true"` |
| a rollback commit never applies | a broken release's sync waits forever for health | `controller.sync.timeout.seconds: "180"` |
| a seed Job on every Argo CD sync blanks the catalog | Argo CD runs Helm post-install hooks on each sync | `retrieval.index --skip-if-current` (catalog fingerprint) |
| half the traffic fails while a node is down | one Envoy Gateway controller, on the dead node | controller ×2 (hard spread), proxies ×2 + PDB, BackendTrafficPolicy (retry only failed connections, eject failing pods) |
| `git push` to the in-cluster server hangs | git's push protocol stalls over kubectl port-forward on Windows | the push script ships a git bundle over `kubectl exec` |

Still open: after a node failure the evicted pods stay on the surviving node (needs a descheduler
or a restart); in-cluster traffic is plain HTTP; rate limits fail open while Redis is down.

## Memory (8 GB Docker VM)

Empty cluster ~1.3 GB · + metrics-server, Envoy Gateway, cert-manager ~0.9 GB · + app ~2 GB ·
+ kube-prometheus-stack ~1.3 GB · + Argo CD ~0.5 GB ≈ 6 GB in all. Every kind node reports the
whole VM as allocatable, so requests don't protect you here: the api HPA is capped at 4.
