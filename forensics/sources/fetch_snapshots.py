#!/usr/bin/env python3
"""Fetch and hash a frozen local snapshot of every source_url cited across all
forensics/data/incident_*.jsonl files.

Why this exists: an event's `source_url` field points at a live web page.
Live pages can change or disappear; citing one without a frozen copy means
"reproducible" is really "reproducible until someone edits/removes the page."
This script pulls each cited URL with stdlib `urllib` only (no extra deps,
matching the sprint's zero-dependency convention), saves the raw bytes plus a
metadata record (fetch timestamp, HTTP status, SHA-256, byte length), so:

  1. Anyone can re-run this script and diff the new hash against ours to see
     if a source has changed since we cited it.
  2. `../src/check_event_grounding.py` can grep event claims against a fixed,
     checked-in copy of the evidence instead of "trust me, I read it."

Two URLs (LessWrong / Boyd Kane's posts) return 403/429 to a plain scripted
fetch (bot detection) -- see README.md for how those two were captured
instead (now wrapped as .html alongside every other source). Documented,
not hidden.

Usage:
    python3 fetch_snapshots.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORENSICS_DATA = HERE.parent / "data"
RAW = HERE / "raw"

UA = "Mozilla/5.0 (X11; Linux x86_64) research-snapshot/1.0 (+AI-incident-response-sprint Track2 FFP-X)"


def slugify(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s[:120]


def collect_urls() -> dict[str, list[tuple[str, str]]]:
    urls: dict[str, list[tuple[str, str]]] = {}
    for fp in sorted(glob.glob(str(FORENSICS_DATA / "incident_*.jsonl"))):
        case = Path(fp).stem
        for line in Path(fp).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            u = obj.get("source_url", "")
            if not u:
                continue
            urls.setdefault(u, []).append((case, obj["event_id"]))
    return urls


def fetch(url: str, attempts: int = 3, backoff: float = 4.0) -> tuple[int, bytes] | None:
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
    urls = collect_urls()
    manifest = []
    fetched_at = datetime.now(timezone.utc).isoformat()

    print(f"{len(urls)} unique source_url values across all incident_*.jsonl files\n")
    for url, refs in sorted(urls.items()):
        slug = slugify(url)
        out_path = RAW / f"{slug}.html"
        print(f"fetching ({len(refs)} events cite this): {url}")
        result = fetch(url)
        record = {
            "url": url,
            "slug": slug,
            "cited_by_events": [f"{case}:{eid}" for case, eid in refs],
            "fetched_at": fetched_at,
        }
        if result is None:
            record["status"] = "FETCH_FAILED"
            record["note"] = "blocked scripted fetch (see README.md for this source's manual capture)"
        else:
            status, data = result
            out_path.write_bytes(data)
            record["status"] = status
            record["local_path"] = str(out_path.relative_to(HERE.parents[2]))
            record["byte_length"] = len(data)
            record["sha256"] = hashlib.sha256(data).hexdigest()
            print(f"  OK {status} {len(data)}B -> {out_path.name}")
        manifest.append(record)

    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2))
    ok = sum(1 for r in manifest if r["status"] != "FETCH_FAILED")
    print(f"\nwrote {HERE / 'manifest.json'}: {ok}/{len(manifest)} fetched directly")


if __name__ == "__main__":
    main()
