#!/usr/bin/env python3
"""Regression test built directly from the confirmed factity case: its raw
HTML contains `href="https://openai.com/index/hugging-face-incident-and-the-road-ahead/"`.
A synthetic candidate with an href to the home URL must flag
is_derivative_by_link=True; one without must not."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prefilter import is_derivative_by_link  # noqa: E402


class TestIndependenceHeuristic(unittest.TestCase):
    HOME_URL = "https://openai.com/index/hugging-face-incident-and-the-road-ahead/"

    def test_href_to_home_url_flags_derivative(self):
        candidate_html = (
            '<html><body><p>See the original post: '
            '<a href="https://openai.com/index/hugging-face-incident-and-the-road-ahead/">here</a></p></body></html>'
        )
        derivative, evidence = is_derivative_by_link(candidate_html, True, self.HOME_URL)
        self.assertTrue(derivative)
        self.assertIn("openai.com", evidence)

    def test_href_to_domain_only_still_flags_derivative(self):
        candidate_html = (
            '<html><body><a href="https://openai.com/index/some-other-page/">OpenAI</a></body></html>'
        )
        derivative, evidence = is_derivative_by_link(candidate_html, True, self.HOME_URL)
        self.assertTrue(derivative)

    def test_no_reference_does_not_flag(self):
        candidate_html = (
            "<html><body><p>Independent analysis with no link to the origin.</p></body></html>"
        )
        derivative, evidence = is_derivative_by_link(candidate_html, True, self.HOME_URL)
        self.assertFalse(derivative)
        self.assertEqual(evidence, "")

    def test_plaintext_domain_mention_in_markdown_fallback(self):
        candidate_md = "As reported by openai.com, the incident began in July."
        derivative, evidence = is_derivative_by_link(candidate_md, False, self.HOME_URL)
        self.assertTrue(derivative)

    def test_unrelated_markdown_does_not_flag(self):
        candidate_md = "This document discusses a completely separate matter."
        derivative, evidence = is_derivative_by_link(candidate_md, False, self.HOME_URL)
        self.assertFalse(derivative)


if __name__ == "__main__":
    unittest.main()
