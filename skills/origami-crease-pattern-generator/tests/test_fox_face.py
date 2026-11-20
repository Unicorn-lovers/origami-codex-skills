"""A change in the recipe must reach the reflected ears, nose and brow."""

import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fox_face import DEFAULT_RECIPE, geometry, write_plan
from test_base_checkpoints import project_landmark


class FoxFaceConstruction(unittest.TestCase):
    def test_landmark_distances_from_the_actual_crease_lines(self):
        for plan in json.loads(DEFAULT_RECIPE.read_text())["variants"]:
            with self.subTest(name=plan["name"]):
                params = plan["parameters"]
                route = plan.get("route", "pointed")
                segments, anchors = geometry(params, route)
                creases = [
                    (complex(*a), complex(*b))
                    for code, a, b in segments
                    if code in (2, 3)
                ]
                points = {
                    name: project_landmark(complex(*xy), creases)
                    for name, xy in anchors.items()
                }
                slope = params["ear_slope"]
                if route == "ruff":
                    ear_x = 1 - 2 / (1 + slope * slope)
                    face_height = 2 * slope / (1 + slope * slope)
                else:
                    drop = 1 - params["ear_root"]
                    ear_x = 1 - 2 * drop / (1 + slope * slope)
                    face_height = 1 + 2 * drop * slope / (1 + slope * slope)
                ears = [points["left_ear"], points["right_ear"]]
                self.assertAlmostEqual(
                    abs(ears[0] - ears[1]), math.sqrt(2) * ear_x, places=7
                )
                self.assertAlmostEqual(
                    abs(sum(ears) / 2 - points["nose"]),
                    face_height / math.sqrt(2),
                    places=7,
                )
                self.assertAlmostEqual(
                    abs(points["left_cheek"] - points["nose"]),
                    abs(points["right_cheek"] - points["nose"]),
                    places=7,
                )

    def test_materialized_plan_reproduces_source_and_artifact_digests(self):
        plan = json.loads(DEFAULT_RECIPE.read_text())["variants"][-1]
        with tempfile.TemporaryDirectory() as tmp:
            a, b = (Path(tmp) / p for p in ["first", "rebuilt"])
            write_plan(a, plan)
            write_plan(b, json.loads((a / "plan.json").read_text()))
            cp = (a / "candidate.cp").read_bytes()
            self.assertEqual(cp, (b / "candidate.cp").read_bytes())
            record = json.loads((a / "adaptation.json").read_text())
            self.assertEqual(record["candidate_sha256"], hashlib.sha256(cp).hexdigest())
            canonical = json.dumps(
                plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
            self.assertEqual(
                record["plan_sha256"], hashlib.sha256(canonical).hexdigest()
            )
