# Claims / corroboration pipeline (Kaustubh)

For each source cited in the sprint's writeup: extract its factual claims,
then check whether every OTHER source independently confirms, contradicts,
or merely repeats (via citation) each one. The point is to distinguish
"stated once" from "independently corroborated" before a number gets quoted
in the PDF.

Depends on page snapshots fetched by
[`../forensics/sources/`](../forensics/README.md) (not shipped; re-fetch them before steps 1-2). Uses an LLM only for extraction (step 1)
and corroboration judgment (step 3); steps 2 and 4 are pure stdlib, zero
LLM calls, deterministic.

## Flow

1. `src/extract_claims.py` — chunked LLM claim extraction per source (sources
   are chunked against a real measured ~8000-token/minute account cap, not a
   guess) → `out/claims_extracted.jsonl`
2. `src/prefilter.py` — deterministic term-overlap + link-derivative check
   (is candidate B just citing/linking source A?) → `out/prefilter_pairs.csv`
3. `src/corroborate.py` — LLM judgment, batched per (origin, candidate) pair,
   only on pairs the prefilter passed → `out/corroboration_runs/`,
   `out/corroboration_results.csv`
4. `src/aggregate_claims.py` — rolls up verdicts into per-claim corroboration
   counts (mechanical, no reliability weighting) → `out/claims_scored.jsonl`,
   `out/claims_scored_summary.csv`

`src/source_registry.py` assigns/maintains the stable `SRC##` ids in
`data/source_registry.json` (append-only — an id never changes once
assigned, so `claim_id`s stay stable as the source list grows).

## Requirements

Pick one LLM backend (`src/groq_client.py`, `LLM_BACKEND` env var):

| Backend | Setup | Cost/speed |
|---|---|---|
| **Ollama (default)** | `ollama pull qwen2.5:14b-instruct-q4_K_M`, `ollama serve` running | free, local, ~138s/chunk |
| **Groq** | `LLM_BACKEND=groq` + `GROQ_API_KEY` env var (or a `.groq_key` file next to `data/`, chmod 600) | ~4s/chunk, ~8000 tokens/min account cap |

Override the Ollama model/host with `OLLAMA_MODEL` / `OLLAMA_HOST` if you
want to re-check the model choice — see `src/groq_client.py`'s docstring for
the 3-way model comparison that picked qwen2.5:14b over gpt-oss:20b.

## Reproduce

```bash
cd submission/claims
python3 src/extract_claims.py
python3 src/prefilter.py
python3 src/corroborate.py
python3 src/aggregate_claims.py
```

Re-registering sources (only needed after editing the manifests in
`forensics/sources/`):
```bash
python3 src/source_registry.py
```

## Tests

No network, no LLM, no real snapshots needed:
```bash
python3 -m pytest tests/ -q
```

## Layout

| Path | Role |
|------|------|
| `data/source_registry.json` | Stable `SRC##` → url/slug/`has_manual_fallback` map |
| `src/` | Pipeline scripts + `groq_client.py` (LLM backend), `claim_schema.py` (schema), `html_util.py` |
| `out/` | Pipeline outputs (see Flow above) |
| `tests/` | Unit tests, offline |

## Not

A source-reliability or Admiralty-style credibility score — independence is
defined purely as "verdict is DIRECT/CONCEPTUAL AND the deterministic
link-check didn't find it citing the origin," nothing more.
