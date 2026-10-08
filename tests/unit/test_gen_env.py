"""The env generator: one spec, both files, no value ever lost or mis-parsed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from dotenv import dotenv_values

from core.config import Settings
from ops.env.gen_env import SPEC, known_keys, main, quote, render

ROOT = Path(__file__).resolve().parents[2]


def _parse(text: str, tmp_path: Path) -> dict[str, str]:
    path = tmp_path / "parsed.env"
    path.write_text(text, encoding="utf-8")
    return {k: (v or "") for k, v in dotenv_values(path).items()}


def test_no_trailing_comments_anywhere() -> None:
    # `KEY=   # note` parses as the value "# note": a bogus non-empty secret.
    for example in (True, False):
        for line in render({}, example=example).splitlines():
            if not line.startswith("#") and "=" in line:
                assert " #" not in line and "\t#" not in line, line


def test_every_key_appears_once_and_the_spec_has_no_duplicates() -> None:
    keys = known_keys()
    assert len(keys) == len(set(keys))
    text = render({}, example=True)
    for name in keys:
        assert len(re.findall(rf"^{name}=", text, flags=re.M)) == 1, name


def test_example_ships_no_secret_values(tmp_path: Path) -> None:
    parsed = _parse(render({}, example=True), tmp_path)
    secrets = [k for t in SPEC for s in t.sections for k in s.keys if k.secret]
    assert secrets
    for key in secrets:
        assert parsed[key.name] == "", key.name


@pytest.mark.parametrize(
    "value",
    [
        "plain",
        "",
        "has space",
        "with # hash",
        "dollar$sign",
        "it's",
        'say "hi"',
        "a\\b",
        "https://x.dev/a?b=c&d=e",
    ],
)
def test_values_round_trip_exactly(value: str, tmp_path: Path) -> None:
    text = render({"LANGFUSE_INIT_USER_NAME": value}, example=False)
    assert _parse(text, tmp_path)["LANGFUSE_INIT_USER_NAME"] == value
    assert quote(value) == value or quote(value)[0] in "'\""


def test_unknown_keys_are_kept_not_dropped(tmp_path: Path) -> None:
    text = render({"QDRANT_URL": "http://q"}, example=False, extra={"OLD_THING": "keep me"})
    parsed = _parse(text, tmp_path)
    assert parsed["OLD_THING"] == "keep me"
    assert parsed["QDRANT_URL"] == "http://q"
    assert "NOT USED BY P2" in text


def test_spec_covers_every_setting_the_app_reads_from_env() -> None:
    # Settings fields with code defaults that are deliberately not exposed in .env.
    internal = {"reranker_model", "rerank_enabled", "min_aggregate_similarity"}
    exposed = {k.lower() for k in known_keys()}
    missing = sorted(set(Settings.model_fields) - exposed - internal)
    assert not missing, f"Settings fields missing from the env spec: {missing}"


def test_main_preserves_values_and_backs_up(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=sk-real\nLANGFUSE_INIT_USER_NAME='Two Words'\nCOHERE_API_KEY=x\n",
        encoding="utf-8",
    )
    assert main(["--root", str(tmp_path)]) == 0
    parsed = dotenv_values(tmp_path / ".env")
    assert parsed["OPENAI_API_KEY"] == "sk-real"
    assert parsed["LANGFUSE_INIT_USER_NAME"] == "Two Words"
    assert parsed["COHERE_API_KEY"] == "x"  # unknown -> kept under "not used"
    assert parsed["QDRANT_HTTP_PORT"] == "2001"  # missing -> added with its default
    assert (tmp_path / ".env.bak").read_text(encoding="utf-8").startswith("OPENAI_API_KEY=sk-real")
    assert dotenv_values(tmp_path / ".env.example")["OPENAI_API_KEY"] == ""


def test_committed_example_is_up_to_date() -> None:
    assert main(["--check", "--root", str(ROOT)]) == 0
