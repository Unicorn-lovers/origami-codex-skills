"""Exercise record linkage using isolated fixture data."""

import base64
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from fox_face import write_plan
from record_fold_trial import load, record, revised_plan


class TrialTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.work = Path(folder.name)
        self.plan = {
            "name": "fixture",
            "parameters": {"ear_root": 0.65, "ear_slope": 0.48, "muzzle_depth": 0.17},
        }
        self.candidate = self.work / "source"
        write_plan(self.candidate, self.plan)
        # A temporary 1 px PNG tests photo copying without shipping a trial report.
        self.photo = self.work / "fixture.png"
        self.photo.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII="
            )
        )

    def options(self, **updates):
        values = {
            "candidate": self.candidate,
            "out_dir": self.work / "test-1",
            "plan": None,
            "feature": "right_ear",
            "point": [0.8, 0.65],
            "observation": "fixture observation",
            "paper": "fixture material",
            "photo": [self.photo],
            "change": ["/parameters/ear_root", "0.68"],
            "expect": "fixture expectation",
            "previous": None,
            "outcome": None,
        }
        values.update(updates)
        return Namespace(**values)

    def test_prior_plan_controls_repeat(self):
        first = record(self.options()).parent
        row = load(first / "trial.json")
        self.assertEqual(row["evidence"], "paper_observation_with_photos")
        self.assertEqual(row["material_point_normalized"], [0.8, 0.65])
        self.assertIn("right_ear", (first / "location.svg").read_text())
        self.assertEqual(
            (first / row["photos"][0]["file"]).read_bytes(), self.photo.read_bytes()
        )
        self.assertEqual(row["proposed_change"]["before"], 0.65)
        self.assertEqual(load(self.candidate / "plan.json"), self.plan)

        new = self.work / "altered"
        write_plan(new, load(first / "next-plan.json"))
        args = self.options(
            candidate=new,
            out_dir=self.work / "test-2",
            observation="repeat fixture",
            previous=first,
            outcome="inconclusive",
            change=None,
            expect=None,
        )
        second = load(record(args))
        self.assertEqual(second["comparison"]["relation"], "proposed_revision_refold")
        self.assertTrue(second["comparison"]["cp_changed"])
        self.assertEqual(second["comparison"]["reported_outcome"], "inconclusive")
        self.assertEqual(
            second["comparison"]["previous_observation"], row["observation"]
        )
        args.out_dir = self.work / "wrong"
        args.feature = "left_ear"
        with self.assertRaisesRegex(ValueError, "same feature"):
            record(args)
        args.feature = "right_ear"
        other = self.work / "other"
        write_plan(other, revised_plan(self.plan, "/parameters/ear_root", "0.72")[0])
        args.candidate = other
        with self.assertRaisesRegex(ValueError, "do not match"):
            record(args)
        self.assertFalse(args.out_dir.exists())

    def test_observation_without_photo(self):
        row = load(record(self.options(photo=[], change=None, expect=None)))
        self.assertEqual(row["evidence"], "paper_observation")
        self.assertEqual(row["photos"], [])

    def test_same_candidate_and_stale_plan(self):
        args = self.options(change=None, expect=None)
        first = record(args).parent
        with self.assertRaises(FileExistsError):
            record(args)
        args.previous, args.outcome, args.out_dir = (
            first,
            "unchanged",
            self.work / "repeat",
        )
        self.assertEqual(
            load(record(args))["comparison"]["relation"], "same_candidate_refold"
        )
        args.out_dir = self.work / "stale"
        (self.candidate / "plan.json").write_text(
            json.dumps({"name": "changed", "parameters": {}})
        )
        with self.assertRaisesRegex(ValueError, "plan has changed"):
            record(args)
        (self.candidate / "candidate.cp").write_text("changed")
        with self.assertRaisesRegex(ValueError, "candidate.cp has changed"):
            record(args)
        self.assertFalse(args.out_dir.exists())

    def test_older_adaptation_and_numeric_change(self):
        old = SKILL / "assets/examples"
        args = self.options(
            candidate=old / "two-ear-result",
            plan=old / "two-ear-study.json",
            feature="Right ear",
            point=None,
            change=["/operations/1/fraction", "0.55"],
        )
        # The older saved plan has more than one operation; use its actual split index.
        split = next(
            i
            for i, op in enumerate(load(args.plan)["operations"])
            if op["op"] == "split_tip"
        )
        args.change = [f"/operations/{split}/fraction", "0.55"]
        path = record(args)
        expected = load(args.plan)
        expected["operations"][split]["fraction"] = 0.55
        self.assertEqual(load(path.parent / "next-plan.json"), expected)
        for change in (
            ["/name", "1"],
            ["/parameters/ear_slope", "NaN"],
            ["/parameters/missing", "4"],
        ):
            with self.assertRaises(ValueError):
                revised_plan(self.plan, *change)
