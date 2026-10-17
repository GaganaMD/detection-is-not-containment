#!/usr/bin/env python3
"""Step 4: roll up raw (claim, candidate-source) verdict rows from
corroborate.py into per-claim counts on ClaimRecord.

Deliberately mechanical -- no source-reliability weighting, no
information_credibility/Admiralty score. Independence is defined the same
way the ad-hoc table in findings/05-full-run-results.md used it: a
candidate only counts toward independent_corroboration_count if its verdict
is DIRECT/CONCEPTUAL *and* prefilter.py's deterministic link-check did not
find it citing/linking the origin source.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAIMS_ROOT = HERE.parent
# override to run two backends into separate output dirs for an A/B comparison
OUT_DIR = Path(os.environ.get("CLAIMS_OUT_DIR", str(CLAIMS_ROOT / "out")))

POSITIVE_VERDICTS = {"DIRECT", "CONCEPTUAL"}


def load_claims(path: Path) -> dict[str, dict]:
    claims = {}
    for line in path.read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            claims[c["claim_id"]] = c
    return claims


def load_results(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def aggregate(claims_by_id: dict[str, dict], results: list[dict]) -> dict[str, dict]:
    """Returns claim_id -> the six rollup fields, for every claim in
    claims_by_id (including claims with zero result rows -- e.g. SRC09's
    skipped extraction, or claims the corroboration step never reached)."""
    by_claim: dict[str, list[dict]] = {cid: [] for cid in claims_by_id}
    for row in results:
        cid = row["claim_id"]
        if cid in by_claim:
            by_claim[cid].append(row)

    out: dict[str, dict] = {}
    for cid, rows in by_claim.items():
        corroborating: set[str] = set()
        independent: set[str] = set()
        derivative: set[str] = set()
        contradicting: set[str] = set()

        for row in rows:
            verdict = row["corroboration_type"]
            candidate = row["candidate_source_id"]
            linked = row["is_derivative_by_link"] == "True"
            if verdict in POSITIVE_VERDICTS:
                corroborating.add(candidate)
                if not linked:
                    independent.add(candidate)
            elif verdict == "DERIVATIVE":
                derivative.add(candidate)
            elif verdict == "CONTRADICTS":
                contradicting.add(candidate)

        out[cid] = {
            "corroborating_sources": sorted(corroborating),
            "independent_corroborating_sources": sorted(independent),
            "derivative_sources": sorted(derivative),
            "contradicting_sources": sorted(contradicting),
            "corroboration_count": len(corroborating),
            "independent_corroboration_count": len(independent),
        }
    return out


def write_scored_jsonl(path: Path, claims_by_id: dict[str, dict], scores: dict[str, dict]) -> None:
    with path.open("w") as f:
        for cid, claim in claims_by_id.items():
            record = {**claim, **scores[cid]}
            f.write(json.dumps(record) + "\n")


def write_summary_csv(path: Path, claims_by_id: dict[str, dict], scores: dict[str, dict]) -> None:
    rows = []
    for cid, claim in claims_by_id.items():
        s = scores[cid]
        rows.append(
            {
                "claim_id": cid,
                "source_id": claim["source_id"],
                "claim_text": claim["claim_text"],
                "corroboration_count": s["corroboration_count"],
                "independent_corroboration_count": s["independent_corroboration_count"],
                "corroborating_sources": ";".join(s["corroborating_sources"]),
                "independent_corroborating_sources": ";".join(s["independent_corroborating_sources"]),
                "derivative_sources": ";".join(s["derivative_sources"]),
                "contradicting_sources": ";".join(s["contradicting_sources"]),
            }
        )
    rows.sort(key=lambda r: r["independent_corroboration_count"], reverse=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    claims_path = OUT_DIR / "claims_extracted.jsonl"
    results_path = OUT_DIR / "corroboration_results.csv"
    if not claims_path.exists() or not results_path.exists():
        print("run extract_claims.py and corroborate.py first")
        return

    claims_by_id = load_claims(claims_path)
    results = load_results(results_path)
    scores = aggregate(claims_by_id, results)

    scored_path = OUT_DIR / "claims_scored.jsonl"
    summary_path = OUT_DIR / "claims_scored_summary.csv"
    write_scored_jsonl(scored_path, claims_by_id, scores)
    write_summary_csv(summary_path, claims_by_id, scores)

    n_ge1 = sum(1 for s in scores.values() if s["independent_corroboration_count"] >= 1)
    n_ge2 = sum(1 for s in scores.values() if s["independent_corroboration_count"] >= 2)
    n_contradicted = sum(1 for s in scores.values() if s["contradicting_sources"])
    print(f"wrote {scored_path}: {len(scores)} claims scored")
    print(f"wrote {summary_path}")
    print(f"{n_ge1} claims with independent_corroboration_count >= 1")
    print(f"{n_ge2} claims with independent_corroboration_count >= 2")
    print(f"{n_contradicted} claims with >=1 contradicting source")


if __name__ == "__main__":
    main()
