"""16-by-16 CLI integration checks. FLAT_FOLDER_ROOT enables the pinned layer solver."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
DIAMOND = SKILL / "assets/examples/pixel-art/diamond-16.txt"


class Search16CliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.output = self.directory / "out"

    def run_search(self, target, flat_folder):
        return subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts/dotfold.py"),
                str(target),
                "--out-dir",
                str(self.output),
                "--flat-folder-dir",
                str(flat_folder),
                "--max-candidates",
                "8",
                "--timeout",
                "20",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=35,
        )

    def artifact(self, filename):
        return json.loads((self.output / filename).read_text(encoding="utf-8"))

    @unittest.skipUnless(
        os.environ.get("FLAT_FOLDER_ROOT"),
        "set FLAT_FOLDER_ROOT for the pinned layer check",
    )
    def test_pixel_diamond_searches_tiles_and_exports_exact_visible_match(self):
        result = self.run_search(DIAMOND, os.environ["FLAT_FOLDER_ROOT"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = self.artifact("report.json")
        self.assertEqual(report["status"], "exact")
        self.assertEqual(report["gridSize"], 16)
        self.assertEqual(report["layers"]["pixelDifferenceArea"], 0)
        self.assertGreaterEqual(report["search"]["layerChecks"], 1)
        rows = self.artifact("target.json")["rows"]
        # This input contains single-pixel steps. A repeated 2×2 rendering
        # of an 8×8 mask could not preserve these two different adjacent rows.
        self.assertNotEqual(rows[0], rows[1])
        self.assertEqual([len(row) for row in rows], [16] * 16)
        solver = self.artifact("solver.json")
        self.assertEqual(solver["inputBits"], "".join(rows))
        recipe = solver["selectedCandidate"]
        self.assertEqual(recipe["method"], "boundary_tiles")
        self.assertEqual(len(recipe["boundary"]), 64)
        self.assertEqual(len(recipe["cpstr"]), 450)

        graph = self.artifact("assigned.fold")
        assignments = set(graph["edges_assignment"])
        self.assertLessEqual(assignments, {"B", "M", "V"})
        self.assertTrue(assignments & {"M", "V"})
        cp_lines = (self.output / "candidate.cp").read_text().splitlines()
        self.assertEqual(len(cp_lines), len(graph["edges_vertices"]))
        self.assertTrue(self.artifact("folded.fold")["faceOrders"])
        self.assertTrue(
            any(cell["ink"] for cell in self.artifact("visible-cells.json"))
        )

    def test_exhausted_checkerboard_has_no_cp(self):
        checker = self.directory / "checker.txt"
        checker.write_text("\n".join(["01" * 8, "10" * 8] * 8) + "\n")
        result = self.run_search(checker, self.directory / "unused")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = self.artifact("report.json")
        self.assertEqual(report["status"], "no_candidate")
        self.assertEqual(report["search"]["candidatesTried"], 0)
        self.assertFalse((self.output / "candidate.cp").exists())

    def test_unverified_geometry_is_reported_without_assigned_cp(self):
        result = self.run_search(DIAMOND, self.directory / "missing-verifier")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = self.artifact("report.json")
        self.assertEqual(report["status"], "candidate_only")
        self.assertEqual(report["stopReason"], "verification_unavailable")
        self.assertTrue((self.output / "unassigned.fold").is_file())
        self.assertFalse((self.output / "candidate.cp").exists())
