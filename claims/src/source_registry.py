#!/usr/bin/env python3
"""Stable SRC## ids for every snapshotted source, union of the two manifests
produced by `forensics/sources/`. Append-only: a URL's id,
once assigned, never changes on a later run, even if new URLs are added --
otherwise every downstream claim_id (EC-{source_id}-{seq}) would silently
break whenever the source list grows.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAIMS_ROOT = HERE.parent
SUBMISSION = CLAIMS_ROOT.parent
FORENSICS_SOURCES = SUBMISSION / "forensics" / "sources"
REGISTRY_PATH = CLAIMS_ROOT / "data" / "source_registry.json"


def _load_manifest_urls() -> list[dict]:
    """Union of both manifests' records, each carrying enough info to locate
    the raw snapshot file (or manual_fallback) later."""
    records: dict[str, dict] = {}

    main = json.loads((FORENSICS_SOURCES / "manifest.json").read_text())
    for rec in main:
        records[rec["url"]] = {
            "url": rec["url"],
            "slug": rec["slug"],
            "status": rec["status"],
            "has_manual_fallback": rec["status"] == "FETCH_FAILED",
        }

    extra = json.loads((FORENSICS_SOURCES / "extra_sources_manifest.json").read_text())
    for rec in extra:
        if rec["url"] not in records:
            records[rec["url"]] = {
                "url": rec["url"],
                "slug": rec["slug"],
                "status": rec["status"],
                "has_manual_fallback": rec["status"] == "FETCH_FAILED",
            }

    return list(records.values())


def load_or_build_registry() -> list[dict]:
    """Returns list of {source_id, url, slug, has_manual_fallback}, stable
    across runs. Loads existing assignments from disk first; only assigns
    fresh SRC## ids to URLs not already present."""
    existing: dict[str, dict] = {}
    if REGISTRY_PATH.exists():
        for row in json.loads(REGISTRY_PATH.read_text()):
            existing[row["url"]] = row

    all_urls = _load_manifest_urls()
    used_numbers = {int(r["source_id"][3:]) for r in existing.values()}
    next_num = max(used_numbers, default=0) + 1

    # New URLs not yet assigned: sort alphabetically for a deterministic
    # first-time assignment order.
    new_urls = sorted(
        (u for u in all_urls if u["url"] not in existing),
        key=lambda u: u["url"],
    )
    for u in new_urls:
        source_id = f"SRC{next_num:02d}"
        existing[u["url"]] = {
            "source_id": source_id,
            "url": u["url"],
            "slug": u["slug"],
            "has_manual_fallback": u["has_manual_fallback"],
        }
        next_num += 1

    rows = sorted(existing.values(), key=lambda r: r["source_id"])
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(rows, indent=2))
    return rows


def get_source_id(url: str, registry: list[dict] | None = None) -> str | None:
    registry = registry or load_or_build_registry()
    for row in registry:
        if row["url"] == url:
            return row["source_id"]
    return None


def main() -> None:
    rows = load_or_build_registry()
    print(f"{len(rows)} sources registered -> {REGISTRY_PATH}")
    for r in rows:
        print(f"  {r['source_id']}  {r['url']}" + ("  [manual_fallback]" if r["has_manual_fallback"] else ""))


if __name__ == "__main__":
    main()
