"""`make help`: every documented target, grouped under the Makefile's boxed section titles.

A target is documented by a trailing `## text` on its rule line. Python rather than grep/awk,
because make on Windows runs recipes in cmd.exe, which has neither.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SECTION = re.compile(r"^#\s+(\d+\.\s+.+?)\s*$")
TARGET = re.compile(r"^([A-Za-z0-9_.-]+)\s*:[^=].*?##\s*(.+)$")


def sections(makefile: str) -> list[tuple[str, list[tuple[str, str]]]]:
    out: list[tuple[str, list[tuple[str, str]]]] = [("", [])]
    for line in makefile.splitlines():
        if match := SECTION.match(line):
            out.append((match.group(1), []))
        elif match := TARGET.match(line):
            out[-1][1].append((match.group(1), match.group(2).strip()))
    return [(title, targets) for title, targets in out if targets]


def main(argv: list[str] | None = None) -> int:
    path = Path((argv or sys.argv[1:] or ["Makefile"])[0])
    for title, targets in sections(path.read_text(encoding="utf-8")):
        print(f"\n  {title}")
        for name, doc in targets:
            print(f"    {name:<24} {doc}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
