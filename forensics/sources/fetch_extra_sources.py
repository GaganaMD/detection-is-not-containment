#!/usr/bin/env python3
"""Same idea as fetch_snapshots.py, but for the handful of sources that are
cited in plan.html/SOURCES.md (Related Work material) without being any
JSONL event's source_url -- so fetch_snapshots.py never had a reason to
grab them. REPORT_PROVENANCE_PLAN.html flags these as "open issue: not yet
raw-snapshotted" for any PDF quote that uses a specific number from them.
This closes that gap for the ones that are plain scriptable fetches.

Usage:
    python3 fetch_extra_sources.py
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
UA = "Mozilla/5.0 (X11; Linux x86_64) research-snapshot/1.0 (+AI-incident-response-sprint Track2 FFP-X)"

EXTRA_SOURCES = [
    ("https://arxiv.org/abs/2607.25890", "Gore — SHarD (Distributing Security Controls Through Harness Engineering)"),
    ("https://arxiv.org/abs/2507.15886", "Hua et al. — cost-constrained runtime monitors (sprint speaker)"),
    ("https://arxiv.org/abs/2604.21412", "Mengesha et al. — SORT / incident trajectories (sprint speaker)"),
    ("https://labs.cloudsecurityalliance.org/research/csa-research-note-openai-model-sandbox-escape-huggingface-br/", "CSA — The Benchmark That Broke Containment"),
    ("https://labs.cloudsecurityalliance.org/research/csa-research-note-hugging-face-rogue-agent-swarm-20260902-cs/", "CSA — 700 Rogue Agents"),
    ("https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/", "METR + Redwood — independent investigation (~1,200 agents, ~70k messages, scorer motivation, transcript spoofing)"),
]


def slugify(url: str) -> str:
    import re
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s[:120]


def fetch(url: str, attempts: int = 3, backoff: float = 4.0):
    last_err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
        if i < attempts - 1:
            time.sleep(backoff)
    print(f"  FAILED after {attempts} attempts: {last_err}")
    return None


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    fetched_at = datetime.now(timezone.utc).isoformat()
    for url, note in EXTRA_SOURCES:
        slug = slugify(url)
        print(f"fetching: {url}")
        result = fetch(url)
        record = {"url": url, "slug": slug, "note": note, "fetched_at": fetched_at}
        if result is None:
            record["status"] = "FETCH_FAILED"
        else:
            status, data = result
            (RAW / f"{slug}.html").write_bytes(data)
            record.update(
                status=status,
                byte_length=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
            print(f"  OK {status} {len(data)}B")
        manifest.append(record)

    (HERE / "extra_sources_manifest.json").write_text(json.dumps(manifest, indent=2))
    ok = sum(1 for r in manifest if r["status"] != "FETCH_FAILED")
    print(f"\nwrote {HERE / 'extra_sources_manifest.json'}: {ok}/{len(manifest)} fetched")


if __name__ == "__main__":
    main()
