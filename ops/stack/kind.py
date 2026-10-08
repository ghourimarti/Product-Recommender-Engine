"""kind lifecycle behind make up / down: it only ever touches the P2 cluster.

    uv run python -m ops.stack.kind plan --enabled 1   # prints create | restart | running | skip
    uv run python -m ops.stack.kind restart            # start the stopped nodes, wait for the app
    uv run python -m ops.stack.kind status             # nodes, pods, and which image is deployed
    uv run python -m ops.stack.kind stop               # stop the nodes; the cluster and data stay
    uv run python -m ops.stack.kind monitoring         # true/false: Prometheus Operator CRDs exist

`plan` decides what `make kind-start` does, and says why on stderr (stdout is the answer make
reads). It never creates or restarts a cluster without enough free memory: kind nodes report the
whole Docker VM as allocatable, so an overfull VM doesn't fail fast, it swaps until everything
on it, compose included, slows to a crawl.

Other kind clusters on the same Docker (other projects) are named in the advice, never touched.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence

from infra.kind.image_tag import image_tag
from ops.stack.catalog import ROOT, KindState, kind_clusters, run

# alpine:3.22 is also the git server's base image (infra/kind/gitops), so it is usually cached.
MEMINFO_IMAGE = "alpine:3.22"
CRD = "servicemonitors.monitoring.coreos.com"


def say(message: str) -> None:
    print(f"  kind: {message}", file=sys.stderr, flush=True)


def vm_available_mb() -> int | None:
    """MemAvailable of the Docker VM: containers share its kernel, so they see its meminfo."""
    res = run(
        ["docker", "run", "--rm", "--network", "none", MEMINFO_IMAGE, "cat", "/proc/meminfo"], 120
    )
    if res is None or res.returncode != 0:
        return None
    match = re.search(r"^MemAvailable:\s+(\d+) kB", res.stdout, re.MULTILINE)
    return int(match.group(1)) // 1024 if match else None


def container_memory_mb(names: Sequence[str]) -> int:
    if not names:
        return 0
    res = run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", *names], 60)
    if res is None or res.returncode != 0:
        return 0
    units = {"KiB": 1 / 1024, "MiB": 1.0, "GiB": 1024.0}
    total = 0.0
    for line in res.stdout.splitlines():
        match = re.match(r"([\d.]+)(KiB|MiB|GiB)", line.strip())
        if match:
            total += float(match.group(1)) * units[match.group(2)]
    return int(total)


def memory_advice(cluster: str, available: int, need: int) -> list[str]:
    lines = [
        f"SKIPPED: the Docker VM has {available / 1024:.1f} GB available; the lean P2 cluster",
        f"needs ~{need / 1024:.1f} GB on top of what is already running.",
    ]
    others = {name: s for name, s in kind_clusters().items() if name != cluster and s.running}
    for name, state in sorted(others.items()):
        nodes = sorted(state.nodes)
        used = container_memory_mb(nodes) / 1024
        lines.append(
            f"  another kind cluster is running: '{name}' ({len(nodes)} nodes, {used:.1f} GB)"
        )
        lines.append(f"    stop it (kept, restartable):  docker stop {' '.join(nodes)}")
    lines.append("  or stop the compose stack first (make down), or skip kind: make up KIND=0")
    return lines


def plan(cluster: str, enabled: bool, need_gb: float) -> str:
    if not enabled:
        say("skipped (KIND=0)")
        return "skip"
    missing = [tool for tool in ("kind", "kubectl", "helm") if shutil.which(tool) is None]
    if missing:
        say(f"SKIPPED: {', '.join(missing)} not installed (see docs/runbook-kind.md)")
        return "skip"
    state = kind_clusters().get(cluster, KindState(cluster))
    if state.running:
        say(f"cluster '{cluster}' is already running")
        return "running"
    available = vm_available_mb()
    need = int(need_gb * 1024)
    if available is None:
        say("could not read the Docker VM's free memory; going ahead")
    elif available < need:
        for line in memory_advice(cluster, available, need):
            say(line)
        return "skip"
    else:
        say(f"Docker VM has {available / 1024:.1f} GB available (need ~{need_gb:.1f} GB)")
    if state.exists:
        say(f"cluster '{cluster}' is {state.label}: restarting its nodes")
        return "restart"
    say(f"no cluster '{cluster}': creating the lean one (no in-cluster monitoring), ~10 min")
    return "create"


def kubectl(context: str, *args: str, timeout: float = 400) -> subprocess.CompletedProcess[str]:
    res = run(["kubectl", "--context", context, *args], timeout)
    if res is None:
        raise SystemExit(f"kubectl {' '.join(args)}: kubectl missing or timed out")
    return res


def must(res: subprocess.CompletedProcess[str], what: str) -> None:
    if res.returncode != 0:
        say(f"FAILED: {what}\n{res.stdout}{res.stderr}")
        raise SystemExit(1)


def until(deadline: float, what: str, context: str, *args: str) -> None:
    """Retry a kubectl command until it succeeds; fail loudly at the deadline."""
    while True:
        res = kubectl(context, *args, timeout=60)
        if res.returncode == 0:
            return
        if time.monotonic() > deadline:
            must(res, what)
        time.sleep(3)


def restart(cluster: str) -> int:
    state = kind_clusters().get(cluster, KindState(cluster))
    if not state.exists:
        say(f"no cluster '{cluster}' to restart (make kind-start creates it)")
        return 1
    stopped = sorted(node for node, s in state.nodes.items() if s != "running")
    if stopped:
        res = run(["docker", "start", *stopped], 120)
        if res is None or res.returncode != 0:
            say(f"FAILED to start {' '.join(stopped)}")
            return 1
        say(f"started {len(stopped)} node(s)")
    # The API server's host port can change across restarts; re-export so kubectl follows it.
    res = run(["kind", "export", "kubeconfig", "--name", cluster], 60)
    if res is None or res.returncode != 0:
        say("FAILED: kind export kubeconfig")
        return 1
    ctx = f"kind-{cluster}"
    say("waiting for the API server, nodes, gateway and app (up to ~5 min)")
    deadline = time.monotonic() + 300
    # A just-restarted API server answers before its RBAC caches load and briefly returns
    # Forbidden for everything: wait for /readyz, then retry each wait until the deadline.
    until(deadline, "API server ready", ctx, "get", "--raw=/readyz")
    until(
        deadline,
        "nodes Ready",
        ctx,
        "wait",
        "--for=condition=Ready",
        "nodes",
        "--all",
        "--timeout=20s",
    )
    for ns in ("envoy-gateway-system", "cert-manager", "p2"):
        until(
            deadline,
            f"deployments in {ns}",
            ctx,
            *("-n", ns, "wait", "--for=condition=Available", "deploy", "--all", "--timeout=20s"),
        )
    until(
        deadline,
        "p2 pods Ready",
        ctx,
        "-n",
        "p2",
        "wait",
        "--for=condition=Ready",
        "pod",
        "--all",
        "--timeout=20s",
    )
    say(f"cluster '{cluster}' is back")
    drift(cluster)
    return 0


def deployed_tag(cluster: str) -> str | None:
    res = run(
        [
            "kubectl",
            "--context",
            f"kind-{cluster}",
            "-n",
            "p2",
            "get",
            "deploy",
            "api",
            "-o",
            "jsonpath={.spec.template.spec.containers[0].image}",
        ],
        20,
    )
    if res is None or res.returncode != 0 or ":" not in res.stdout:
        return None
    return res.stdout.rsplit(":", 1)[1]


def drift(cluster: str) -> None:
    """Say so when the cluster runs an older build than the working tree: kind never rebuilds."""
    deployed = deployed_tag(cluster)
    if deployed is None:
        return
    current = image_tag(ROOT)
    if deployed == current:
        say(f"runs the current code (image tag {current})")
        return
    gitops = run(
        ["kubectl", "--context", f"kind-{cluster}", "-n", "argocd", "get", "application", "p2"], 20
    )
    ship = (
        "make kind-images kind-gitops"
        if gitops and gitops.returncode == 0
        else "make kind-redeploy"
    )
    say(f"runs image {deployed}; your working tree is {current}. Ship it: {ship}")


def status(cluster: str) -> int:
    state = kind_clusters().get(cluster, KindState(cluster))
    print(f"  kind cluster '{cluster}': {state.label}")
    for node, s in sorted(state.nodes.items()):
        print(f"    {node:<28} {s}")
    if not state.running:
        return 0
    ctx = f"kind-{cluster}"
    print(kubectl(ctx, "get", "nodes", "-o", "wide", timeout=30).stdout)
    print(kubectl(ctx, "-n", "p2", "get", "pods", "-o", "wide", timeout=30).stdout)
    drift(cluster)
    return 0


def stop(cluster: str) -> int:
    state = kind_clusters().get(cluster, KindState(cluster))
    running = sorted(node for node, s in state.nodes.items() if s == "running")
    if not running:
        say(f"cluster '{cluster}' is {state.label}: nothing to stop")
        return 0
    res = run(["docker", "stop", *running], 180)
    if res is None or res.returncode != 0:
        say(f"FAILED to stop {' '.join(running)}")
        return 1
    say(f"stopped {len(running)} node(s) of '{cluster}'; cluster kept (make downv deletes it)")
    return 0


def delete(cluster: str) -> int:
    if cluster not in kind_clusters():
        say(f"no cluster '{cluster}': nothing to delete")
        return 0
    res = run(["kind", "delete", "cluster", "--name", cluster], 300)
    if res is None or res.returncode != 0:
        say(f"FAILED: kind delete cluster --name {cluster}")
        return 1
    say(f"deleted cluster '{cluster}' (nodes, volumes, everything in it)")
    return 0


def monitoring(cluster: str) -> str:
    res = run(["kubectl", "--context", f"kind-{cluster}", "get", "crd", CRD], 20)
    return "true" if res is not None and res.returncode == 0 else "false"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "command", choices=["plan", "restart", "drift", "status", "stop", "delete", "monitoring"]
    )
    parser.add_argument("--cluster", default="p2")
    parser.add_argument("--enabled", default="1", help="KIND from make: 0 skips kind")
    parser.add_argument("--need-gb", type=float, default=5.0, help="free VM memory a start needs")
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(plan(args.cluster, args.enabled == "1", args.need_gb))
        return 0
    if args.command == "monitoring":
        print(monitoring(args.cluster))
        return 0
    if args.command == "drift":
        drift(args.cluster)
        return 0
    if args.enabled != "1" and args.command in ("stop", "delete"):
        say("skipped (KIND=0)")
        return 0
    commands = {"restart": restart, "status": status, "stop": stop, "delete": delete}
    return commands[args.command](args.cluster)


if __name__ == "__main__":
    raise SystemExit(main())
