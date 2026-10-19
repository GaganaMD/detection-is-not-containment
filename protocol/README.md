# protocol/

> **Two things live in this folder.** Upper-case `B2_*`, `C_*`, `D_*`, `E_*`, `F_*` files are the frozen experiment protocols used by `pilot/` and `hermes_phase_f/` (hash-checked; do not edit). Everything else here is the checklist protocol from the report (section 3.2, appendix A.1, A.3, A.4, A.8).

| Path | Role |
|------|------|
| `sim_real_rubric.md` | SR-1..SR-8 questions, their grounding (appendix A.3), and why SR-9..SR-16 were not adopted |
| `stance-audit-template.md`, `stance_<case>.md` | Stance Audit (SA-1) template and one human-authored sheet per case |
| `src/score_checklist_from_claims.py` | Heuristic SR-1..SR-6 scorer over `../claims/out`; SR-7 is pulled from the stance sheets |
| `src/llm_audit_from_claims.py` | Independent local-LLM re-read of SR-1..SR-7 + SA-1, diffed against the heuristic (needs Ollama) |
| `src/claims_case_metrics.py` | Per-case claim/source/epistemic/corroboration counts for the results table |
| `src/stance_tag.py` | Light intentional-vs-design tagger for an excerpt |
| `checklist_scores_from_claims/` | Heuristic sheets per case (appendix A.4). These include human lock notes, so re-running the scorer will not reproduce them byte for byte |
| `out/` | `claims_case_metrics.*`, `llm_audit_from_claims_report.*` |

Cases: `openai_hf`, `anthropic`, `openrouter`, `dsewiki`, `hf_space_representative`. SR-8 is always UNKNOWN (no public chain-of-thought transcript). Sheets are drafts, not independently validated.
