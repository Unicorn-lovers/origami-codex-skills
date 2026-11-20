"""Geometry regressions for named base edits. Run with unittest discovery."""

import json
import math
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from base_operations import adapted_point, apply_operations, split_tip_points


def read_base(name):
    segments = []
    for row in (SKILL / "assets/bases" / (name + ".cp")).read_text().splitlines():
        kind, *coordinates = row.split()
        x, y, u, v = [float(n) / 1000 for n in coordinates]
        segments.append((int(kind), (x, y), (u, v)))
    return segments


def reflect(p, a, b):
    direction = tuple(y - x for x, y in zip(a, b))
    scale = sum((p[i] - a[i]) * direction[i] for i in (0, 1)) / math.dist(a, b) ** 2
    return tuple(2 * (a[i] + scale * direction[i]) - p[i] for i in (0, 1))


class BaseEdits(unittest.TestCase):
    maps = json.loads((SKILL / "assets/bases/regions.json").read_text())

    def edit(self, operations, name="blintz-base"):
        return apply_operations(read_base(name), operations, self.maps[name], name)

    def test_tip_to_target(self):
        for op, target in (
            ({"op": "shorten_tip", "fraction": 0.4}, (0.1, 0.1)),
            ({"op": "redirect_tip", "target": [0.1, 0.06]}, (0.1, 0.06)),
        ):
            cp = self.edit([{**op, "flap": "inward-a1"}])
            [(a, b)] = [(a, b) for kind, a, b in cp if kind == 3]
            self.assertLess(math.dist(reflect((0, 0), a, b), target), 1e-8)

    def test_split_pleat_preserves_two_distinct_peaks(self):
        flap = self.maps["blintz-base"]["flaps"]["inward-a1"]
        cp = self.edit([{"op": "split_tip", "flap": "inward-a1", "fraction": 0.4}])
        shoulder, tip = split_tip_points(flap, 0.4)
        [(a, b)] = [(a, b) for k, a, b in cp if k == 3]
        [(c, d)] = [(a, b) for k, a, b in cp if k == 2 and max(*a, *b) < 0.3]
        self.assertLess(min(math.dist(shoulder, a), math.dist(shoulder, b)), 1e-8)
        # The inner cap reflects over its own hinge then with the outer packet.
        folded = reflect(reflect(tip, c, d), a, b)
        self.assertLess(math.dist(folded, (0.076, 0.068)), 1e-8)
        self.assertGreater(math.dist(folded, shoulder), 0.1)
        with self.assertRaisesRegex(ValueError, "uncreased"):
            self.edit([{"op": "split_tip", "flap": "flap-a1"}], "preliminary-base")

    def test_release(self):
        cp = self.edit([{"op": "release_corner", "flap": "inward-a1"}])
        self.assertEqual(sum(kind == 2 for kind, a, b in cp), 3)
        self.assertIn((0.0, 0.0), {p for kind, a, b in cp if kind == 1 for p in (a, b)})

    def test_graft_preserves_square_and_transports_anchors(self):
        for side, new_origin in (
            ("top", (0.1, 0.2)),
            ("bottom", (0.1, 0)),
            ("left", (0.2, 0.1)),
            ("right", (0, 0.1)),
        ):
            op = {"op": "border_graft", "side": side, "width": 0.2}
            cp = self.edit([op])
            self.assertEqual(adapted_point((0, 0), [op]), new_origin)
            self.assertAlmostEqual(sum(math.dist(a, b) for k, a, b in cp if k == 1), 4)
            self.assertTrue(all(0 <= n <= 1 for _, a, b in cp for n in (*a, *b)))
            # A non-boundary crease from the source stays at its mapped coordinates.
            expected = [adapted_point(p, [op]) for p in ((0, 0.5), (0.5, 0))]
            self.assertTrue(
                any(
                    k == 2
                    and max(math.dist(p, q) for p, q in zip(expected, (a, b))) < 1e-8
                    for k, a, b in cp
                )
            )

    def test_region_replacement_keeps_other_quadrants(self):
        op = {"op": "hybrid_quadrant", "donor": "blintz-base", "quadrant": "sw"}
        cp = self.edit([op], "preliminary-base")
        self.assertIn((2, (0.0, 0.5), (0.5, 1.0)), cp)
        self.assertNotIn((2, (0.0, 0.5), (0.5, 0.0)), cp)
        self.assertIn((2, (0.0, 0.0), (0.5, 0.5)), cp)

    def test_invalid_edits_do_not_silently_default(self):
        with self.assertRaisesRegex(ValueError, "unknown field"):
            self.edit([{"op": "shorten_tip", "flap": "inward-a1", "fracion": 0.2}])
        with self.assertRaisesRegex(ValueError, "must follow"):
            self.edit(
                [
                    {"op": "border_graft", "side": "left", "width": 0.2},
                    {"op": "shorten_tip", "flap": "inward-a1"},
                ]
            )
        with self.assertRaisesRegex(ValueError, "unchanged"):
            self.edit([{"op": "shorten_tip", "flap": "inward-a1"}] * 2)


if __name__ == "__main__":
    unittest.main()
