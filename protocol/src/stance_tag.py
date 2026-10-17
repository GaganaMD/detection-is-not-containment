#!/usr/bin/env python3
"""Light intentional vs design stance tagger for postmortem excerpts.

Usage:
  python3 stance_tag.py path/to/excerpt.txt
  echo "The model wanted to cheat" | python3 stance_tag.py -

Human still locks PASS/FAIL on the Stance sheet.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INTENTIONAL = re.compile(
    r"\b(wanted|believed|decided|intended|thought|chose|deceptive|lazy|motivated)\b",
    re.I,
)
DESIGN = re.compile(
    r"\b(reward|flag|CTF|ExploitGym|egress|network|internet|prompt|sandbox|Artifactory|"
    r"monitor|classifier|misconfiguration|harness|tool|proxy|isolation|safeguard)\b",
    re.I,
)


def tag_sentence(s: str) -> str:
    i = bool(INTENTIONAL.search(s))
    d = bool(DESIGN.search(s))
    if i and d:
        return "I+D"
    if i:
        return "I"
    if d:
        return "D"
    return "?"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: stance_tag.py <file|->")
    raw = sys.stdin.read() if sys.argv[1] == "-" else Path(sys.argv[1]).read_text()
    # naive sentence split
    parts = re.split(r"(?<=[.!?])\s+", raw.strip())
    n_i = n_d = 0
    for p in parts:
        if not p.strip():
            continue
        tag = tag_sentence(p)
        if "I" in tag:
            n_i += 1
        if "D" in tag:
            n_d += 1
        print(f"[{tag}] {p.strip()}")
    print("---")
    print(f"intentionalish_sentences={n_i} designish_sentences={n_d}")
    if n_i and not n_d:
        print("draft_hint=FAIL_intentional_only")
    elif n_d:
        print("draft_hint=PASS_has_design_language")
    else:
        print("draft_hint=UNKNOWN")


if __name__ == "__main__":
    main()
