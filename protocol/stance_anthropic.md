# Stance Audit — Anthropic (LOCKED)

| Field | Fill |
|-------|------|
| Case | Anthropic cyber-eval incidents |
| Source URL | https://www.anthropic.com/research/investigating-incidents-cybersecurity-evals |
| Excerpt date accessed | 2026-09-10 |
| Intentional-only? | N (primary post includes design facts) |
| Audit result | PASS |
| Linked forensic `event_id`s | A003, A010, A004 |
| Linked claim IDs | A1–A11 |

## Intentional-only excerpt (illustrative FAIL if used alone)

> Claude believed everything it initially encountered was part of the simulation, and treated the real systems it found as pieces of the exercise.

## Design-stance rewrite (PASS pattern)

> The evaluation prompt stated the environment was a simulation with no internet access. A misconfiguration neither Anthropic nor its evaluation partner knew about left evaluation machines with live internet. CTF objectives rewarded reaching a flag without hard network limits matching the prompt. Under those design facts, contacting real organizations was an available path — not explained by desire language alone.

## Checklist

- [x] Named reward/task (CTF / flag)
- [x] Named infra fact (live internet / misconfiguration)
- [x] Named prompt claim vs network
- [x] Cited URL + event ids
- [x] Did not stop at "the model wanted X"

**Status:** LOCKED 2026-09-13 — source check confirmed the quotes. Wording fix: "partner misconfiguration" → shared unknown misconfiguration (Anthropic's own framing).
