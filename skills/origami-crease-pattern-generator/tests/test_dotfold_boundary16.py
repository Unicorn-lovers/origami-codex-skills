import sys
import unittest
from collections import Counter
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dotfold_boundary16 import boundary_assignments


def mask(predicate):
    return "".join(
        "1" if predicate(x, y) else "0" for y in range(16) for x in range(16)
    )


def walk_pixels(codes):
    """Decode a folded paper boundary and ray-cast the odd-covered cells."""
    x, y = 0, 0
    dx, dy = 0, -1
    side = 1
    vertical = Counter()
    points = []
    for i, code in enumerate(codes):
        if i % 16 == 0:
            assert code == 8
        else:
            assert code in (0, 1, 3, 4, 6)
        if code:
            if (code == 4) == (side == -1):
                dx, dy = -dy, dx
            else:
                dx, dy = dy, -dx
        if code in (1, 4):
            side *= -1
        if dy:
            vertical[x, min(y, y + dy)] += 1
        points.append((x, y))
        x, y = x + dx, y + dy
    assert (x, y, side) == (0, 0, 1)
    return {
        (x, y)
        for x in range(min(p[0] for p in points), max(p[0] for p in points))
        for y in range(min(p[1] for p in points), max(p[1] for p in points))
        if sum(count for (u, v), count in vertical.items() if v == y and u <= x) % 2
    }


def normalized(pixels):
    left = min(x for x, _ in pixels)
    top = min(y for _, y in pixels)
    return {(x - left, y - top) for x, y in pixels}


class BoundaryWalkTest(unittest.TestCase):
    def check_reconstruction(self, predicate):
        bits = mask(predicate)
        codes = next(boundary_assignments(bits, monotonic() + 3))
        self.assertEqual(len(codes), 64)
        for corner in (0, 16, 32, 48):
            self.assertEqual(codes[corner - 1] & 1, codes[corner + 1] >> 2)
        pixels = walk_pixels(codes)
        expected = normalized(
            {(i % 16, i // 16) for i, b in enumerate(bits) if b == "1"}
        )
        views = []
        for _ in range(4):
            views.extend([normalized(pixels), normalized({(-x, y) for x, y in pixels})])
            pixels = {(-y, x) for x, y in pixels}
        self.assertIn(expected, views)
        return codes

    def test_single_diagonal_for_native_odd_width_l(self):
        codes = self.check_reconstruction(lambda x, y: x < 3 or y >= 13)
        self.assertCountEqual((code for code in codes if code not in (0, 8)), [1, 4])

    def test_contours_meeting_at_a_four_way_vertex(self):
        self.check_reconstruction(lambda x, y: (x < 7 and y < 9) or (x >= 7 and y >= 9))

    def test_short_disconnected_outline_uses_doubled_steps(self):
        # Two rectangles have perimeters 28 and 30. The remaining six steps
        # come in pairs and may join them without changing odd coverage.
        self.check_reconstruction(lambda x, y: x != 7 and 3 <= y < 10)

    def test_expiry_empty_and_excess_perimeter(self):
        self.assertEqual(list(boundary_assignments("1" * 256, monotonic() - 1)), [])
        self.assertEqual(list(boundary_assignments("0" * 256, monotonic() + 1)), [])
        checker = mask(lambda x, y: (x + y) % 2 == 0)
        self.assertEqual(list(boundary_assignments(checker, monotonic() + 1)), [])
        with self.assertRaises(ValueError):
            list(boundary_assignments("1" * 64, monotonic() + 1))
