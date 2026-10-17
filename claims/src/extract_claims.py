#!/usr/bin/env python3
"""Step 1: LLM claim extraction.

CORRECTED DESIGN (see groq_client.py docstring): the account has a real
~8000-token/minute cap that governs a SINGLE request's size, not just a
rate ceiling across many small ones -- a single call for a ~43k-char source
(openai.com's post, not even the largest) hit a hard 413 requesting 11,550
tokens against an 8000 limit. So sources ARE chunked here, sized
conservatively against the real measured cap -- reversing the plan's
earlier (wrong) "no chunking needed" call, which was based on misreading
the rate-limit headers as a fast-refilling per-second bucket.

Chunk budget math: reserve max_tokens=1500 for output, ~300 tokens for the
fixed prompt template text, ~100 tokens headroom for reasoning -- leaves
~6100 tokens, so document chunks are capped at ~5500 tokens (~22,000 chars
at a conservative 4 chars/token) to leave margin for estimation error.
Chunks overlap by 400 chars so a fact stated right at a chunk boundary
isn't silently split in half.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAIMS_ROOT = HERE.parent
SUBMISSION = CLAIMS_ROOT.parent
SOURCES_RAW = SUBMISSION / "forensics" / "sources" / "raw"
# override to run two backends into separate output dirs for an A/B comparison
OUT_DIR = Path(os.environ.get("CLAIMS_OUT_DIR", str(CLAIMS_ROOT / "out")))

sys.path.insert(0, str(HERE))
from groq_client import (  # noqa: E402
    call_groq,
    extract_message_text,
    call_budget_used,
    estimate_tokens,
    wait_for_token_budget,
    RequestTooLargeError,
    MODEL,
)
from html_util import strip_html, normalize_for_match  # noqa: E402

PROMPT_TEMPLATE = (HERE / "prompt_extract.txt").read_text()

CHUNK_CHARS = 22_000
CHUNK_OVERLAP_CHARS = 400
OUTPUT_MAX_TOKENS = 1500

# Previously confirmed unextractable (JS single-page app, zero incident content
# in the raw snapshot -- verify/FINDINGS.md #1). Now backed by a manual-fallback
# capture (forensics/sources/raw/.originals/ has the original SPA-shell snapshot)
# built from forensics/data/hf_space_EVENTS.json, so no longer skipped.
SKIP_SOURCE_URLS: set[str] = set()

def load_registry() -> list[dict]:
    return json.loads((CLAIMS_ROOT / "data" / "source_registry.json").read_text())


def load_source_text(row: dict) -> str | None:
    """All 20 sources live as `{slug}.html` under forensics/sources/raw/ --
    including the 2 manual-fallback captures (wrapped in a trivial HTML
    shell for a consistent extension); strip_html() below reduces both to
    plain text the same way, so no special-casing is needed here."""
    if row["url"] in SKIP_SOURCE_URLS:
        return None
    p = SOURCES_RAW / f"{row['slug']}.html"
    if not p.exists():
        return None
    raw = p.read_text(encoding="utf-8", errors="replace")
    return strip_html(raw)


def chunk_text(text: str, chunk_chars: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    if len(text) <= chunk_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def parse_jsonl_response(content: str) -> tuple[list[dict], list[str]]:
    """Returns (parsed_claims, parse_error_lines)."""
    claims, errors = [], []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^```(json)?|```$", "", line).strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "claim" in obj:
                claims.append(obj)
            else:
                errors.append(line)
        except json.JSONDecodeError:
            errors.append(line)
    return claims, errors


def extract_for_source(row: dict) -> tuple[list[dict], dict]:
    """Returns (claim_records, run_metadata). Chunks internally if needed."""
    text = load_source_text(row)
    if text is None:
        return [], {"status": "skipped", "reason": "no source text available or explicitly excluded"}

    chunks = chunk_text(text)
    run_meta = {
        "source_id": row["source_id"],
        "source_url": row["url"],
        "model": MODEL,
        "document_chars": len(text),
        "n_chunks": len(chunks),
        "chunks": [],
    }

    claim_records = []
    seq = 1
    now = datetime.now(timezone.utc).isoformat()

    for chunk_idx, chunk in enumerate(chunks, start=1):
        prompt = PROMPT_TEMPLATE.format(source_url=row["url"], document_text=chunk)
        est_needed = estimate_tokens(prompt) + OUTPUT_MAX_TOKENS
        wait_for_token_budget(est_needed)
        try:
            response = call_groq(
                [{"role": "user", "content": prompt}],
                reasoning_effort="low",
                max_tokens=OUTPUT_MAX_TOKENS,
            )
        except RequestTooLargeError as e:
            run_meta["chunks"].append(
                {"chunk_index": chunk_idx, "status": "REQUEST_TOO_LARGE", "error": str(e)}
            )
            continue

        content, reasoning = extract_message_text(response)
        parsed, parse_errors = parse_jsonl_response(content)
        run_meta["chunks"].append(
            {
                "chunk_index": chunk_idx,
                "chunk_chars": len(chunk),
                "usage": call_budget_used(response),
                "n_parsed": len(parsed),
                "n_parse_errors": len(parse_errors),
                "parse_error_lines": parse_errors[:10],
                "raw_response": response,
            }
        )

        for c in parsed:
            quote = c.get("quote", "")
            quote_verified = bool(quote) and normalize_for_match(quote) in normalize_for_match(text)  # check against FULL text, not just this chunk
            claim_records.append(
                {
                    "claim_id": f"EC-{row['source_id']}-{seq:03d}",
                    "source_id": row["source_id"],
                    "source_url": row["url"],
                    "claim_text": c.get("claim", ""),
                    "quote": quote,
                    "quote_verified": quote_verified,
                    "extraction_model": MODEL,
                    "extraction_run_id": f"{row['source_id']}_chunk{chunk_idx:02d}",
                    "epistemic_hint": c.get("epistemic_hint", "unknown"),
                    "status": "proposed",
                    "created_at": now,
                    "pipeline_version": "claims-v1",
                }
            )
            seq += 1

    run_meta["n_parsed_total"] = len(claim_records)
    return claim_records, run_meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=None, help="comma-separated SRC## ids, default = all")
    args = ap.parse_args()

    registry = load_registry()
    if args.sources:
        wanted = set(args.sources.split(","))
        registry = [r for r in registry if r["source_id"] in wanted]

    out_dir = OUT_DIR
    (out_dir / "claims_raw").mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "claims_extracted.jsonl"

    # --sources restricts which sources get (re-)extracted this run, but must
    # NOT drop claims already extracted for every OTHER source -- a plain
    # overwrite here previously meant `--sources SRC19` silently deleted the
    # 146 claims from the SRC06/10/14 pilot. Merge instead: keep every
    # existing claim whose source_id wasn't part of this run, replace the
    # ones that were (so a re-run of an already-extracted source updates
    # cleanly rather than duplicating).
    rerun_ids = {row["source_id"] for row in registry}
    preserved = []
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            if c["source_id"] not in rerun_ids:
                preserved.append(c)

    def write_merged(new_so_far: list[dict]) -> None:
        with out_path.open("w") as f:
            for c in preserved + new_so_far:
                f.write(json.dumps(c) + "\n")

    # Write after EVERY source, not just once at the end of the whole batch:
    # a multi-source run can take a long time (network/rate-limit stalls are
    # real -- one hung request during a 15-source run lost all 9 already-
    # completed sources' worth of claims because they only lived in this
    # function's local list until the final write). Now each source's
    # progress survives a kill/crash on a LATER source.
    new_claims: list[dict] = []
    for row in registry:
        print(f"extracting {row['source_id']} ({row['url']}) ...")
        claims, meta = extract_for_source(row)
        (out_dir / "claims_raw" / f"{row['source_id']}.json").write_text(json.dumps(meta, indent=2))
        if meta.get("status") == "skipped":
            print(f"  skipped: {meta['reason']}")
            continue
        print(f"  {meta['n_chunks']} chunk(s) -> {meta['n_parsed_total']} claims parsed")
        new_claims.extend(claims)
        write_merged(new_claims)
        print(f"  saved -- {len(preserved) + len(new_claims)} total claims in {out_path.name} so far")

    print(f"\nwrote {out_path}: {len(new_claims)} new/updated claims "
          f"({rerun_ids or 'all sources'}) + {len(preserved)} preserved from other sources "
          f"= {len(preserved) + len(new_claims)} total")


if __name__ == "__main__":
    main()
