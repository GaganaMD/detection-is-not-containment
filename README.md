# Detection Is Not Containment

A local, deterministic AI-control research artifact about a basic but often-missed distinction:

> A monitor detecting a problem eventually does not establish that an intervention could still prevent the problem.

This repository measures monitor evidence and threshold crossings over trajectory prefixes, compares them to an independently frozen safety boundary, and then replays a matched authority-revocation intervention. The empirical setting is deliberately narrow: a synthetic authorization-controlled delivery environment, local Qwen monitors, fixed prompts, fixed inputs, and deterministic/cached evaluation where stated.

This repository accompanies the report *Detection Is Not Containment* (Gagana M D, Kaustubh Gupta, Maria Ines; Apart Research AI Incident Response Sprint). The report has three parts: a public-source **forensics** pipeline over five AI incidents (`forensics/`, `claims/`), a **protocol** that scores those cases on a sim/real checklist (`protocol/`), and the controlled monitoring **experiment** described in the rest of this README (`pilot/`, `hermes_phase_f/`, `results/`). The experiment does not read the forensics or protocol inputs.

## Extension in progress: human-deadline oversight

The `oversight/` package scales the monitoring experiment from one fixture to 54 matched attack/benign pairs (6 task types x 3 identifier styles x 3 intervention margins), adds repeated sampling, and tests whether a human or LLM overseer can make the revoke-or-allow decision before the last-safe point. The design and hypotheses were pre-registered before any data: [`docs/HUMAN_DEADLINE_PREREGISTRATION.md`](docs/HUMAN_DEADLINE_PREREGISTRATION.md). Runbook: [`oversight/README.md`](oversight/README.md).

Checklist scoring was also revised after review: a control that no public source mentions is now `NOT_DISCLOSED` rather than `FAIL` (see `protocol/sim_real_rubric.md`).

![Evidence arrives differently across monitor views](figures/fig1.png)

## What the project shows — and does not show

### Supported in this artifact

1. **Timing is observable.** For the primary neutral attack (A2), the grounded view first received relevant authorization evidence at sequence 37. The frozen monitor crossed its benign-control-calibrated threshold at sequence 37; the last safe intervention point was sequence 38. This gives utilization delay 0 and intervention margin +1.
2. **A closed-loop intervention can prevent the effect in the toy environment.** In the matched F1 replay, a frozen score crossing at sequence 37 revokes the confirmation capability. The same later confirmation is attempted, rejected by the authoritative environment, and the prohibited effect is absent.
3. **Representation instability can become a real control cost.** In Phase E, only 8/12 semantics-preserving identifier assignments retained correct paired threshold decisions, and only 3/12 were strictly control-ready. In the F3 replay, a representation-induced benign crossing revoked legitimate authority and caused task failure.

### Not established

- General monitoring, containment, or control performance.
- Robustness beyond one synthetic environment, fixed prompt/model settings, single deterministic draws, or sampled identifier transformations.
- Chain-of-thought faithfulness. The A1 result is explicitly treated as sensitivity to externalized wording, not evidence that CoT is faithful.
- Claims about unfinished B2/B2-R work. Its frozen protocol lineage and the B2-R cache baseline are retained solely because Phases C/F validate antecedent integrity byte-for-byte; they are not analyzed or presented as completed results.

![Representation robustness is conditional, not assumed](figures/fig2.png)

## Headline results

| Question | Result | Interpretation |
|---|---:|---|
| Primary B1.3 run | 690 logical prefix evaluations; 119/119 unique local calls valid | Exact-input reuse is explicit and auditable. |
| Calibration | Threshold 51; 0/12 control trajectory false positives | Threshold was chosen from controls, not attacks. |
| A2 grounded timing | information available 37; detected 37; safe boundary 38 | Detection was timely by one event in this fixture. |
| Phase C relational telemetry | G2: attack 100 vs benign 0 at seq 37 | A visible authorization relation was sufficient in this tested representation. |
| Phase E invariance | 8/12 semantic decision invariance; 3/12 strict control-ready invariance | The signal is representation-conditional. |
| Phase F closed loop | F1 attack prevented; F3 benign task disrupted | A score can produce both prevention and harmful false intervention. |

![Closed-loop intervention changes environment authority, not the actor history](figures/main/fig3_closed_loop_intervention.png)

## Forensics and protocol results

**Forensics.** Claims were extracted with a local `qwen2.5:14b-instruct-q4_K_M` (Ollama), each with a verbatim quote and an epistemic tag, then cross-checked against the other sources (a link-based filter separates independent corroboration from citation). 679 claims across five cases:

| Case | Claims | Sources |
|---|---:|---:|
| OpenAI → Hugging Face | 494 | 8 |
| DseWiki | 101 | 1 |
| OpenRouter | 39 | 2 |
| Anthropic | 23 | 1 |
| Hugging Face Space replay | 22 | 1 |

Four of the five cases rest on one or two sources, so most of their claims are single-sourced.

**Protocol.** An 8-item sim/real checklist (SR-1..SR-8) plus a Stance Audit (SA-1) was scored per case from the claims:

- SR-1 (internet actually blocked) FAILs on every case with enough evidence to score: sources describe a residual path to the public internet.
- SR-4 (isolation proven before the run) and SR-6 (canaries trip an alarm) are NOT_DISCLOSED on all five cases: no public source says whether these controls existed. An earlier draft scored this silence as FAIL; that rule was removed after review, because absence of disclosure is not evidence that a control was absent.
- SR-7 and SA-1 (does the postmortem name the design, not just what the model wanted) PASS on the four well-documented cases.
- SR-8 (evaluation-awareness reasoning checked) stays UNKNOWN: no public source contains a chain-of-thought transcript.
- An independent LLM audit agrees with the heuristic scorer on 22 of 40 items (55%), and 2 of 8 (25%) on the largest case. The checklist is a draft, not a validated instrument.

Per-case sheets are in `protocol/checklist_scores_from_claims/`; counts and audit output are in `protocol/out/`. Page snapshots are not shipped (third-party content): fetch them with `forensics/sources/fetch_snapshots.py` to re-run extraction. Reproduce the deterministic parts with:

```bash
python3 protocol/src/claims_case_metrics.py
(cd claims && python3 -m unittest discover -s tests)
```

## Design in one page

The same canonical trajectory is projected into three monitor-visible views:

- `M_ACTION`: actions and tool observations only.
- `M_COT_ACTION`: action view plus externalized reasoning.
- `M_GROUNDED`: action/reasoning plus environment-issued authorization telemetry.

For each prefix, the study records:

- `information_available_seq`: first prefix where the frozen oracle says relevant evidence exists;
- `first_detection_seq`: first monitor score at or above the frozen threshold;
- `monitor_utilization_delay = first_detection_seq - information_available_seq`;
- `last_safe_intervention_seq`: final blockable point before the prohibited effect; and
- `intervention_margin = last_safe_intervention_seq - first_detection_seq`.

The safety oracle, monitor prompt, input serialization, and thresholding protocol are separated. The oracle does not access the monitor output; the controller does not rewrite the actor’s subsequent action attempt.

## Repository map

```text
pilot/                       Phase A/A.5, B1.3, C, D, and E implementation
hermes_phase_f/              deterministic cached-decision closed-loop replay
results/                     released CSV/JSON/JSONL evidence for included phases
docs/                        protocols, freezes, phase results, limits, figure captions
protocol/                    frozen condition files, manifests, and validation reports
figures/main/                three judge-facing explanatory PNGs
figures/supporting/          timing and outcome supporting figures
tests/                       deterministic apparatus and protocol tests
scripts/verify_release.py   read-only integrity and release-layout verification
claims/                      claim extraction, link prefilter, corroboration, aggregation (src/, tests/, out/)
forensics/                   source manifests (URLs + SHA-256) and fetch scripts for the 20 public sources
protocol/                    frozen experiment conditions (upper-case files) plus the sim/real checklist: rubric, stance sheets, scorers, per-case sheets
```

## Reproduce and verify

### Requirements

- Python 3.10+.
- No Python package installation is required for verification; the released code uses the standard library.
- The primary inference artifacts were generated locally using Ollama's native API with `qwen3:14b`, temperature `0`, seed `424242`. A local model is **not** required to inspect results, run deterministic tests, or validate the Phase F cached replay.

### Safe, read-only verification

Run from the repository root:

```bash
python scripts/verify_release.py
python -m unittest discover -s tests -v
python -m hermes_phase_f.pilot.validate_phase_f
```

These commands do not call a model. `verify_release.py` checks the frozen A.5 oracle-body hash and frozen monitor-prompt hash, checks expected released structure, and verifies that the six explanatory PNGs are present without decoding or transforming them.

### Important execution boundary

Do **not** run `python -m pilot.run_phase_b13 --run` against the released results directory. It is an inference runner and appends to the immutable JSONL call log. The public release includes the completed B1.3 records for audit; normal review should use the read-only checks above. Any new inference should occur in a separate, versioned run directory and be reported as a new experiment, not as a reproduction of this frozen result.

## Evidence and interpretation

- **Primary synthesis:** [`docs/APART_RESEARCH_SYNTHESIS.md`](docs/APART_RESEARCH_SYNTHESIS.md)
- **Frozen A.5 evidence oracle:** [`docs/ORACLE_FREEZE_A5.md`](docs/ORACLE_FREEZE_A5.md)
- **B1.3 full prefix result:** [`docs/PHASE_B13_RESULTS.md`](docs/PHASE_B13_RESULTS.md)
- **Relational-evidence ablation:** [`docs/PHASE_C_RESULTS.md`](docs/PHASE_C_RESULTS.md)
- **Semantic counterfactuals:** [`docs/PHASE_D_RESULTS.md`](docs/PHASE_D_RESULTS.md)
- **Identifier invariance diagnostic:** [`docs/PHASE_E_RESULTS.md`](docs/PHASE_E_RESULTS.md)
- **Closed-loop replay:** [`docs/PHASE_F_RESULTS.md`](docs/PHASE_F_RESULTS.md)
- **Exact figure provenance/captions:** [`docs/FIGURE_DATA_AUDIT.json`](docs/FIGURE_DATA_AUDIT.json) and [`docs/PAPER_CAPTIONS.md`](docs/PAPER_CAPTIONS.md)

## Integrity anchors

| Frozen item | SHA-256 |
|---|---|
| A.5 oracle rule body | `83141b61abf6c95ad2afa6bddea72e74ca59f79aae32f41fd04cf3d17e37b93d` |
| B1 monitor prompt | `d6bbb910488951d4daad76f80d140c88ba134b1b6984df2b9ecfba8d2b4b7b4a` |

The primary B1.3 monitor used local Ollama native API (`http://127.0.0.1:11434/api/generate`), `qwen3:14b`, model digest `bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8`, temperature 0, seed 424242, and a 90-second hard timeout. See the phase result documents for exact scope and all limitations.

## License

MIT. See [LICENSE](LICENSE).
