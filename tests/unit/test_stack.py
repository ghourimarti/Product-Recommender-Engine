"""ops/stack: the service directory, the kind lifecycle decisions, make help and the Makefile."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from ops.stack import catalog, directory, kind, make_help
from ops.stack.catalog import KindState, compose_groups, load_env, model_group

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = {
    tier: ROOT / f"infra/compose/docker-compose.{tier}.yml"
    for tier in ("data", "app", "observability")
}
LOCAL_SECRETS = (
    "LANGFUSE_POSTGRES_PASSWORD",
    "LANGFUSE_CLICKHOUSE_PASSWORD",
    "LANGFUSE_REDIS_AUTH",
    "LANGFUSE_MINIO_ROOT_PASSWORD",
    "LANGFUSE_INIT_USER_PASSWORD",
    "LANGFUSE_SECRET_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "QDRANT_API_KEY",
)


def _env() -> dict[str, str]:
    """Defaults plus a sentinel in every secret, so a leak is easy to spot."""
    env = load_env(Path("does-not-exist.env"))
    for key in (*catalog.PROVIDER_SECRETS, *LOCAL_SECRETS):
        env[key] = f"sentinel-{key.lower()}-0123456789"
    return env


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    env = _env()
    monkeypatch.setattr(directory, "load_env", lambda: env)
    monkeypatch.setattr(directory, "running_containers", lambda: {"p2-api", "p2-web"})
    monkeypatch.setattr(directory, "kind_clusters", lambda: {})
    monkeypatch.setattr(directory, "kind_addons", lambda context: set())
    return env


def test_defaults_come_from_the_env_spec(tmp_path: Path) -> None:
    env = load_env(tmp_path / "missing.env")
    assert env["API_PORT"] == "2011" and env["LANGFUSE_UI_PORT"] == "2008"
    path = tmp_path / ".env"
    path.write_text("API_PORT=2999\n", encoding="utf-8")
    assert load_env(path)["API_PORT"] == "2999"


def test_every_listed_container_is_a_compose_container() -> None:
    names = {
        svc.get("container_name")
        for path in COMPOSE.values()
        for svc in yaml.safe_load(path.read_text(encoding="utf-8"))["services"].values()
    }
    listed = {i.container for g in compose_groups(_env()) for i in g.items if i.container}
    assert listed <= names, listed - names


def test_urls_print_no_credentials(offline: dict[str, str]) -> None:
    out = directory.render(creds=False, cluster="p2")
    assert "sentinel" not in out
    assert "http://localhost:2012" in out and "http://localhost:2008" in out


def test_service_ls_prints_local_logins_but_never_provider_keys(offline: dict[str, str]) -> None:
    out = directory.render(creds=True, cluster="p2")
    for key in catalog.PROVIDER_SECRETS:
        assert offline[key] not in out, key
    for key in LOCAL_SECRETS:
        assert offline[key] in out, key
    assert "postgresql://langfuse:" in out


def test_status_marks(offline: dict[str, str]) -> None:
    out = directory.render(creds=False, cluster="p2")
    assert re.search(r"\[ up \] Web app", out)
    assert re.search(r"\[DOWN\] Grafana", out)
    assert re.search(r"\[key \] 1\. Groq", out)
    assert "kind cluster 'p2' (absent)" in out


def test_missing_provider_key_is_flagged(offline: dict[str, str]) -> None:
    offline["GROQ_API_KEY"] = ""
    out = directory.render(creds=False, cluster="p2")
    assert re.search(r"\[MISS\] 1\. Groq", out)


def test_llm_chain_is_in_fallback_order() -> None:
    names = [item.name for item in model_group(_env()).items]
    assert names[:3] == ["1. Groq (tried first)", "2. OpenAI (fallback)", "3. Anthropic (last)"]


def test_kind_state_labels() -> None:
    assert KindState("p2").label == "absent"
    assert KindState("p2", {"a": "running", "b": "running"}).label == "running"
    stopped = KindState("p2", {"a": "running", "b": "exited"})
    assert stopped.exists and not stopped.running and stopped.label == "stopped (1/2 nodes up)"


def test_kind_clusters_reads_node_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    out = "p2 p2-control-plane running\np2 p2-worker exited\nother other-control-plane running\n"

    def fake_run(cmd: Any, timeout: float = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, out, "")

    monkeypatch.setattr(catalog, "run", fake_run)
    clusters = catalog.kind_clusters()
    assert set(clusters) == {"p2", "other"}
    assert clusters["p2"].nodes == {"p2-control-plane": "running", "p2-worker": "exited"}


@pytest.fixture
def kind_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {"clusters": {}, "available": 8192}
    monkeypatch.setattr("ops.stack.kind.shutil.which", lambda tool: f"/bin/{tool}")
    monkeypatch.setattr(kind, "kind_clusters", lambda: state["clusters"])
    monkeypatch.setattr(kind, "vm_available_mb", lambda: state["available"])
    monkeypatch.setattr(kind, "container_memory_mb", lambda names: 3300)
    return state


def test_plan_skips_when_disabled(kind_env: dict[str, Any]) -> None:
    assert kind.plan("p2", enabled=False, need_gb=6) == "skip"


def test_plan_creates_a_missing_cluster(kind_env: dict[str, Any]) -> None:
    assert kind.plan("p2", enabled=True, need_gb=6) == "create"


def test_plan_restarts_a_stopped_cluster(kind_env: dict[str, Any]) -> None:
    kind_env["clusters"] = {"p2": KindState("p2", {"p2-control-plane": "exited"})}
    assert kind.plan("p2", enabled=True, need_gb=6) == "restart"


def test_plan_leaves_a_running_cluster_alone(kind_env: dict[str, Any]) -> None:
    kind_env["clusters"] = {"p2": KindState("p2", {"p2-control-plane": "running"})}
    kind_env["available"] = 100  # a running cluster needs no new memory
    assert kind.plan("p2", enabled=True, need_gb=6) == "running"


def test_plan_skips_without_memory_and_names_other_clusters(
    kind_env: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    kind_env["available"] = 4900
    kind_env["clusters"] = {
        "voyantra": KindState("voyantra", {"voyantra-control-plane": "running"})
    }
    assert kind.plan("p2", enabled=True, need_gb=6) == "skip"
    err = capsys.readouterr().err
    assert "voyantra" in err and "docker stop voyantra-control-plane" in err


def test_plan_skips_without_tools(
    monkeypatch: pytest.MonkeyPatch, kind_env: dict[str, Any]
) -> None:
    monkeypatch.setattr(
        "ops.stack.kind.shutil.which", lambda tool: None if tool == "helm" else tool
    )
    assert kind.plan("p2", enabled=True, need_gb=6) == "skip"


def test_stop_never_touches_other_clusters(
    monkeypatch: pytest.MonkeyPatch, kind_env: dict[str, Any]
) -> None:
    kind_env["clusters"] = {
        "p2": KindState("p2", {"p2-control-plane": "running", "p2-worker": "running"}),
        "voyantra": KindState("voyantra", {"voyantra-control-plane": "running"}),
    }
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], timeout: float = 30) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(kind, "run", fake_run)
    assert kind.stop("p2") == 0
    assert calls == [["docker", "stop", "p2-control-plane", "p2-worker"]]


# ---- the Makefile ----------------------------------------------------------------------------

MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")


def _make_var(name: str) -> set[str]:
    joined = MAKEFILE.replace("\\\n", " ")
    match = re.search(rf"^{name}\s*:=\s*(.+)$", joined, re.MULTILINE)
    assert match, name
    words: set[str] = set()
    for word in match.group(1).split():
        ref = re.fullmatch(r"\$\((\w+)\)", word)
        words |= _make_var(ref.group(1)) if ref else {word}
    return words


@pytest.mark.parametrize(
    ("var", "tier"), [("SVC_DATA", "data"), ("SVC_APP", "app"), ("SVC_OBS", "observability")]
)
def test_tier_service_lists_match_compose(var: str, tier: str) -> None:
    services = set(yaml.safe_load(COMPOSE[tier].read_text(encoding="utf-8"))["services"])
    assert _make_var(var) == services


def test_recipes_are_shell_neutral() -> None:
    # From PowerShell, make runs recipes in cmd.exe: no sh syntax may appear in a recipe line.
    sh_only = re.compile(r"\$\$\(|;\s*then\b|\bfi\b|/dev/null|\bset -a\b|\bfor \w+ in\b|\|\| true")
    recipes = [line for line in MAKEFILE.splitlines() if line.startswith("\t")]
    assert recipes
    assert [line for line in recipes if sh_only.search(line)] == []


def test_echo_lines_avoid_shell_metacharacters() -> None:
    # Parentheses or quotes in echo break sh or print literally in cmd.exe.
    echoes = [line for line in MAKEFILE.splitlines() if re.match(r"\t@?echo\b", line)]
    shell_text = [
        re.sub(r"\$\([^)]*\)", "", line) for line in echoes
    ]  # $(VAR) is make's, not the shell's
    bad = [line for line in shell_text if re.search(r"[()'\"<>|&;]", line)]
    assert bad == []


def test_help_lists_every_documented_target() -> None:
    sections = dict(make_help.sections(MAKEFILE))
    documented = {name for targets in sections.values() for name, _ in targets}
    for target in (
        "up",
        "upv",
        "down",
        "downv",
        "urls",
        "service_ls",
        "verify",
        "kind-start",
        "kind-all",
    ):
        assert target in documented
    assert any(title.startswith("7. LIFECYCLE") for title in sections)


def test_every_phony_target_has_a_rule() -> None:
    joined = MAKEFILE.replace("\\\n", " ")
    phony = set(re.search(r"^\.PHONY:(.+)$", joined, re.MULTILINE).group(1).split())  # type: ignore[union-attr]
    rules = set(re.findall(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", MAKEFILE, re.MULTILINE))
    assert phony - rules == set()


def test_no_compose_service_restarts_on_its_own() -> None:
    # After a reboot P2 stays down until `make up`: half a stack (Langfuse without the app) helped
    # nobody and held memory while other projects ran.
    for path in COMPOSE.values():
        for name, svc in yaml.safe_load(path.read_text(encoding="utf-8"))["services"].items():
            assert "restart" not in svc, f"{path.name}: {name}"
