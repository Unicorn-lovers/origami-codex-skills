"""The documented example regenerates the audited model and exposes both ear tips."""

import hashlib
import math
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from adapt_base import prepare, read_json, write_cp
from base_preview import outline_checks, visible_view


class PublishedExample(unittest.TestCase):
    def test_two_visible_tips(self):
        examples = SKILL / "assets/examples"
        result = examples / "two-ear-result"
        segments, landmarks, _, conflicts, source = prepare(
            read_json(examples / "two-ear-study.json")
        )
        report = read_json(result / "adaptation.json")
        self.assertFalse(conflicts)
        self.assertEqual(
            hashlib.sha256(source.read_bytes()).hexdigest(), report["source_sha256"]
        )
        with tempfile.TemporaryDirectory() as temp:
            cp = Path(temp) / "candidate.cp"
            write_cp(cp, segments)
            self.assertEqual(cp.read_bytes(), (result / "candidate.cp").read_bytes())
            self.assertEqual(
                hashlib.sha256(cp.read_bytes()).hexdigest(), report["candidate_sha256"]
            )
        lines, points, view = visible_view(
            read_json(result / "candidate.fold"),
            read_json(result / "folded-model.json"),
            landmarks,
        )
        self.assertEqual(view, "Oriedita layer cells")
        outline = outline_checks(lines, points)
        self.assertEqual(outline, report["on_projected_outline"])
        for part in ["Left ear", "Right ear", "Tail"]:
            self.assertTrue(outline[part])
        self.assertGreater(math.dist(points["Left ear"], points["Right ear"]), 100)
