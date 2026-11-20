"""Measure recognizable geometry independently of labels, drawing direction, and scale."""

import cmath
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from shape_cues import evaluate, outer_ring


def model_for(cells):
    vertices = [p for cell in cells for p in cell]
    x0, x1 = min(p.real for p in vertices), max(p.real for p in vertices)
    y0, y1 = min(p.imag for p in vertices), max(p.imag for p in vertices)
    return {
        "foldedBounds": {"minX": x0, "minY": y0, "maxX": x1, "maxY": y1},
        "visibleRegions": [
            {
                "polygonNormalized": [
                    {"x": (z.real - x0) / (x1 - x0), "y": (z.imag - y0) / (y1 - y0)}
                    for z in cell
                ]
            }
            for cell in cells
        ],
    }


class FrontFaceCues(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = json.loads(
            (SKILL / "assets/examples/fox-face/profile.json").read_text()
        )
        cls.ring = [
            0j,
            0.6 + 0.5j,
            0.55 + 1j,
            0.17 + 0.72j,
            -0.17 + 0.72j,
            -0.55 + 1j,
            -0.6 + 0.5j,
        ]
        cls.features = {
            "left_ear": cls.ring[5],
            "right_ear": cls.ring[2],
            "nose": cls.ring[0],
            "left_cheek": cls.ring[6],
            "right_cheek": cls.ring[1],
        }

    def score(self, ring, features):
        return evaluate(
            model_for([ring]),
            {k: [z.real, z.imag] for k, z in features.items()},
            self.profile,
        )

    def test_pointed_ears_notch_and_taper(self):
        result = self.score(self.ring, self.features)
        self.assertEqual(result["status"], "pass", result)
        self.assertAlmostEqual(
            result["cues"]["forehead_notch"]["measurements"]["notch_depth_min"], 0.28
        )

    def test_rigid_frame_scale_and_handedness(self):
        transform = lambda z: 11 + 8j + 100 * cmath.exp(0.78j) * z.conjugate()
        result = self.score(
            [transform(z) for z in self.ring],
            {k: transform(z) for k, z in self.features.items()},
        )
        original = self.score(self.ring, self.features)
        self.assertEqual(result["status"], original["status"])
        self.assertEqual(result["score"], original["score"])

    def test_shallow_brow_fails_despite_distinct_tips(self):
        ring = self.ring[:]
        ring[3], ring[4] = 0.17 + 0.98j, -0.17 + 0.98j
        result = self.score(ring, self.features)
        self.assertIn("forehead_notch", result["failed_cues"])
        self.assertIn("ear_peaks", result["failed_cues"])

    def test_covered_tips_cannot_satisfy_peak_requirement(self):
        result = self.score(self.ring, self.features | {"left_ear": -0.5 + 0.93j})
        self.assertIn("ear_peaks", result["failed_cues"])

    def test_missing_evidence(self):
        result = self.score(self.ring, {})
        self.assertEqual(result["status"], "undetermined")
        self.assertIsNone(result["score"])
        self.assertEqual(
            evaluate({}, {}, self.profile, view="Folded projection / all layers")[
                "status"
            ],
            "undetermined",
        )

    def test_split_cell_edges_cancel(self):
        model = model_for(
            [
                [0j, 1 + 0j, 1 + 2j, 2j],
                [1 + 0j, 2 + 0j, 2 + 1j, 1 + 1j],
                [1 + 1j, 2 + 1j, 2 + 2j, 1 + 2j],
            ]
        )
        boundary = outer_ring(model)
        self.assertNotIn(1 + 1j, boundary)
        self.assertEqual(len(boundary), 7)

    def test_prior_outline_points_do_not_define_ears(self):
        base = SKILL / "assets/examples/two-ear-result"
        model = json.loads((base / "folded-model.json").read_text())
        pts = json.loads((base / "adaptation.json").read_text())["folded_landmarks"]
        mapped = {
            "left_ear": pts["Left ear"],
            "right_ear": pts["Right ear"],
            "nose": pts["Tail"],
            "left_cheek": [2, 414],
            "right_cheek": [342, -206],
        }
        result = evaluate(model, mapped, self.profile)
        self.assertEqual(result["status"], "revise", result)
        self.assertIn("ear_peaks", result["failed_cues"])
