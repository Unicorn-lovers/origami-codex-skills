"""Rebuild the published four-way comparison using its saved Oriedita solution."""

import json
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from compare_faces import compare, load_candidate
from fox_face import write_plan
from fox_fold_guide import generate

STUDY = SKILL / "assets/examples/fox-face"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class PublishedFoxFaces(unittest.TestCase):
    def test_rebuild_four_variants_and_selected_result(self):
        plans = read(STUDY / "recipe.json")["variants"]
        published = read(STUDY / "comparison.json")
        ordered_names = [item["id"] for item in published["candidates"]]
        self.assertEqual([p["name"] for p in plans], ordered_names)
        self.assertEqual(len(set(ordered_names)), 4)
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            folders = []
            for plan in plans:
                name = plan["name"]
                fixture = STUDY / "validated" / name
                candidate = root / name
                with self.subTest(candidate=name):
                    write_plan(candidate, plan)
                    self.assertEqual(
                        read(candidate / "plan.json"), read(fixture / "plan.json")
                    )
                    self.assertEqual(
                        (candidate / "candidate.cp").read_bytes(),
                        (fixture / "candidate.cp").read_bytes(),
                    )
                    self.assertEqual(
                        read(candidate / "features.json"),
                        read(fixture / "features.json"),
                    )
                    self.assertEqual(
                        read(candidate / "adaptation.json")["plan_sha256"],
                        read(fixture / "adaptation.json")["plan_sha256"],
                    )
                    validation = read(fixture / "validation/report.json")
                    self.assertTrue(validation["success"])
                    self.assertEqual(
                        validation["oriedita"]["calculation"]["violationCount"], 0
                    )
                    self.assertTrue(validation["oriedita"]["completed"])
                    shutil.copytree(fixture / "validation", candidate / "validation")
                    folders.append(candidate)

            output = root / "comparison"
            compare(
                folders,
                STUDY / "profile.json",
                output,
                back=published["side"] == "back",
                swap_paper=published["orange_paper_side"] == "back",
            )
            rebuilt = read(output / "comparison.json")
            self.assertEqual(rebuilt["profile_sha256"], published["profile_sha256"])
            for got, saved in zip(
                rebuilt["candidates"], published["candidates"], strict=True
            ):
                with self.subTest(comparison=got["id"]):
                    for field in (
                        "id",
                        "position",
                        "candidate_sha256",
                        "features_sha256",
                    ):
                        self.assertEqual(got[field], saved[field])
                    self.assertEqual(
                        got["evaluation"]["status"], saved["evaluation"]["status"]
                    )
                    self.assertEqual(
                        got["evaluation"]["failed_cues"],
                        saved["evaluation"]["failed_cues"],
                    )
                    self.assertAlmostEqual(
                        got["evaluation"]["score"],
                        saved["evaluation"]["score"],
                        places=5,
                    )
            selected = next(c for c in rebuilt["candidates"] if c["id"] == "ruff")
            self.assertEqual(selected["evaluation"]["status"], "pass")
            for generated, saved in (
                ("paper.svg", "paper.svg"),
                ("silhouettes.svg", "silhouettes.svg"),
                (f"view-{selected['position']}.svg", "folded.svg"),
            ):
                artwork = (output / generated).read_text(encoding="utf-8")
                self.assertEqual(artwork, (STUDY / saved).read_text(encoding="utf-8"))
                self.assertFalse(ET.fromstring(artwork).findall(".//{*}text"))
            self.assertEqual(
                generate(read(root / "ruff/plan.json")),
                (STUDY / "fold-guide.svg").read_text(encoding="utf-8"),
            )

    def test_stale_cp_and_swapped_solver_state_are_rejected(self):
        fixtures = STUDY / "validated"
        profile = read(STUDY / "profile.json")
        with tempfile.TemporaryDirectory() as workspace:
            candidate = Path(workspace) / "ruff"
            shutil.copytree(fixtures / "ruff", candidate)
            for artifact in (
                "candidate.cp",
                "validation/candidate.fold",
                "validation/folded-model.json",
            ):
                with self.subTest(artifact=artifact):
                    destination = candidate / artifact
                    original = destination.read_bytes()
                    shutil.copyfile(fixtures / "balanced" / artifact, destination)
                    with self.assertRaisesRegex(ValueError, "revalidate"):
                        load_candidate(candidate, profile)
                    destination.write_bytes(original)
