"""Local image tags: one tag per build input state, so a rebuild after an edit always rolls out."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from infra.kind.image_tag import image_tag

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo: Path, *args: str) -> str:
    command = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    return subprocess.run(
        [*command, *args], capture_output=True, check=True, encoding="utf-8"
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "app.py").write_text("x = 1\n")
    (tmp_path / "README.md").write_text("docs\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_clean_tree_is_the_short_sha(repo: Path) -> None:
    assert image_tag(repo) == _git(repo, "rev-parse", "--short", "HEAD")


def test_each_edit_gets_its_own_tag_and_undoing_it_restores_the_old_one(repo: Path) -> None:
    sha = image_tag(repo)
    source = repo / "packages" / "app.py"
    source.write_text("x = 2\n")
    first = image_tag(repo)
    source.write_text("x = 3\n")
    second = image_tag(repo)
    assert first.startswith(f"{sha}-dirty-") and second.startswith(f"{sha}-dirty-")
    assert first != second  # a rebuild after an edit must not reuse a tag
    source.write_text("x = 2\n")
    assert image_tag(repo) == first  # same content, same tag
    source.write_text("x = 1\n")
    assert image_tag(repo) == sha


def test_untracked_inputs_count_but_other_files_do_not(repo: Path) -> None:
    sha = image_tag(repo)
    (repo / "README.md").write_text("edited docs\n")  # not an image input
    assert image_tag(repo) == sha
    new_module = repo / "packages" / "new.py"
    new_module.write_text("y = 1\n")
    tagged = image_tag(repo)
    assert tagged.startswith(f"{sha}-dirty-")
    new_module.write_text("y = 2\n")
    assert image_tag(repo) != tagged
