#!/usr/bin/env python3
"""Claims-based equivalent of forensics/out/metrics_*.json, for the Results table.

forensics/out/metrics_{case}.json reports n_events/n_actors/epistemic counts per
case from the JSONL events. This script reports the analogous n_claims/n_sources/
epistemic counts per case from claims/, plus a corroboration-strength summary the
event-based metrics never had (independent_corroboration_count has no equivalent
in the JSONL schema).

Note the epistemic vocabulary differs: JSONL events use confirmed/asserted/
reconstructed/unknown; ClaimRecord's epistemic_hint uses confirmed/asserted/unknown
only (no "reconstructed" -- that's an event-only concept). Report tables switching
to this source should say so explicitly, not silently drop a column.

Output: protocol/out/claims_case_metrics.json (one entry per case) and a
paste-ready markdown table at protocol/out/claims_case_metrics.md.
"""

from __future__ import annotations

import json
from pathlib import Path

PROTO = Path(__file__).resolve().parents[1]
CLAIMS = PROTO.parent / "claims"
REGISTRY_PATH = CLAIMS / "data" / "source_registry.json"
EXTRACTED_PATH = CLAIMS / "out" / "claims_extracted.jsonl"
SCORED_PATH = CLAIMS / "out" / "claims_scored.jsonl"
BACKFILL_PATH = CLAIMS / "out.backfill-08-09-15" / "claims_extracted.jsonl"
OUT = PROTO / "out"

CANONICAL_CASES = ["openai_hf", "anthropic", "hf_space_representative", "openrouter", "dsewiki"]
CASE_ALIASES = {"openrouter_warning": "openrouter"}


def load_claims_by_case() -> dict[str, list[dict]]:
    registry = {}
    if REGISTRY_PATH.exists():
        for e in json.loads(REGISTRY_PATH.read_text()):
            registry[e["source_id"]] = [CASE_ALIASES.get(c, c) for c in e.get("cases", [])]

    merged: dict[str, dict] = {}
    for path in (EXTRACTED_PATH, BACKFILL_PATH, SCORED_PATH):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            merged[c["claim_id"]] = c

    by_case: dict[str, list[dict]] = {c: [] for c in CANONICAL_CASES}
    for claim in merged.values():
        for case in registry.get(claim.get("source_id"), []):
            if case in by_case:
                by_case[case].append(claim)
    return by_case


def metrics_for_case(claims: list[dict]) -> dict:
    epistemic: dict[str, int] = {}
    for c in claims:
        e = c.get("epistemic_hint", "unknown")
        epistemic[e] = epistemic.get(e, 0) + 1
    sources = sorted({c.get("source_id") for c in claims if c.get("source_id")})
    corroborated = [c for c in claims if (c.get("independent_corroboration_count") or 0) >= 1]
    corroborated_ge2 = [c for c in claims if (c.get("independent_corroboration_count") or 0) >= 2]
    return {
        "n_claims": len(claims),
        "n_sources": len(sources),
        "source_ids": sources,
        "epistemic": epistemic,
        "n_independently_corroborated_ge1": len(corroborated),
        "n_independently_corroborated_ge2": len(corroborated_ge2),
    }


def main() -> None:
    by_case = load_claims_by_case()
    all_metrics = {case: metrics_for_case(claims) for case, claims in by_case.items()}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claims_case_metrics.json").write_text(json.dumps(all_metrics, indent=2))

    lines = [
        "# Claims-based case metrics (DRAFT)",
        "",
        "Analogous to `forensics/out/metrics_*.json`, computed from `claims/` instead of "
        "JSONL events. Epistemic vocabulary here is confirmed/asserted/unknown (no "
        "\"reconstructed\" -- that's event-only). Corroboration columns have no JSONL "
        "equivalent.",
        "",
        "| Case | Claims | Sources | Confirmed | Asserted | Unknown | Corroborated (>=1) | Corroborated (>=2) |",
        "|------|-------:|--------:|----------:|---------:|--------:|--------------------:|--------------------:|",
    ]
    totals = {"n_claims": 0, "confirmed": 0, "asserted": 0, "unknown": 0, "ge1": 0, "ge2": 0}
    for case in CANONICAL_CASES:
        m = all_metrics[case]
        ep = m["epistemic"]
        confirmed, asserted, unknown = ep.get("confirmed", 0), ep.get("asserted", 0), ep.get("unknown", 0)
        lines.append(
            f"| {case} | {m['n_claims']} | {m['n_sources']} | {confirmed} | {asserted} | "
            f"{unknown} | {m['n_independently_corroborated_ge1']} | {m['n_independently_corroborated_ge2']} |"
        )
        totals["n_claims"] += m["n_claims"]
        totals["confirmed"] += confirmed
        totals["asserted"] += asserted
        totals["unknown"] += unknown
        totals["ge1"] += m["n_independently_corroborated_ge1"]
        totals["ge2"] += m["n_independently_corroborated_ge2"]
    lines.append(
        f"| **Total** | **{totals['n_claims']}** | — | **{totals['confirmed']}** | "
        f"**{totals['asserted']}** | **{totals['unknown']}** | **{totals['ge1']}** | **{totals['ge2']}** |"
    )
    (OUT / "claims_case_metrics.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT / 'claims_case_metrics.json'}")
    print(f"wrote {OUT / 'claims_case_metrics.md'}")


if __name__ == "__main__":
    main()
