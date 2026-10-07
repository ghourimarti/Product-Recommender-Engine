"""The kind GitOps deploy repo: what Argo CD sees, built from the working tree."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from infra.kind.gitops_push import RELEASE_FILE, SYNCED_PATHS, _git, build

ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def test_deploy_repo_mirrors_the_chart_and_apps_and_carries_the_tag(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy"
    assert build(ROOT, deploy, "abc1234") is True
    for rel in SYNCED_PATHS:
        assert (deploy / rel).is_dir(), rel
    assert (deploy / "ops/helm/p2-recommender/Chart.yaml").read_bytes() == (
        ROOT / "ops/helm/p2-recommender/Chart.yaml"
    ).read_bytes()
    release = yaml.safe_load((deploy / RELEASE_FILE).read_text(encoding="utf-8"))
    assert release == {"image": {"tag": "abc1234"}}
    # Only what Argo CD needs: no app code, no .env, nothing else from the project.
    assert sorted(p.name for p in deploy.iterdir()) == [".git", "ops"]
    assert sorted(p.name for p in (deploy / "ops").iterdir()) == ["argocd", "helm"]


def test_rebuilding_without_changes_makes_no_commit(tmp_path: Path) -> None:
    deploy = tmp_path / "deploy"
    build(ROOT, deploy, "abc1234")
    assert build(ROOT, deploy, "abc1234") is False
    assert build(ROOT, deploy, "def5678") is True  # a new tag is a new deploy
    log = _git(deploy, "log", "--format=%s").split("\n")
    assert [line for line in log if line] == ["deploy def5678", "deploy abc1234"]


def test_the_committed_release_file_has_no_tag() -> None:
    # The project's copy stays empty: only a real deploy writes a tag.
    committed = yaml.safe_load((ROOT / RELEASE_FILE).read_text(encoding="utf-8"))
    assert committed == {"image": {"tag": ""}}


def test_a_tag_is_required(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="tag"):
        build(ROOT, tmp_path / "deploy", "")
