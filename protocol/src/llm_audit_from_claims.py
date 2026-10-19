#!/usr/bin/env python3
"""LLM-audited cross-check for the Sim/Real checklist (SR-1..SR-7) and Stance
Audit (SA-1), reading `claims/` corroboration data instead of `forensics/` JSONL
events.

Mirrors `protocol/src/llm_audit.py`'s structure and Ollama call pattern exactly,
but embeds claim records (claim_id, source_id, epistemic_hint, corroboration_count,
claim_text, quote) in the prompt instead of forensic events. Diffs against
`protocol/checklist_scores_from_claims/*.md` (the claims-based deterministic scorer's
output) instead of the event-based `protocol/checklist_scores/*.md`. Does NOT touch
`llm_audit.py`, anything under `forensics/`, or the original `protocol/out/
llm_audit_report.*` files -- writes to `protocol/out/llm_audit_from_claims_report.*`.

Requires a local Ollama server with a model pulled:
    ollama pull qwen2.5:14b-instruct-q4_K_M
    ollama serve   # if not already running

Usage:
    python3 llm_audit_from_claims.py [--model MODEL] [--cases openai_hf,anthropic,...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROTO = Path(__file__).resolve().parents[1]
CLAIMS = PROTO.parent / "claims"
REGISTRY_PATH = CLAIMS / "data" / "source_registry.json"
EXTRACTED_PATH = CLAIMS / "out" / "claims_extracted.jsonl"
SCORED_PATH = CLAIMS / "out" / "claims_scored.jsonl"
# ponytail: same one-off backfill merge as score_checklist_from_claims.py -- see
# that file's comment. Safe to remove once claims_extracted.jsonl naturally covers
# SRC08/09/15 itself.
BACKFILL_PATH = CLAIMS / "out.backfill-08-09-15" / "claims_extracted.jsonl"
SCORES_FROM_CLAIMS = PROTO / "checklist_scores_from_claims"
OUT = PROTO / "out"

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:14b-instruct-q4_K_M"

SR_IDS = [f"SR-{i}" for i in range(1, 8)]

CANONICAL_CASES = ["openai_hf", "anthropic", "openrouter", "dsewiki", "hf_space_representative"]
# Registry spells this case "openrouter_warning"; score_checklist.py,
# score_checklist_from_claims.py, and stance_openrouter.md all use "openrouter".
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


def call_ollama(model: str, prompt: str) -> dict:
    # ponytail: claims prompts run far larger than the event-based original's (a
    # case can carry hundreds of claims vs. a handful of events) -- bump num_ctx and
    # the timeout rather than building a chunking/map-reduce system. Ceiling: this
    # comfortably covers today's largest case (~488 claims, ~30k tokens); a case
    # needing more context than num_ctx allows would need real chunking.
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_ctx": 32768},
        }
    ).encode()
    req = urllib.request.Request(
        OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            body = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise SystemExit(
            f"Could not reach Ollama at {OLLAMA_URL} ({e}).\n"
            f"Start it with `ollama serve` and make sure `{model}` is pulled "
            f"(`ollama pull {model}`)."
        )
    return json.loads(body["response"])


def build_prompt(case: str, claims: list[dict], sr_rubric: str, sa_template: str) -> str:
    claims_text = "\n".join(
        f"- {c['claim_id']} | source={c.get('source_id')} | "
        f"epistemic={c.get('epistemic_hint')} | "
        f"corroboration={c.get('corroboration_count', '?')}/{c.get('independent_corroboration_count', '?')} | "
        f'claim="{c.get("claim_text", "")}" | quote="{(c.get("quote") or "")[:200]}"'
        for c in claims
    )
    return f"""You are independently applying a fixed incident-review checklist to
extracted factual claims. Do NOT invent new questions or change wording -- only
answer the questions exactly as given, using only the evidence below. If the
claims do not contain enough information to answer, say UNKNOWN rather than
guessing.

## SR-1..SR-7 checklist (verbatim)
{sr_rubric}

## Stance Audit SA-1 (verbatim)
{sa_template}

## Extracted claims for case "{case}"
{claims_text}

## Your task
For each of SR-1 through SR-7, answer PASS, FAIL, or UNKNOWN based only on the
claims above, and cite the claim_id(s) you used. For SA-1, read the claim texts
as if they were postmortem sentences: tag the overall case as "I"
(intentional-only), "D" (has design-stance facts), or "I+D", then give a
PASS/FAIL per the SA-1 scoring rule (FAIL if root cause is intentional-only
with no material design facts), citing claim_id(s).

Respond with ONLY a JSON object, no prose outside it, in exactly this shape:
{{
  "case": "{case}",
  "sr_answers": {{
    "SR-1": {{"result": "PASS|FAIL|UNKNOWN", "claim_ids": ["..."], "reasoning": "one sentence"}},
    "SR-2": {{"result": "...", "claim_ids": ["..."], "reasoning": "..."}},
    "SR-3": {{"result": "...", "claim_ids": ["..."], "reasoning": "..."}},
    "SR-4": {{"result": "...", "claim_ids": ["..."], "reasoning": "..."}},
    "SR-5": {{"result": "...", "claim_ids": ["..."], "reasoning": "..."}},
    "SR-6": {{"result": "...", "claim_ids": ["..."], "reasoning": "..."}},
    "SR-7": {{"result": "...", "claim_ids": ["..."], "reasoning": "..."}}
  }},
  "sa1": {{"stance": "I|D|I+D", "result": "PASS|FAIL", "claim_ids": ["..."], "reasoning": "one sentence"}}
}}"""


def parse_existing_checklist_from_claims(case: str) -> dict[str, str]:
    path = SCORES_FROM_CLAIMS / f"{case}.md"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\|\s*(SR-\d)\s*\|\s*([A-Za-z ()]+?)\s*\|", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def parse_existing_stance(case: str) -> str | None:
    """Unchanged from llm_audit.py -- Stance sheets are still per-case, not per-pipeline."""
    path = PROTO / f"stance_{case}.md"
    if not path.exists():
        return None
    text = path.read_text()
    m = re.search(r"\|\s*Audit result\s*\|\s*(.+?)\s*\|", text)
    return m.group(1).strip() if m else None


def normalize(s: str | None) -> str:
    if not s:
        return "UNKNOWN"
    s = s.upper()
    if "PASS" in s and "FAIL" in s:
        return "MIXED"
    if "PASS" in s:
        return "PASS"
    if "FAIL" in s:
        return "FAIL"
    if "SEE STANCE" in s:
        return "SEE_STANCE"
    return "UNKNOWN"


def audit_case(model: str, case: str, claims: list[dict], sr_rubric: str, sa_template: str) -> dict:
    prompt = build_prompt(case, claims, sr_rubric, sa_template)
    llm = call_ollama(model, prompt)

    heuristic_sr = parse_existing_checklist_from_claims(case)
    heuristic_sa = parse_existing_stance(case)

    diffs = []
    for sr in SR_IDS:
        llm_ans = llm.get("sr_answers", {}).get(sr, {})
        llm_result = normalize(llm_ans.get("result"))
        heur_raw = heuristic_sr.get(sr)
        heur_result = normalize(heur_raw)
        coverage_gap = heur_raw is None
        agree = coverage_gap or heur_result == llm_result
        diffs.append(
            {
                "id": sr,
                "heuristic": heur_result,
                "heuristic_raw": heur_raw if heur_raw is not None else "no sheet",
                "llm": llm_result,
                "llm_claim_ids": llm_ans.get("claim_ids", []),
                "llm_reasoning": llm_ans.get("reasoning", ""),
                "coverage_gap": coverage_gap,
                "agree": agree,
            }
        )

    sa1 = llm.get("sa1", {})
    sa_llm_result = normalize(sa1.get("result"))
    sa_coverage_gap = heuristic_sa is None
    sa_heur_result = normalize(heuristic_sa)
    sa_diff = {
        "id": "SA-1",
        "heuristic": sa_heur_result,
        "heuristic_raw": heuristic_sa if heuristic_sa is not None else "no sheet",
        "llm": sa_llm_result,
        "llm_stance": sa1.get("stance"),
        "llm_claim_ids": sa1.get("claim_ids", []),
        "llm_reasoning": sa1.get("reasoning", ""),
        "coverage_gap": sa_coverage_gap,
        "agree": sa_coverage_gap or sa_heur_result == sa_llm_result,
    }

    return {"case": case, "n_claims": len(claims), "sr_diffs": diffs, "sa1_diff": sa_diff}


def render_report(results: list[dict], model: str) -> str:
    lines = [
        "# LLM-audited cross-check (from claims) — SR-1..SR-7 + SA-1 (DRAFT)",
        "",
        f"Generated by `protocol/src/llm_audit_from_claims.py` using local model `{model}` "
        "via Ollama, reading `claims/` corroboration data instead of `forensics/` events.",
        "Compares an independent LLM read of the extracted claims against "
        "`protocol/checklist_scores_from_claims/*.md`. **Not human-locked** — "
        "disagreements are prompts for review, not automatic corrections.",
        "",
    ]
    scored = agree = disagree = gaps = 0
    for res in results:
        lines.append(f"## Case: {res['case']} ({res['n_claims']} claims)")
        lines.append("")
        lines.append("| ID | Heuristic sheet | LLM independent read | Status | LLM reasoning |")
        lines.append("|----|------------------|------------------------|--------|----------------|")
        for d in res["sr_diffs"] + [res["sa1_diff"]]:
            if d.get("coverage_gap"):
                gaps += 1
                mark = "GAP (no prior sheet)"
            else:
                scored += 1
                if d["agree"]:
                    agree += 1
                    mark = "agree"
                else:
                    disagree += 1
                    mark = "**DISAGREE**"
            stance = f", stance={d['llm_stance']}" if d["id"] == "SA-1" else ""
            lines.append(
                f"| {d['id']} | {d['heuristic_raw']} | {d['llm']}{stance} "
                f"({', '.join(d['llm_claim_ids']) or '—'}) | {mark} | {d['llm_reasoning']} |"
            )
        lines.append("")
    lines.append(
        f"**Summary: {scored} items had an existing sheet to compare against "
        f"({agree} agreed, {disagree} disagreed, "
        f"{100*agree//scored if scored else 0}% agreement); "
        f"{gaps} items had no prior sheet at all and are now covered for the first time.**"
    )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--cases", default=",".join(CANONICAL_CASES))
    args = ap.parse_args()

    sr_rubric = (PROTO / "sim_real_rubric.md").read_text()
    sa_template = (PROTO / "stance-audit-template.md").read_text()

    by_case = load_claims_by_case()
    requested = [c.strip() for c in args.cases.split(",") if c.strip()]
    results = []
    for case in requested:
        claims = by_case.get(case, [])
        if not claims:
            print(f"skip case with no claims yet: {case}", file=sys.stderr)
            continue
        print(f"auditing {case} ({len(claims)} claims) with {args.model} ...", file=sys.stderr)
        results.append(audit_case(args.model, case, claims, sr_rubric, sa_template))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "llm_audit_from_claims_report.json").write_text(json.dumps(results, indent=2))
    (OUT / "llm_audit_from_claims_report.md").write_text(render_report(results, args.model))
    print(f"wrote {OUT / 'llm_audit_from_claims_report.md'}")
    print(f"wrote {OUT / 'llm_audit_from_claims_report.json'}")


if __name__ == "__main__":
    main()
