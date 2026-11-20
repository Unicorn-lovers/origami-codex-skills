import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dotfold_solver as solver

L_MASK = "11000000" * 6 + "11111111" * 2
FLAG_MASK = "11111111" * 3 + "11000000" * 5


class SolverProtocolTest(unittest.TestCase):
    def test_rejects_unbounded_or_malformed_input(self):
        for mask in ("1" * 63, "2" * 64, "1" * 65):
            with self.assertRaises(ValueError):
                solver.solve_mask(mask)
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                solver.solve_mask(L_MASK, timeout=timeout)

    def test_standalone_no_cp_and_empty_disconnected_results(self):
        for output in (
            "Search CP\nNo CP\n",
            "CPSTR:No CP\nCORNERS:\n",
            "CPSTR:\nCORNERS:\n",
        ):
            self.assertIsNone(solver._candidate(output))

    def test_malformed_results_are_errors(self):
        for output in (
            "some unrelated stdout",
            "CPSTR:36" + "00" * 48 + "\nCORNERS:0 0 0 0",
            "CPSTR:" + "00" * 49 + "\nCORNERS: 0 1 0",
        ):
            with self.assertRaises(ValueError):
                solver._candidate(output)

    def test_timeout_retains_partial_output(self):
        timeout = subprocess.TimeoutExpired(
            [], 1, output=b"partial search", stderr=b"diagnostic"
        )
        preflight = subprocess.CompletedProcess(
            [], 0, stdout="LOOP_LENGTH: 32\n", stderr=""
        )
        with (
            patch.object(solver, "prepare_solver", return_value=Path("/fixture")),
            patch.object(solver.subprocess, "run", side_effect=[preflight, timeout]),
        ):
            result = solver.solve_mask(L_MASK, timeout=1)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["branch"], "connected")
        self.assertEqual(result["stdout"], "LOOP_LENGTH: 32\npartial search")
        self.assertEqual(result["stderr"], "diagnostic")
        self.assertNotIn("cpstr", result)


@unittest.skipUnless(
    os.environ.get("DOTFOLD_TEST_SOURCE"),
    "set DOTFOLD_TEST_SOURCE to a pinned local checkout for native integration",
)
class NativeSolverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.cache.cleanup)
        cls.options = {
            "source_dir": os.environ["DOTFOLD_TEST_SOURCE"],
            "cache_dir": cls.cache.name,
        }

    def test_native_block_letter_and_offline_cache(self):
        result = solver.solve_mask(L_MASK, timeout=30, **self.options)
        self.assertEqual(result["status"], "candidate", result["reason"])
        self.assertEqual(result["loop_length"], 32)
        self.assertEqual(result["branch"], "connected")
        self.assertNotEqual(result["cpstr"], "00" * 49)
        self.assertEqual(len(result["corners"]), 4)
        self.assertTrue((Path(result["source_dir"]) / "TileDrawer.py").is_file())
        with patch.object(
            solver, "_read_sources", side_effect=AssertionError("unexpected download")
        ):
            rejected = solver.solve_mask("0" * 64, cache_dir=self.cache.name)
        self.assertEqual(rejected["status"], "unsupported")
        self.assertEqual(rejected["loop_length"], 0)

    def test_disconnected_boundary_with_retraced_bridge(self):
        two_bars = "11111110" + "00000000" + "11111100" + "00000000" * 5
        result = solver.solve_mask(two_bars, timeout=30, **self.options)
        self.assertEqual(result["status"], "candidate", result["reason"])
        self.assertEqual(result["perimeter"], 30)
        self.assertEqual(result["loop_length"], 32)
        self.assertEqual(result["branch"], "disconnected")
        self.assertIn(
            "shortest_euler_walk", [command[0] for command in result["commands"]]
        )

    def test_exhausted_connected_search(self):
        result = solver.solve_mask(FLAG_MASK, timeout=10, **self.options)
        self.assertEqual(result["status"], "no_candidate", result["reason"])
        self.assertEqual(result["branch"], "connected")
        self.assertIn("No CP", result["stdout"])


if __name__ == "__main__":
    unittest.main()
