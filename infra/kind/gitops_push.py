"""Push the chart and the Argo CD apps to the in-cluster git server (todo 6.5.5).

Copies ops/helm/p2-recommender and ops/argocd from the working tree into a deploy repo outside
the project, writes the image tag into ops/argocd/kind/release.yaml, commits, and hands the
commits to the git server. Argo CD picks them up within 30 s.

The deploy repo is the source of truth for what kind runs; the server's copy is disposable (an
emptyDir), so its main branch is force-updated. Nothing here touches the project's own history.

    uv run python infra/kind/gitops_push.py --tag 56b28de
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

SYNCED_PATHS: tuple[str, ...] = ("ops/helm/p2-recommender", "ops/argocd")
RELEASE_FILE = "ops/argocd/kind/release.yaml"
DEFAULT_DEPLOY_REPO = Path(tempfile.gettempdir()) / "p2-gitops-kind"
SERVER_REPO = "/srv/git/p2.git"


def _git(repo: Path, *args: str) -> str:
    command = ["git", "-C", str(repo), "-c", "user.name=p2 kind gitops"]
    command += ["-c", "user.email=gitops@localhost", *args]
    return subprocess.run(command, capture_output=True, check=True, encoding="utf-8").stdout


def build(project: Path, deploy: Path, tag: str) -> bool:
    """Mirror the synced paths into the deploy repo and commit; False when nothing changed."""
    if not tag:
        raise ValueError("an image tag is required")
    if not (deploy / ".git").is_dir():
        deploy.mkdir(parents=True, exist_ok=True)
        _git(deploy, "init", "--quiet", "--initial-branch=main")
    for rel in SYNCED_PATHS:
        shutil.rmtree(deploy / rel, ignore_errors=True)
        shutil.copytree(project / rel, deploy / rel)
    release = deploy / RELEASE_FILE
    release.write_text(
        f'# Written by infra/kind/gitops_push.py\nimage:\n  tag: "{tag}"\n', encoding="utf-8"
    )
    _git(deploy, "add", "--all")
    if not _git(deploy, "status", "--porcelain").strip():
        return False
    _git(deploy, "commit", "--quiet", "-m", f"deploy {tag}")
    return True


def push(deploy: Path, context: str) -> None:
    """Hand the deploy repo's main branch to the git server as a bundle.

    A `git push` through kubectl port-forward stalls as soon as the pack starts flowing (seen on
    Windows, with both the WebSocket and SPDY transports), while the same push from inside the
    pod works. So the commits travel as a file over `kubectl exec` stdin, and the server fetches
    them from it: the same history, without git's two-way protocol on the tunnel.
    """
    kubectl = ["kubectl", "--context", context, "-n", "argocd"]
    pod = subprocess.run(
        [*kubectl, "get", "pods", "-l", "app.kubernetes.io/name=git-server"]
        + ["-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "p2.bundle"
        _git(deploy, "bundle", "create", "--quiet", str(bundle), "main")
        upload = [*kubectl, "exec", "-i", pod, "-c", "git-daemon", "--"]
        subprocess.run(
            [*upload, "sh", "-c", "cat > /tmp/p2.bundle"], input=bundle.read_bytes(), check=True
        )
    fetch = ["git", "-C", SERVER_REPO, "fetch", "--quiet", "/tmp/p2.bundle", "+main:main"]
    subprocess.run([*kubectl, "exec", pod, "-c", "git-daemon", "--", *fetch], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--tag", required=True, help="the image tag to deploy (see image_tag.py)")
    parser.add_argument("--context", default="kind-p2")
    parser.add_argument("--deploy-repo", type=Path, default=DEFAULT_DEPLOY_REPO)
    args = parser.parse_args(argv)
    if not args.context.startswith("kind-"):
        parser.error(f"refusing context {args.context!r}: this script is for kind clusters only")

    changed = build(Path.cwd(), args.deploy_repo, args.tag)
    head = _git(args.deploy_repo, "log", "-1", "--format=%h %s").strip()
    print(
        f"deploy repo {args.deploy_repo}: {'new commit' if changed else 'no changes'}, HEAD {head}"
    )
    push(args.deploy_repo, args.context)
    print("delivered to git://git-server.argocd.svc.cluster.local/p2.git (main)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
