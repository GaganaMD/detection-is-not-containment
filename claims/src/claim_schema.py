#!/usr/bin/env python3
"""Schema for the new claims registry. Parallel to
`forensics/src/events.py`'s ForensicEvent -- same "small TypedDict +
validate function" shape, deliberately a SEPARATE namespace/file, not a
rewrite of the forensics schema (see plan: additive, not replacing).
"""

from __future__ import annotations

from typing import Any, TypedDict

CORROBORATION_TYPES = frozenset({"DIRECT", "CONCEPTUAL", "DERIVATIVE", "CONTRADICTS", "NOT_MENTIONED"})
EPISTEMIC_HINTS = frozenset({"confirmed", "asserted", "unknown"})
RELIABILITY_TIERS = frozenset({"A", "B", "C", "D", "E", "F"})


class ClaimRecord(TypedDict, total=False):
    claim_id: str                                  # "EC-SRC07-003"
    source_id: str                                 # "SRC07"
    source_url: str
    claim_text: str
    quote: str
    quote_verified: bool
    extraction_model: str
    extraction_run_id: str
    epistemic_hint: str                            # confirmed | asserted | unknown
    corroborating_sources: list[str]
    contradicting_sources: list[str]
    derivative_sources: list[str]
    independent_corroborating_sources: list[str]
    corroboration_count: int
    independent_corroboration_count: int
    information_credibility: int                   # 1-6, Admiralty-style, computed
    status: str                                    # always "proposed" from this pipeline
    created_at: str
    pipeline_version: str


REQUIRED_CLAIM_FIELDS = ("claim_id", "source_id", "source_url", "claim_text", "quote", "status")


def validate_claim(obj: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for field in REQUIRED_CLAIM_FIELDS:
        if field not in obj or obj[field] in (None, ""):
            errs.append(f"missing:{field}")
    hint = obj.get("epistemic_hint")
    if hint is not None and hint not in EPISTEMIC_HINTS:
        errs.append(f"bad_epistemic_hint:{hint}")
    return errs


class CorroborationResult(TypedDict, total=False):
    claim_id: str
    candidate_source_id: str
    corroboration_type: str                        # one of CORROBORATION_TYPES
    quote: str
    reason: str
    is_derivative_by_link: bool                    # deterministic href/domain check, independent of the LLM verdict


def validate_corroboration(obj: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for field in ("claim_id", "candidate_source_id", "corroboration_type"):
        if field not in obj or obj[field] in (None, ""):
            errs.append(f"missing:{field}")
    ct = obj.get("corroboration_type")
    if ct is not None and ct not in CORROBORATION_TYPES:
        errs.append(f"bad_corroboration_type:{ct}")
    return errs


class SourceReliability(TypedDict):
    source_id: str
    url: str
    tier: str            # A-F
    self_interested: bool
    rationale: str


def validate_source_reliability(obj: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    for field in ("source_id", "url", "tier", "self_interested", "rationale"):
        if field not in obj:
            errs.append(f"missing:{field}")
    tier = obj.get("tier")
    if tier is not None and tier not in RELIABILITY_TIERS:
        errs.append(f"bad_tier:{tier}")
    return errs
