# Sources

Frozen local snapshots of every source cited across `forensics/data/incident_*.jsonl`
(plus 5 Related-Work sources), hashed for provenance. Backs two consumers:
`forensics/src/check_event_grounding.py` (does an event's claim actually appear
in its cited source?) and `claims/` (the cross-source corroboration pipeline).

## Layout

| Path | Role |
|------|------|
| `raw/*.html` | All 20 sources, one file per source, named `{slug}.html` (slug = `source_registry.json`'s `slug` field) |
| `manifest.json` | Fetch record per source cited in `forensics/data/*.jsonl`: url, slug, status, SHA-256, fetch timestamp |
| `extra_sources_manifest.json` | Same, for the 5 Related-Work sources not cited by any event |
| `fetch_snapshots.py` | Re-fetches + re-hashes every `manifest.json` source (stdlib `urllib` only) |
| `fetch_extra_sources.py` | Same, for the `extra_sources_manifest.json` list |

## Manual-fallback sources (2 of 20)

Two sources — Boyd Kane's two LessWrong posts — return `403`/`429` to a plain
scripted fetch (bot detection a stdlib HTTP client trips). Everything else here
is a real raw-HTML fetch with a SHA-256 in `manifest.json`; these two are not:

| File | Source | Captured |
|------|--------|----------|
| `raw/www_lesswrong_com_posts_fBLDaAKzigo65eJn7_public_evidence_of_the_openai_huggingface_ai_attack.html` | [post 1](https://www.lesswrong.com/posts/fBLDaAKzigo65eJn7/public-evidence-of-the-openai-huggingface-ai-attack) | 2026-09-11, tool-mediated |
| `raw/www_lesswrong_com_posts_pok3KtAGApwvCBndf_further_public_evidence_of_the_openai_huggingface_attack.html` | [post 2](https://www.lesswrong.com/posts/pok3KtAGApwvCBndf/further-public-evidence-of-the-openai-huggingface-attack) | 2026-09-11, tool-mediated |

**What these actually are:** tool-mediated extractions (an agent's web-fetch
capability, asked for verbatim content but returned a structured summary, not
raw HTML) — not the same evidentiary strength as the 18 raw-HTML snapshots.
Wrapped in a trivial `<html><body><pre>` shell here only so every source in
`raw/` shares one file extension; there is no real markup inside, and
`manifest.json` marks both `status: "FETCH_FAILED"` so downstream code (the
`has_manual_fallback` field in `claims/data/source_registry.json`, and the
`is_fallback` flag in `check_event_grounding.py`) keeps treating them as
weaker-tier evidence rather than silently upgrading them once the extension
looks the same as everything else. Disclosed, not hidden: treat these two as
a weaker link in the citation chain until someone re-captures them with a
real browser session and replaces the fallback with a proper raw snapshot.

### Note on scope (read before extending the JSONL)

Post 2's extraction surfaced additional named entities beyond what's currently
in `forensics/data/incident_openai_hf.jsonl` (E030–E033): further account
names (`user-qaiocbhg`, `user-unhrdtnl`, `user-lzathslk`), a repo
(`huggingchat/papers-content`), and C2 protocol specifics (RSA-signed
channels, XOR/SHA-256 keystreams, a `DDSE1` dataset-naming marker). These were
deliberately not added as new events — verifying/reproducing what's already
there was in scope, expanding the incident record was not, and C2 protocol
mechanics sit closer to the dual-use line than the phase/actor/target-level
facts already in the JSONL (see `../../docs/DUAL_USE.md`). Flagging for a human
decision, not adding unilaterally.

## Adding a new source

1. Register it in `claims/data/source_registry.json`: `{source_id, url, slug,
   has_manual_fallback}` — `slug` must match the filename you add below.
2. Get the text into `raw/{slug}.html`:
   - Scriptable fetch: add `(url, note)` to `fetch_extra_sources.py`'s
     `EXTRA_SOURCES` list and run it.
   - Blocked site / non-HTML: set `has_manual_fallback: true`, hand-capture
     the text, wrap it in `<html><body><pre>...</pre></body></html>`, save as
     `raw/{slug}.html`.

No separate fallback-filename map to maintain — `load_raw_html()` /
`load_source_text()` / `load_snapshots()` all key off `slug` alone now.
