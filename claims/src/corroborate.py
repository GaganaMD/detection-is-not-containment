#!/usr/bin/env python3
"""Step 3: LLM corroboration judgment, batched per (origin_source,
candidate_source) pair -- NOT per claim, and NOT the candidate's full text
(the real ~8000 TPM account cap, discovered while building extract_claims.py,
rules out handing over whole documents for anything but the smallest
candidates). Instead: build a bounded excerpt of the candidate centered on
the term matches the deterministic prefilter already found, and dynamically
split the claims list into sub-batches sized against the real token budget
rather than a fixed count.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAIMS_ROOT = HERE.parent
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
from prefilter import load_raw_html  # noqa: E402
from html_util import strip_html  # noqa: E402
from claim_schema import CORROBORATION_TYPES  # noqa: E402

PROMPT_TEMPLATE = (HERE / "prompt_corroborate.txt").read_text()

EXCERPT_WINDOW_CHARS = 350
MAX_EXCERPT_TOTAL_CHARS = 9000
OUTPUT_MAX_TOKENS = 3000
PROMPT_OVERHEAD_TOKENS = 500  # fixed template text + JSON scaffolding
SAFE_INPUT_BUDGET_TOKENS = 6000  # leaves margin under the real 8000 cap


def load_registry() -> dict[str, dict]:
    rows = json.loads((CLAIMS_ROOT / "data" / "source_registry.json").read_text())
    return {r["source_id"]: r for r in rows}


def build_excerpt(candidate_text_lower_stripped_case_preserving: str, shared_terms_by_claim: list[list[str]]) -> str:
    """Merge windows around every shared term across all claims in this
    batch into one bounded excerpt. Case-insensitive search, case-preserving
    output (so quotes the model returns can be verified against the
    original casing)."""
    text = candidate_text_lower_stripped_case_preserving
    lower = text.lower()
    windows: list[tuple[int, int]] = []
    for terms in shared_terms_by_claim:
        for term in terms:
            idx = lower.find(term.lower())
            if idx != -1:
                windows.append((max(0, idx - EXCERPT_WINDOW_CHARS), min(len(text), idx + len(term) + EXCERPT_WINDOW_CHARS)))
    if not windows:
        return text[:MAX_EXCERPT_TOTAL_CHARS]

    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1] + 50:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    pieces = []
    total = 0
    for start, end in merged:
        piece = text[start:end]
        if total + len(piece) > MAX_EXCERPT_TOTAL_CHARS:
            break
        pieces.append(piece)
        total += len(piece)
    return "\n[...]\n".join(pieces)


def dynamic_batches(claims: list[dict], excerpt: str) -> list[list[dict]]:
    """Split claims into sub-batches sized so each call's estimated total
    (prompt template + excerpt + claims-json + output reserve) stays under
    SAFE_INPUT_BUDGET_TOKENS, rather than a fixed claim count."""
    batches: list[list[dict]] = []
    current: list[dict] = []
    excerpt_tokens = estimate_tokens(excerpt)
    for c in claims:
        claim_tokens = estimate_tokens(json.dumps({"claim_id": c["claim_id"], "claim": c["claim_text"], "quote": c["quote"]}))
        prospective = current + [c]
        claims_tokens = sum(
            estimate_tokens(json.dumps({"claim_id": x["claim_id"], "claim": x["claim_text"], "quote": x["quote"]}))
            for x in prospective
        )
        total_est = PROMPT_OVERHEAD_TOKENS + excerpt_tokens + claims_tokens
        if total_est > SAFE_INPUT_BUDGET_TOKENS and current:
            batches.append(current)
            current = [c]
        else:
            current.append(c)
    if current:
        batches.append(current)
    return batches


def parse_verdict_array(content: str) -> tuple[list[dict], str | None]:
    content = re.sub(r"^```(json)?|```$", "", content.strip(), flags=re.M).strip()
    try:
        arr = json.loads(content)
        if isinstance(arr, list):
            return arr, None
        return [], f"expected JSON array, got {type(arr).__name__}"
    except json.JSONDecodeError as e:
        return [], f"JSONDecodeError: {e}"


def run_corroboration() -> None:
    registry = load_registry()
    prefilter_path = OUT_DIR / "prefilter_pairs.csv"
    claims_path = OUT_DIR / "claims_extracted.jsonl"
    if not prefilter_path.exists() or not claims_path.exists():
        print("run extract_claims.py and prefilter.py first")
        return

    claims_by_id = {}
    for line in claims_path.read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            claims_by_id[c["claim_id"]] = c

    with prefilter_path.open(newline="") as f:
        pairs = [r for r in csv.DictReader(f) if r["prefilter_pass"] == "True"]

    # group by (origin_source_id, candidate_source_id)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in pairs:
        groups[(row["origin_source_id"], row["candidate_source_id"])].append(row)

    all_results = []
    run_dir = OUT_DIR / "corroboration_runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "corroboration_results.csv"

    def flush_results() -> None:
        """Write whatever's accumulated so far -- called after every pair,
        not just once at the end, so a crash mid-run (a real one already
        happened: a slow-but-legitimate Ollama generation exceeded the old
        socket timeout and took the whole process down) loses at most the
        one in-flight pair, not every result computed before it."""
        if all_results:
            with out_path.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
                w.writeheader()
                w.writerows(all_results)

    print(f"{len(groups)} (origin, candidate) source-pairs with >=1 prefilter-passing claim")

    for (origin_id, candidate_id), rows in groups.items():
        candidate_loaded = load_raw_html(candidate_id, list(registry.values()))
        if candidate_loaded is None:
            continue
        candidate_raw, candidate_is_html = candidate_loaded
        candidate_text = strip_html(candidate_raw) if candidate_is_html else candidate_raw

        claims_in_group = []
        shared_terms_lists = []
        for row in rows:
            claim = claims_by_id.get(row["claim_id"])
            if claim is None:
                continue
            claims_in_group.append(claim)
            shared_terms_lists.append(row["shared_terms"].split(";") if row["shared_terms"] else [])

        if not claims_in_group:
            continue

        excerpt = build_excerpt(candidate_text, shared_terms_lists)
        batches = dynamic_batches(claims_in_group, excerpt)
        print(f"{origin_id} -> {candidate_id}: {len(claims_in_group)} claims, {len(batches)} batch(es)")

        for batch_idx, batch in enumerate(batches, start=1):
            run_id = f"{origin_id}__{candidate_id}__b{batch_idx}"
            cached_path = run_dir / f"{run_id}.json"

            if cached_path.exists():
                # Resume-safe: a prior run already got a real response for
                # this exact batch (saved before the crash/kill happened),
                # so replay it instead of burning another LLM call.
                cached = json.loads(cached_path.read_text())
                response = cached["raw_response"]
                content, reasoning = extract_message_text(response)
                verdicts, parse_error = parse_verdict_array(content)
                print(f"  batch {batch_idx}: {len(verdicts)} verdicts (cached)" + (f" (parse_error: {parse_error})" if parse_error else ""))
            else:
                claims_json = json.dumps(
                    [{"claim_id": c["claim_id"], "claim": c["claim_text"]} for c in batch], indent=2
                )
                prompt = PROMPT_TEMPLATE.format(
                    origin_source_url=registry[origin_id]["url"],
                    claims_json_list=claims_json,
                    candidate_source_url=registry[candidate_id]["url"],
                    candidate_document_text=excerpt,
                )
                est_needed = estimate_tokens(prompt) + OUTPUT_MAX_TOKENS
                wait_for_token_budget(est_needed)
                try:
                    response = call_groq(
                        [{"role": "user", "content": prompt}],
                        reasoning_effort="medium",
                        max_tokens=OUTPUT_MAX_TOKENS,
                    )
                except RequestTooLargeError as e:
                    print(f"  batch {batch_idx}: REQUEST_TOO_LARGE ({len(batch)} claims) -- {e}")
                    continue

                content, reasoning = extract_message_text(response)
                verdicts, parse_error = parse_verdict_array(content)

                cached_path.write_text(
                    json.dumps(
                        {
                            "origin_source_id": origin_id,
                            "candidate_source_id": candidate_id,
                            "batch_index": batch_idx,
                            "n_claims_in_batch": len(batch),
                            "usage": call_budget_used(response),
                            "parse_error": parse_error,
                            "raw_response": response,
                        },
                        indent=2,
                    )
                )
                print(f"  batch {batch_idx}: {len(verdicts)} verdicts parsed" + (f" (parse_error: {parse_error})" if parse_error else ""))

            for v in verdicts:
                claim_id = v.get("claim_id", "")
                verdict = v.get("verdict", "")
                quote = v.get("quote", "")
                if verdict not in CORROBORATION_TYPES:
                    verdict = "NOT_MENTIONED"
                quote_verified = bool(quote) and quote in excerpt
                is_derivative_by_link = any(
                    r["claim_id"] == claim_id and r["is_derivative_by_link"] == "True" for r in rows
                )
                all_results.append(
                    {
                        "claim_id": claim_id,
                        "candidate_source_id": candidate_id,
                        "corroboration_type": verdict,
                        "quote": quote,
                        "quote_verified_in_excerpt": quote_verified,
                        "reason": v.get("reason", ""),
                        "is_derivative_by_link": is_derivative_by_link,
                    }
                )

        flush_results()

    print(f"\nwrote {out_path}: {len(all_results)} corroboration verdicts")


if __name__ == "__main__":
    run_corroboration()
