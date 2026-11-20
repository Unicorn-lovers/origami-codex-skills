import os
import sys
import unittest
from pathlib import Path
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dotfold_geometry import tile_catalog
from dotfold_grid16 import DIRECTIONS, TILE_CATALOG, solve_tiles


def boundary(entries=()):
    folds = [8 if i % 16 == 0 else 0 for i in range(64)]
    for vertex, code in entries:
        folds[vertex] = code
    return folds


def decode(cp, corners):
    """Read every emitted ray and reconstruct all perimeter assignments independently."""
    states = {}
    for i in range(225):
        center = (1 + i % 15, 1 + i // 15)
        for (dx, dy), bit in zip(DIRECTIONS, TILE_CATALOG[int(cp[2 * i : 2 * i + 2])]):
            end = center[0] + dx, center[1] + dy
            edge = tuple(sorted((center, end)))
            if states.setdefault(edge, bit) != bit:
                raise AssertionError(f"shared edge {edge} disagrees")
    ring = [(i, 0) for i in range(16)] + [(16, i) for i in range(16)]
    ring += [(16 - i, 16) for i in range(16)] + [(0, 16 - i) for i in range(16)]
    codes = []
    for i, (x, y) in enumerate(ring):
        prev = ring[i - 1]
        nx, ny = ring[(i + 1) % 64]
        dx, dy = nx - x, ny - y
        if i % 16 == 0:
            states[tuple(sorted((prev, (nx, ny))))] = corners[i // 16]
            enter = x + dx - dy, y + dy + dx
            if states[tuple(sorted(((x, y), enter)))]:
                raise AssertionError("a crease originates at a paper corner")
    for i, (x, y) in enumerate(ring):
        if i % 16 == 0:
            codes.append(8)
            continue
        nx, ny = ring[(i + 1) % 64]
        dx, dy = nx - x, ny - y
        code = 0
        for bit, advance in enumerate((1, 0, -1)):
            end = x - dy + advance * dx, y + dx + advance * dy
            code |= states[tuple(sorted(((x, y), end)))] << bit
        codes.append(code)
    return codes


class TileSearchTests(unittest.TestCase):
    def candidates(self, folds, limit=2):
        candidates = list(solve_tiles(folds, monotonic() + 2, limit))
        for cp, caps in candidates:
            self.assertEqual(len(cp), 450)
            self.assertEqual(decode(cp, caps), folds)
        return candidates

    def test_36_canonical_indices(self):
        self.assertEqual(len(TILE_CATALOG), 36)
        self.assertEqual(TILE_CATALOG[2], (0, 0, 1, 0, 0, 0, 1, 0))
        self.assertEqual(TILE_CATALOG[16], (1, 0, 0, 0, 1, 0, 0, 0))
        self.assertEqual(TILE_CATALOG[35], (1,) * 8)

    @unittest.skipUnless(
        os.environ.get("DOTFOLD_TEST_SOURCE"), "pinned tile source is optional"
    )
    def test_complete_pinned_catalog(self):
        expected = tile_catalog(os.environ["DOTFOLD_TEST_SOURCE"])
        self.assertEqual([list(bits) for bits in TILE_CATALOG], expected)

    def test_empty_grid_has_a_single_answer(self):
        self.assertEqual(self.candidates(boundary()), [("00" * 225, (0, 0, 0, 0))])

    def test_corner_cap_agreement_is_required(self):
        for side in range(4):
            i = 16 * side
            folds = boundary([((i - 1) % 64, 1), (i + 1, 4)])
            self.assertEqual(
                self.candidates(folds),
                [("00" * 225, tuple(int(j == side) for j in range(4)))],
            )
            folds[i + 1] = 0
            self.assertEqual(self.candidates(folds), [])

    def test_interior_junction_with_unpaired_boundary_rays(self):
        # At image-grid (7,5), four rays extend NW, E, SE and S. Only the
        # diagonals have a straight partner on the opposite side of the sheet.
        folds = boundary([(2, 1), (21, 2), (30, 4), (41, 2)])
        answers = self.candidates(folds)
        self.assertEqual(len(answers), 1)
        cp, _ = answers[0]
        i = 15 * (5 - 1) + 7 - 1
        self.assertEqual(cp[2 * i : 2 * i + 2], "05")

    def test_distinct_solutions_obey_the_same_boundary(self):
        folds = boundary([(4, 2), (20, 2), (44, 2), (60, 2)])
        full = self.candidates(folds)
        self.assertEqual(len(set(full)), 2)
        self.assertEqual(self.candidates(folds, limit=1), full[:1])

    def test_invalid_impossible_and_expired_search(self):
        with self.assertRaises(ValueError):
            self.candidates([0] * 64)
        self.assertEqual(self.candidates(boundary([(8, 2)])), [])
        with self.assertRaises(TimeoutError):
            list(solve_tiles(boundary(), monotonic() - 1, 1))
