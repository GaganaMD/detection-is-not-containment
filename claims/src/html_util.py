#!/usr/bin/env python3
"""Case-preserving HTML stripping for extraction (readable text for the
model -- proper nouns, numbers as written). Deliberately separate from
check_event_grounding.py's lowercased html_to_text(), which is for
substring matching, not for handing to an LLM.
"""

from __future__ import annotations

import html
import re

SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)

# Block-level tags get replaced with a newline (preserve paragraph/heading
# structure); everything else (inline tags: em, strong, a, span, b, i, u,
# mark, sub, sup, code, ...) gets replaced with NOTHING so a word wrapped
# in inline markup mid-sentence stays contiguous with its neighbors. Found
# by a real bug: "had <em>ever</em> produced" was turning into
# "had \n\never\n\n produced", which silently broke otherwise-correct
# verbatim-quote matches for any sentence containing emphasis/links.
_BLOCK_TAGS = (
    "p|div|li|ul|ol|h[1-6]|br|hr|tr|td|th|thead|tbody|table|section|article|"
    "header|footer|nav|blockquote|pre|figure|figcaption|dl|dt|dd"
)
BLOCK_TAG_RE = re.compile(rf"</?(?:{_BLOCK_TAGS})(?:\s[^>]*)?/?>", re.I)
ANY_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"[ \t]+")
BLANKLINES_RE = re.compile(r"\n{3,}")


def strip_html(raw: str) -> str:
    """Case-preserving strip: drop script/style blocks, replace block-level
    tags with a newline (paragraph structure), replace all other (inline)
    tags with nothing (keeps mid-sentence markup from splitting a
    sentence), unescape entities, collapse whitespace."""
    text = SCRIPT_STYLE_RE.sub(" ", raw)
    text = BLOCK_TAG_RE.sub("\n", text)
    text = ANY_TAG_RE.sub("", text)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text)
    text = BLANKLINES_RE.sub("\n\n", text)
    return text.strip()


_TYPOGRAPHIC_NORMALIZE = {
    "‑": "-",   # non-breaking hyphen
    "‐": "-",   # hyphen
    "–": "-",   # en dash
    "—": "-",   # em dash
    "‘": "'", "’": "'",   # curly single quotes
    "“": '"', "”": '"',   # curly double quotes
    " ": " ",   # non-breaking space
    "…": "...",  # ellipsis char -> three dots (still detectable as elision)
}
_NORMALIZE_TABLE = str.maketrans(_TYPOGRAPHIC_NORMALIZE)


_WS_RUN_RE = re.compile(r"\s+")


def normalize_for_match(s: str) -> str:
    """Some models 'prettify' text when told to copy it verbatim -- two
    confirmed cases from real pilot claims: (1) plain hyphen -> non-breaking
    hyphen ("zero-day" -> "zero‑day"), (2) table-cell double-newlines
    (from HTML <td> stripping) collapsed to single newlines when quoting a
    table row. Neither changes the actual content. Normalize both sides to
    plain-ASCII typography AND collapse all whitespace runs (including
    newlines) to a single space before substring-matching, so a quote
    that's faithful in substance isn't falsely flagged for formatting.
    This does NOT paper over real elision -- an ellipsis is content, not
    whitespace, so "..." still won't bridge a genuine gap in the source
    and is still correctly flagged unverified."""
    s = s.translate(_NORMALIZE_TABLE)
    s = _WS_RUN_RE.sub(" ", s).strip()
    return s


def read_source_text(raw_path_or_text: str, is_markdown: bool = False) -> str:
    """For raw HTML files: strip. For manual_fallback markdown files: return as-is."""
    if is_markdown:
        return raw_path_or_text.strip()
    return strip_html(raw_path_or_text)
