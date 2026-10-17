#!/usr/bin/env python3
"""Unit tests for the term-overlap prefilter's pseudo-event adaptation.
No network, no real snapshots."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "forensics" / "src"))

from prefilter import extract_claim_terms, is_meaningful_match  # noqa: E402
from check_event_grounding import check_terms  # noqa: E402


class TestMeaningfulMatchThreshold(unittest.TestCase):
    """Regression test for a real pilot finding: bare 2-digit number
    fragments (day-of-month, hour) coincide across almost any two
    documents discussing the same month and must not count as a
    meaningful prefilter pass on their own."""

    def test_only_2digit_fragments_not_meaningful(self):
        self.assertFalse(is_meaningful_match(["07", "13", "00"]))

    def test_3digit_number_is_meaningful(self):
        self.assertTrue(is_meaningful_match(["07", "700"]))

    def test_full_date_is_meaningful(self):
        self.assertTrue(is_meaningful_match(["13", "2026-07-13"]))

    def test_no_terms_not_meaningful(self):
        self.assertFalse(is_meaningful_match([]))


class TestPrefilterAdaptation(unittest.TestCase):
    def test_claim_text_yields_extractable_terms(self):
        claim_text = "OpenAI's benchmark ExploitGym was published on 2026-05-11 with 898 vulnerability instances."
        terms = extract_claim_terms(claim_text)
        self.assertIn("898", terms)
        self.assertIn("2026-05-11", terms)

    def test_term_overlap_detected_in_candidate_text(self):
        claim_text = "The campaign involved approximately 1200 agents."
        terms = extract_claim_terms(claim_text)
        candidate_text = "reports indicate roughly 1200 agents were coordinating during the incident"
        found, missing = check_terms(terms, candidate_text, candidate_text)
        self.assertIn("1200", found)

    def test_no_overlap_when_candidate_unrelated(self):
        claim_text = "The dataset cfahlgren1/hub-stats was taken down around 2026-08-09."
        terms = extract_claim_terms(claim_text)
        candidate_text = "this document discusses an entirely different topic with no shared facts"
        found, missing = check_terms(terms, candidate_text, candidate_text)
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
