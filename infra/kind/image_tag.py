"""Print the tag for locally built images: the commit's short SHA, plus a content hash when dirty.

A tag must name exactly one build. Plain `<sha>-dirty` named every uncommitted state of the same
commit, so rebuilding after an edit produced a different image under an old tag, and Kubernetes
saw no change to roll out (the pod spec's image string was identical). The suffix hashes what the
images are built from, so every edit gets its own tag, and undoing it returns to the same tag.

    uv run python infra/kind/image_tag.py            # e.g. 56b28de, or 56b28de-dirty-3f9a1c2
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

# What the api and web images are built from (apps/api/Dockerfile, apps/web/Dockerfile).
IMAGE_INPUTS: tuple[str, ...] = ("apps", "packages", "data", "pyproject.toml", "uv.lock")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True, encoding="utf-8"
    )
    return result.stdout.strip()


def image_tag(repo: Path) -> str:
    sha = _git(repo, "rev-parse", "--short", "HEAD")
    if not _git(repo, "status", "--porcelain", "--untracked-files=all", "--", *IMAGE_INPUTS):
        return sha
    digest = hashlib.sha256()
    # Tracked changes against HEAD (staged or not), then untracked files by name and content.
    digest.update(_git(repo, "diff", "HEAD", "--binary", "--", *IMAGE_INPUTS).encode())
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "--", *IMAGE_INPUTS)
    for path in sorted(untracked.splitlines()):
        digest.update(path.encode())
        digest.update((repo / path).read_bytes())
    return f"{sha}-dirty-{digest.hexdigest()[:7]}"


if __name__ == "__main__":
    print(image_tag(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()))
