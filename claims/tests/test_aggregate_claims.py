#!/usr/bin/env python3
"""Unit tests for the corroboration rollup in aggregate_claims.py.
No network, no real out/ files -- synthetic claims + result rows only."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aggregate_claims import aggregate  # noqa: E402


def row(claim_id, candidate, verdict, linked="False"):
    return {
        "claim_id": claim_id,
        "candidate_source_id": candidate,
        "corroboration_type": verdict,
        "is_derivative_by_link": linked,
    }


class TestAggregate(unittest.TestCase):
    def test_direct_verdicts_count_toward_corroboration(self):
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [row("C1", "SRC02", "DIRECT"), row("C1", "SRC03", "CONCEPTUAL")]
        out = aggregate(claims, results)["C1"]
        self.assertEqual(out["corroboration_count"], 2)
        self.assertEqual(out["corroborating_sources"], ["SRC02", "SRC03"])

    def test_link_flagged_candidate_excluded_from_independent_count(self):
        """The exact case findings/05 flagged: an LLM-judged DIRECT verdict
        whose candidate literally hyperlinks back to the origin must not
        count as independent, even though it still counts as corroborating."""
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [
            row("C1", "SRC02", "DIRECT", linked="True"),
            row("C1", "SRC03", "DIRECT", linked="False"),
        ]
        out = aggregate(claims, results)["C1"]
        self.assertEqual(out["corroboration_count"], 2)
        self.assertEqual(out["independent_corroboration_count"], 1)
        self.assertEqual(out["independent_corroborating_sources"], ["SRC03"])

    def test_derivative_verdict_goes_to_derivative_sources_not_corroborating(self):
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [row("C1", "SRC02", "DERIVATIVE")]
        out = aggregate(claims, results)["C1"]
        self.assertEqual(out["corroboration_count"], 0)
        self.assertEqual(out["derivative_sources"], ["SRC02"])

    def test_contradicts_tracked_separately(self):
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [row("C1", "SRC02", "CONTRADICTS")]
        out = aggregate(claims, results)["C1"]
        self.assertEqual(out["contradicting_sources"], ["SRC02"])
        self.assertEqual(out["corroboration_count"], 0)

    def test_not_mentioned_ignored(self):
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [row("C1", "SRC02", "NOT_MENTIONED")]
        out = aggregate(claims, results)["C1"]
        self.assertEqual(out["corroboration_count"], 0)
        self.assertEqual(out["corroborating_sources"], [])

    def test_claim_with_no_result_rows_gets_zeroed_fields(self):
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        out = aggregate(claims, [])["C1"]
        self.assertEqual(out["corroboration_count"], 0)
        self.assertEqual(out["independent_corroboration_count"], 0)
        self.assertEqual(out["corroborating_sources"], [])

    def test_result_row_for_unknown_claim_id_is_ignored(self):
        """Defensive: a stale/mismatched CSV row referencing a claim_id not
        in the current claims_extracted.jsonl must not crash or silently
        create a phantom claim."""
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [row("C_STALE", "SRC02", "DIRECT")]
        out = aggregate(claims, results)
        self.assertEqual(set(out.keys()), {"C1"})
        self.assertEqual(out["C1"]["corroboration_count"], 0)

    def test_duplicate_candidate_rows_deduplicated(self):
        """A candidate could theoretically produce more than one row for the
        same claim across batches; the source should only count once."""
        claims = {"C1": {"claim_id": "C1", "source_id": "SRC01"}}
        results = [row("C1", "SRC02", "DIRECT"), row("C1", "SRC02", "CONCEPTUAL")]
        out = aggregate(claims, results)["C1"]
        self.assertEqual(out["corroboration_count"], 1)


if __name__ == "__main__":
    unittest.main()
