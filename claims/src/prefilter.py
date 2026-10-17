#!/usr/bin/env python3
"""Deterministic, zero-LLM-call prefilter + independence flag.

For each claim x every OTHER source, decide (a) is it even worth an LLM
corroboration call (term overlap with the candidate's text), and (b) is the
candidate's raw HTML a citation/link to the claim's origin source (flagged
`is_derivative_by_link=True` -- alongside the LLM's own judgment, not
instead of it, per the plan).

Reuses `extract_terms`/`check_terms`/`html_to_text` from
`forensics/src/check_event_grounding.py` rather than reimplementing --
imported via sys.path injection, same pattern `forensics/src/loader.py`
uses for `events.py`.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CLAIMS_ROOT = HERE.parent
SUBMISSION = CLAIMS_ROOT.parent
FORENSICS = SUBMISSION / "forensics"
SOURCES_RAW = FORENSICS / "sources" / "raw"
# override to run two backends into separate output dirs for an A/B comparison
OUT_DIR = Path(os.environ.get("CLAIMS_OUT_DIR", str(CLAIMS_ROOT / "out")))

sys.path.insert(0, str(FORENSICS / "src"))
from check_event_grounding import extract_terms, check_terms, html_to_text  # noqa: E402

from html_util import strip_html  # noqa: E402


INLINE_DATE_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")


def claim_as_pseudo_event(claim_text: str) -> dict:
    """Adapt a claim into the shape extract_terms() expects (an event dict).
    `extract_terms()` only recognizes dates via the event's separate `ts`
    field, not dates written inline in prose -- but claims will very often
    state a date as part of the claim text itself (e.g. "...on 2026-07-09").
    Lift the FIRST inline ISO date found into `ts` so the date-term logic
    (which also emits short/full month-name variants) fires for claims too,
    not just structured events. Confirmed by a unit test that this matters:
    without it, "2026-05-11" fragments into bare "05"/"11" number terms and
    loses its recognizability as a date."""
    m = INLINE_DATE_RE.search(claim_text)
    ts = m.group(0) if m else ""
    return {"action": claim_text, "target": "", "notes": "", "ts": ts}


def extract_claim_terms(claim_text: str) -> list[str]:
    return extract_terms(claim_as_pseudo_event(claim_text))


def load_raw_html(source_id: str, registry: list[dict]) -> tuple[str, bool] | None:
    """Returns (raw_html_or_markdown, is_html). None if unavailable.

    All 20 sources live as `{slug}.html` under sources/raw/ -- the 2
    manual-fallback captures are wrapped in a trivial HTML shell for a
    consistent extension, not real markup, so `is_html` still keys off
    `has_manual_fallback` (False for them) rather than the file extension:
    `is_derivative_by_link` needs to know there's no real href= to search."""
    row = next((r for r in registry if r["source_id"] == source_id), None)
    if row is None:
        return None
    p = SOURCES_RAW / f"{row['slug']}.html"
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    return (text, not row["has_manual_fallback"])


def is_derivative_by_link(candidate_raw: str, candidate_is_html: bool, home_url: str) -> tuple[bool, str]:
    """Deterministic: does the candidate's RAW (untouched) HTML contain a
    hyperlink or plain-text reference to the home source's URL/domain?
    Must run on raw HTML, not tag-stripped text -- stripping destroys
    href= attributes."""
    if not candidate_is_html:
        # manual_fallback markdown: check plain-text mention of the domain
        domain = urlparse(home_url).netloc
        if domain and domain in candidate_raw:
            return True, f"domain '{domain}' mentioned in text"
        return False, ""

    if home_url in candidate_raw:
        return True, f"exact URL '{home_url}' found in raw HTML"

    domain = urlparse(home_url).netloc
    if domain:
        href_pattern = re.compile(
            r'href=["\'][^"\']*' + re.escape(domain), re.IGNORECASE
        )
        m = href_pattern.search(candidate_raw)
        if m:
            return True, f"href referencing domain '{domain}' found"
    return False, ""


def is_meaningful_match(found_terms: list[str]) -> bool:
    """A bare 1-2 digit number (day-of-month, hour) is not distinctive
    evidence of real content overlap -- it's common enough to coincide
    between almost any two documents both discussing dates in the same
    month. Require at least one term of 3+ characters (a real number, a
    full date, a named entity) before treating a claim/candidate pair as
    worth an LLM corroboration call."""
    return any(len(t) >= 3 for t in found_terms)


def run_prefilter(claims: list[dict], registry: list[dict]) -> list[dict]:
    """claims: list of {claim_id, source_id, claim_text}. Returns list of
    row dicts: claim_id, candidate_source_id, prefilter_pass, shared_terms,
    is_derivative_by_link, derivative_evidence."""
    # cache stripped/raw text per source_id
    text_cache: dict[str, tuple[str, str, bool]] = {}  # source_id -> (raw, stripped_lower_nocommas_text, is_html)

    def get_texts(source_id: str):
        if source_id not in text_cache:
            loaded = load_raw_html(source_id, registry)
            if loaded is None:
                text_cache[source_id] = (None, None, None)
            else:
                raw, is_html = loaded
                if is_html:
                    lower_text = html_to_text(raw.encode("utf-8"))
                else:
                    lower_text = raw.lower()
                text_cache[source_id] = (raw, lower_text, is_html)
        return text_cache[source_id]

    nocomma_re = re.compile(r"(?<=\d),(?=\d)")
    rows = []
    for claim in claims:
        terms = extract_claim_terms(claim["claim_text"])
        for candidate in registry:
            if candidate["source_id"] == claim["source_id"]:
                continue
            raw, lower_text, is_html = get_texts(candidate["source_id"])
            if raw is None:
                continue
            lower_nocommas = nocomma_re.sub("", lower_text)
            found, missing = check_terms(terms, lower_text, lower_nocommas)
            prefilter_pass = is_meaningful_match(found)
            derivative, evidence = is_derivative_by_link(
                raw, is_html, claim.get("source_url", "")
            )
            rows.append(
                {
                    "claim_id": claim["claim_id"],
                    "origin_source_id": claim["source_id"],
                    "candidate_source_id": candidate["source_id"],
                    "prefilter_pass": prefilter_pass,
                    "shared_terms": ";".join(found),
                    "is_derivative_by_link": derivative,
                    "derivative_evidence": evidence,
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--candidates",
        default=None,
        help="comma-separated SRC## ids to restrict CANDIDATE sources to (e.g. the pilot set). "
        "Default = all registered sources. Use this during the pilot so corroboration doesn't "
        "silently balloon into a full 18-source run before the pilot checklist passes.",
    )
    args = ap.parse_args()

    registry = json.loads((CLAIMS_ROOT / "data" / "source_registry.json").read_text())
    if args.candidates:
        wanted = set(args.candidates.split(","))
        registry = [r for r in registry if r["source_id"] in wanted]

    claims_path = OUT_DIR / "claims_extracted.jsonl"
    if not claims_path.exists():
        print(f"no claims yet at {claims_path} -- run extract_claims.py first")
        return
    claims = [json.loads(l) for l in claims_path.read_text().splitlines() if l.strip()]
    if args.candidates:
        claims = [c for c in claims if c["source_id"] in wanted]
    rows = run_prefilter(claims, registry)
    out_path = OUT_DIR / "prefilter_pairs.csv"
    write_csv(out_path, rows)
    n_pass = sum(1 for r in rows if r["prefilter_pass"])
    print(f"wrote {out_path}: {len(rows)} pairs checked, {n_pass} pass prefilter")


if __name__ == "__main__":
    main()
