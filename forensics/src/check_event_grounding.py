#!/usr/bin/env python3
"""Deterministic, non-LLM grounding check: for every event in every
forensics/data/incident_*.jsonl file, extract distinctive terms from the
event (numbers, named entities/handles, dataset-style paths, key phase
counts) and check whether they actually occur in the frozen snapshot of
that event's cited source_url (../sources/raw/*.html -- includes the two
blocked LessWrong posts, manually captured but wrapped as .html for a
consistent extension; see ../sources/README.md).

Deliberately NOT an LLM judge: this is pure regex + substring matching, so
the same inputs always produce the same output, byte for byte, on any
machine, forever -- no model version drift, no sampling. A "STRONG" verdict
means we found hard textual evidence in the archived source; "WEAK" or
"UNSUPPORTED" does not mean the event is false, it means our (imperfect,
heuristic) term extractor could not automatically confirm it -- those rows
are exactly the ones a human should spot-check before locking a sheet.

Usage:
    python3 check_event_grounding.py
Writes: verification_report.csv, verification_summary.md
"""

from __future__ import annotations

import csv
import glob
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORENSICS = HERE.parent
FORENSICS_DATA = FORENSICS / "data"
SOURCES_RAW = FORENSICS / "sources" / "raw"

# url -> local snapshot text (populated in load_snapshots)
SNAPSHOT_TEXT: dict[str, tuple[str, str, bool]] = {}  # url -> (plain_text, plain_text_no_commas, is_manual_fallback)

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def slugify(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_")
    return s[:120]


def html_to_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text)
    return text.lower()


COMMA_BETWEEN_DIGITS = re.compile(r"(?<=\d),(?=\d)")


def load_snapshots() -> None:
    """All 20 sources now live as `{slug}.html` under sources/raw/ -- the 2
    manual-fallback captures (status FETCH_FAILED, no real fetch) are wrapped
    in a trivial HTML shell for a consistent extension, not real markup, so
    `is_fallback` still keys off manifest status rather than file presence."""
    manifest_path = FORENSICS / "sources" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for rec in manifest:
        p = SOURCES_RAW / f"{rec['slug']}.html"
        if not p.exists():
            continue
        is_fallback = rec["status"] == "FETCH_FAILED"
        text = html_to_text(p.read_bytes())
        SNAPSHOT_TEXT[rec["url"]] = (text, COMMA_BETWEEN_DIGITS.sub("", text), is_fallback)


NUMBER_RE = re.compile(r"\b\d[\d,]{1,}\b")
PATH_RE = re.compile(r"\b[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+\b")
HANDLE_RE = re.compile(r"\b[a-zA-Z]+\d{2,}\b|\buser-[a-z]+\b", re.IGNORECASE)
DATE_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)")  # not anchored to end -- ts may carry a time suffix


def looks_like_real_path(segment: str) -> bool:
    """Reject prose word-pairs like 'read/write' or 'phase/target' that the
    greedy PATH_RE also matches; accept things that look like an actual
    dataset/repo/account path (has a digit, hyphen, dot, or uppercase)."""
    return any(c.isdigit() or c in ".-" or c.isupper() for c in segment)

MONTHS = {
    "01": "jan", "02": "feb", "03": "mar", "04": "apr", "05": "may", "06": "jun",
    "07": "jul", "08": "aug", "09": "sep", "10": "oct", "11": "nov", "12": "dec",
}
FULL_MONTHS = {
    "01": "january", "02": "february", "03": "march", "04": "april", "05": "may", "06": "june",
    "07": "july", "08": "august", "09": "september", "10": "october", "11": "november", "12": "december",
}

STRICT_TS_RE = re.compile(r"^\d{4}-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2})?Z?)?)?$|^\d{4}-\d{2}$")

STOPWORD_NUMBERS = {"2026", "2025", "2027"}  # years alone are too common to count as strong evidence


def extract_terms(event: dict) -> list[str]:
    terms: set[str] = set()
    haystack = " ".join(
        str(event.get(k, "")) for k in ("action", "target", "notes")
    )

    for m in NUMBER_RE.finditer(haystack):
        n = m.group(0)
        n_clean = n.replace(",", "")
        if n_clean in STOPWORD_NUMBERS:
            continue
        if len(n_clean) < 2:
            continue
        terms.add(n_clean)

    for m in PATH_RE.finditer(haystack):
        v = m.group(0)
        if "/" in v and not v.startswith("http") and looks_like_real_path(v):
            terms.add(v.lower())

    for m in HANDLE_RE.finditer(haystack):
        terms.add(m.group(0).lower())

    ts = event.get("ts", "")
    dm = DATE_RE.match(ts)
    if dm:
        y, mo, d = dm.groups()
        clean_date = f"{y}-{mo}-{d}"  # use the matched ISO date only, never the raw ts
        # (raw ts can carry malformed suffixes, e.g. a missing "T" before a
        # time component -- see verification_summary.md "data quality notes")
        terms.add(clean_date)
        month_name = MONTHS.get(mo)
        if month_name:
            terms.add(f"{month_name} {int(d)}")
            terms.add(f"{FULL_MONTHS.get(mo, month_name)} {int(d)}")

    return sorted(terms)


def check_terms(terms: list[str], text: str, text_nocommas: str) -> tuple[list[str], list[str]]:
    found, missing = [], []
    for t in terms:
        if t in text or (t.isdigit() and t in text_nocommas):
            found.append(t)
        else:
            missing.append(t)
    return found, missing


def verdict_for(found: list[str], missing: list[str], is_fallback: bool, has_snapshot: bool) -> str:
    if not has_snapshot:
        return "NO_SNAPSHOT"
    total = len(found) + len(missing)
    if total == 0:
        return "NO_TERMS_EXTRACTED"
    ratio = len(found) / total
    base = "STRONG" if ratio >= 0.66 else ("PARTIAL" if ratio > 0 else "UNSUPPORTED")
    return f"{base}_MANUAL_FALLBACK" if is_fallback else base


def main() -> None:
    load_snapshots()
    rows = []
    for fp in sorted(glob.glob(str(FORENSICS_DATA / "incident_*.jsonl"))):
        case = Path(fp).stem.removeprefix("incident_")
        for line in Path(fp).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            event = json.loads(line)
            url = event.get("source_url", "")
            terms = extract_terms(event)
            entry = SNAPSHOT_TEXT.get(url)
            if entry is None:
                found, missing = [], terms
                is_fallback = False
                has_snapshot = False
            else:
                text, text_nocommas, is_fallback = entry
                found, missing = check_terms(terms, text, text_nocommas)
                has_snapshot = True
            v = verdict_for(found, missing, is_fallback, has_snapshot)
            ts_ok = bool(STRICT_TS_RE.match(event.get("ts", "")))
            rows.append(
                {
                    "case": case,
                    "event_id": event["event_id"],
                    "ts_well_formed": ts_ok,
                    "ts_raw": event.get("ts", "") if not ts_ok else "",
                    "epistemic": event.get("epistemic", ""),
                    "source_url": url,
                    "terms_extracted": len(terms),
                    "terms_found": len(found),
                    "terms_missing": len(missing),
                    "verdict": v,
                    "found_terms": "; ".join(found),
                    "missing_terms": "; ".join(missing),
                }
            )

    out_csv = FORENSICS / "out" / "verification_report.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    from collections import Counter

    counts = Counter(r["verdict"] for r in rows)
    lines = [
        "# Deterministic grounding check — summary",
        "",
        f"{len(rows)} events checked across {len(set(r['case'] for r in rows))} incident files.",
        "",
        "| Verdict | Count | Meaning |",
        "|---------|-------|---------|",
        f"| STRONG | {counts.get('STRONG', 0)} | >=66% of extracted terms found verbatim in the frozen snapshot |",
        f"| PARTIAL | {counts.get('PARTIAL', 0)} | some but not most terms found — spot-check before lock |",
        f"| UNSUPPORTED | {counts.get('UNSUPPORTED', 0)} | none of the extracted terms found — spot-check before lock |",
        f"| STRONG_MANUAL_FALLBACK | {counts.get('STRONG_MANUAL_FALLBACK', 0)} | strong match, but against a tool-mediated summary, not raw HTML (see sources/README.md) |",
        f"| PARTIAL_MANUAL_FALLBACK | {counts.get('PARTIAL_MANUAL_FALLBACK', 0)} | partial match against a tool-mediated summary — treat as lower-confidence |",
        f"| UNSUPPORTED_MANUAL_FALLBACK | {counts.get('UNSUPPORTED_MANUAL_FALLBACK', 0)} | no match against a tool-mediated summary — spot-check |",
        f"| NO_TERMS_EXTRACTED | {counts.get('NO_TERMS_EXTRACTED', 0)} | our heuristic extractor found nothing distinctive to check (e.g. purely qualitative notes) — not a failure, just outside this check's coverage |",
        f"| NO_SNAPSHOT | {counts.get('NO_SNAPSHOT', 0)} | source_url has no snapshot at all (should be 0; investigate if not) |",
        "",
    ]
    malformed = [r for r in rows if not r["ts_well_formed"]]
    if malformed:
        lines += [
            "## Data-quality finding: malformed `ts` values (not fixed here — see note)",
            "",
            "This check also validates every event's `ts` field against a strict ISO-8601-ish pattern",
            "(`YYYY-MM`, `YYYY-MM-DD`, or `YYYY-MM-DDTHH:MM[:SS]Z`). The following do not match:",
            "",
            "| case | event_id | raw ts |",
            "|------|----------|--------|",
        ] + [f"| {r['case']} | {r['event_id']} | `{r['ts_raw']}` |" for r in malformed] + [
            "",
            "**Not fixed in this pass** — this reproducibility run is additive/read-only with respect to",
            "`forensics/data/*.jsonl` per tonight's instruction not to touch last night's locked-pending work.",
            "Looks like a missing `T` separator (should likely be e.g. `2026-07-10T00:00Z`). One-line fix,",
            "left for a human/owner to apply and re-run `forensics/src/build_all.py` afterward.",
            "",
        ]
    lines += [
        "**What this is not:** proof that every claim is true — it is a mechanical check that the specific numbers/",
        "names/dates written into each event actually appear in the page we cite for it, using a frozen local copy",
        "so the check doesn't silently break if the live page changes. PARTIAL/UNSUPPORTED rows are not accusations,",
        "they're a triage list — some are heuristic-extractor misses (e.g. a number formatted differently in the",
        "source), some are genuine gaps worth a human look before a sheet gets locked.",
        "",
        "Full per-event detail: `verification_report.csv`.",
    ]
    (FORENSICS / "out" / "verification_summary.md").write_text("\n".join(lines))

    print(f"wrote {out_csv} ({len(rows)} rows)")
    print(f"wrote {FORENSICS / 'out' / 'verification_summary.md'}")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
