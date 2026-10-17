# Claims-based case metrics (DRAFT)

Analogous to `forensics/out/metrics_*.json`, computed from `claims/` instead of JSONL events. Epistemic vocabulary here is confirmed/asserted/unknown (no "reconstructed" -- that's event-only). Corroboration columns have no JSONL equivalent.

| Case | Claims | Sources | Confirmed | Asserted | Unknown | Corroborated (>=1) | Corroborated (>=2) |
|------|-------:|--------:|----------:|---------:|--------:|--------------------:|--------------------:|
| openai_hf | 494 | 8 | 344 | 150 | 0 | 7 | 3 |
| anthropic | 23 | 1 | 23 | 0 | 0 | 0 | 0 |
| hf_space_representative | 22 | 1 | 22 | 0 | 0 | 0 | 0 |
| openrouter | 39 | 2 | 39 | 0 | 0 | 0 | 0 |
| dsewiki | 101 | 1 | 100 | 1 | 0 | 1 | 1 |
| **Total** | **679** | — | **528** | **151** | **0** | **8** | **4** |
