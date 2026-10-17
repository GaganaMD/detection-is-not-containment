#!/usr/bin/env python3
"""Unit test: appending a new URL to the manifests never renumbers existing
SRC ids. Uses temp copies of the real manifest files, not the live ones."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class TestSourceRegistryStability(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "snapshots").mkdir()
        (self.tmp / "data").mkdir()
        self.manifest_path = self.tmp / "snapshots" / "manifest.json"
        self.extra_path = self.tmp / "snapshots" / "extra_sources_manifest.json"
        self.manifest_path.write_text(json.dumps([
            {"url": "https://b.example/x", "slug": "b", "status": 200},
            {"url": "https://a.example/x", "slug": "a", "status": 200},
        ]))
        self.extra_path.write_text(json.dumps([]))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, monkeypatch_root):
        import source_registry as sr
        sr.FORENSICS_SOURCES = self.tmp / "snapshots"
        sr.REGISTRY_PATH = self.tmp / "data" / "source_registry.json"
        return sr.load_or_build_registry()

    def test_first_run_alphabetical(self):
        rows = self._run(self.tmp)
        by_url = {r["url"]: r["source_id"] for r in rows}
        self.assertEqual(by_url["https://a.example/x"], "SRC01")
        self.assertEqual(by_url["https://b.example/x"], "SRC02")

    def test_appending_new_url_does_not_renumber(self):
        first = self._run(self.tmp)
        first_ids = {r["url"]: r["source_id"] for r in first}

        # add a third URL that would sort alphabetically FIRST
        existing = json.loads(self.manifest_path.read_text())
        existing.append({"url": "https://aaa.example/x", "slug": "aaa", "status": 200})
        self.manifest_path.write_text(json.dumps(existing))

        second = self._run(self.tmp)
        second_ids = {r["url"]: r["source_id"] for r in second}

        # old assignments must be unchanged
        self.assertEqual(second_ids["https://a.example/x"], first_ids["https://a.example/x"])
        self.assertEqual(second_ids["https://b.example/x"], first_ids["https://b.example/x"])
        # new one gets the next available number, not SRC01
        self.assertEqual(second_ids["https://aaa.example/x"], "SRC03")


if __name__ == "__main__":
    unittest.main()
