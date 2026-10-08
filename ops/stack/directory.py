"""Print where every P2 component lives, and whether it is running.

    uv run python -m ops.stack.directory urls     # make urls: no credentials, safe to share
    uv run python -m ops.stack.directory creds    # make service_ls: plus local logins

Status comes from `docker ps` (compose containers and kind nodes), so it is instant and needs no
network. `make verify` is the deep check: it calls every service.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Mapping

from ops.stack.catalog import (
    PROVIDER_SECRETS,
    Group,
    Item,
    KindState,
    compose_groups,
    kind_addons,
    kind_clusters,
    kind_group,
    kind_secret_value,
    load_env,
    model_group,
    running_containers,
)

WIDTH = 100
NAME_W = 30
TARGET_W = 42


def _row(tag: str, name: str, target: str, note: str) -> str:
    line = f"  {tag} {name:<{NAME_W}} {target}"
    if note:
        pad = max(TARGET_W - len(target), 0)
        line += " " * pad + "  " + note
    return line.rstrip()


def render_group(
    group: Group,
    tag_for: Callable[[Item], str],
    *,
    creds: bool,
    redact: frozenset[str] = frozenset(),
) -> list[str]:
    lines = ["", f"  {group.title} ".ljust(WIDTH, "-")]
    for item in group.items:
        tag = tag_for(item)
        links = item.links or ()
        first = links[0] if links else None
        lines.append(
            _row(tag, item.name, first.target if first else "", first.note if first else "")
        )
        for link in links[1:]:
            lines.append(_row(" " * len(tag), "", link.target, link.note))
        if creds:
            for label, value in item.creds:
                for secret in redact:
                    value = value.replace(secret, "<redacted>")
                lines.append(f"  {'':<{len(tag)}} {'':<4}{label:<12} {value}")
    if creds and group.footer:
        lines.extend(f"         {text}" for text in group.footer)
    return lines


def compose_tag(running: set[str] | None) -> Callable[[Item], str]:
    def tag(item: Item) -> str:
        if item.container is None:
            return "[    ]"
        if running is None:
            return "[ ?? ]"
        return "[ up ]" if item.container in running else "[DOWN]"

    return tag


def model_tag(env: Mapping[str, str], running: set[str] | None) -> Callable[[Item], str]:
    container_tag = compose_tag(running)

    def tag(item: Item) -> str:
        if item.key:
            return "[key ]" if env.get(item.key) else "[MISS]"
        return container_tag(item)

    return tag


def kind_tag(state: KindState) -> Callable[[Item], str]:
    value = "[ up ]" if state.running else "[stop]" if state.exists else "[ -- ]"
    return lambda item: value


def render(*, creds: bool, cluster: str) -> str:
    env = load_env()
    running = running_containers()
    # A provider key never reaches the screen, even if someone pastes one into a printed field.
    redact = frozenset(v for k, v in env.items() if k in PROVIDER_SECRETS and len(v) >= 8)

    title = (
        "P2 ProductIQ - services and LOCAL logins" if creds else "P2 ProductIQ - service directory"
    )
    hint = "provider API keys are never printed" if creds else "make service_ls adds the logins"
    out = [
        "",
        "  " + "=" * (WIDTH - 2),
        f"   {title:<{WIDTH - 45}}{hint:>40}",
        "  " + "=" * (WIDTH - 2),
    ]
    if running is None:
        out.append("  Docker is not reachable: start Docker Desktop, then make up.")

    groups = compose_groups(env)
    for group in groups:
        out += render_group(group, compose_tag(running), creds=creds, redact=redact)
    out += render_group(model_group(env), model_tag(env, running), creds=creds, redact=redact)

    state = kind_clusters().get(cluster, KindState(cluster))
    addons = kind_addons(f"kind-{cluster}") if state.running else set()
    passwords: dict[str, str | None] = {}
    if creds and state.running:
        ctx = f"kind-{cluster}"
        if "argocd" in addons:
            passwords["argocd"] = kind_secret_value(
                ctx, "argocd", "argocd-initial-admin-secret", "password"
            )
        if "monitoring" in addons:
            passwords["grafana"] = kind_secret_value(
                ctx, "monitoring", "kube-prometheus-stack-grafana", "admin-password"
            )
    out += render_group(kind_group(cluster, state, addons, passwords), kind_tag(state), creds=creds)

    out.append("")
    out.append("  " + "=" * (WIDTH - 2))
    containers = [i.container for g in groups for i in g.items if i.container]
    if running is not None:
        down = [c for c in containers if c not in running]
        summary = f"   compose: {len(containers) - len(down)}/{len(containers)} UIs running"
        summary += f"   kind '{cluster}': {state.label}"
        out.append(summary)
        if down:
            out.append(f"   not running: {', '.join(down)}  ->  make up")
        if not state.running:
            out.append("   kind not running  ->  make kind-start   (or make up; KIND=0 skips kind)")
    out.append("   deep check of every component: make verify")
    out.append("  " + "=" * (WIDTH - 2))
    out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["urls", "creds"])
    parser.add_argument("--cluster", default=os.environ.get("KIND_CLUSTER", "p2"))
    args = parser.parse_args(argv)
    print(render(creds=args.mode == "creds", cluster=args.cluster))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
