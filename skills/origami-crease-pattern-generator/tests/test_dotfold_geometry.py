import itertools
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dotfold_geometry import (
    CORNER_EDGES,
    DIRECTIONS,
    coverage_cells,
    crease_svg,
    edge_key,
    make_fold,
    projection,
)


def synthetic_catalog():
    """Enumerate eight-ray masks satisfying Kawasaki's local angle condition."""
    masks = []
    for bits in itertools.product(range(2), repeat=8):
        rays = [i for i, present in enumerate(bits) if present]
        if not rays or (
            len(rays) % 2 == 0
            and sum(b - a for a, b in zip(rays[::2], rays[1::2])) == 4
        ):
            masks.append(list(bits))
    return masks


class DotFoldGeometryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)
        self.catalog = synthetic_catalog()
        # Loading with import or executing the extracted module would fail.
        (self.source / "TileDrawer.py").write_text(
            f'raise RuntimeError("GUI executed")\nTILE = {self.catalog!r}\n',
            encoding="utf-8",
        )

    def fold(self, segments=(), corners=(0, 0, 0, 0)):
        used = {edge_key(a, b) for a, b in segments}
        indices = []
        for y in range(7, 0, -1):
            for x in range(1, 8):
                mask = [
                    int(edge_key((x, y), (x + dx, y + dy)) in used)
                    for dx, dy in DIRECTIONS
                ]
                indices.append(self.catalog.index(mask))
        return make_fold("".join(f"{idx:02d}" for idx in indices), corners, self.source)

    def test_empty_graph_has_complete_boundary_and_exact_projection(self):
        fold = self.fold()
        self.assertEqual(len(fold["faces_vertices"]), 1)
        self.assertEqual(len(fold["vertices_coords"]), 32)
        self.assertEqual(fold["edges_assignment"], ["B"] * 32)
        report = projection(fold, "1" * 64)
        self.assertTrue(report["footprintMatchesTarget"])
        self.assertTrue(report["oddCoverageRegistration"]["exact"])
        self.assertEqual(report["maxLayers"], 1)

    def test_all_four_corner_indices_follow_source_screen_order(self):
        for i, edge in enumerate(CORNER_EDGES):
            with self.subTest(corner=i):
                fold = self.fold(corners=[int(j == i) for j in range(4)])
                ids = fold["edges_vertices"][fold["edges_assignment"].index("U")]
                self.assertEqual(
                    tuple(tuple(fold["vertices_coords"][k]) for k in ids), edge
                )
                self.assertEqual(len(fold["faces_vertices"]), 2)
                image = ElementTree.fromstring(crease_svg(fold))
                nodes = image.findall(".//{http://www.w3.org/2000/svg}line")
                self.assertEqual(len(nodes), 33)
                self.assertEqual(sum(n.get("data-assignment") == "U" for n in nodes), 1)

    def test_registered_odd_region_is_distinct_from_the_silhouette(self):
        fold = self.fold(corners=[1, 0, 0, 0])
        report = projection(fold, "0" + "1" * 63)
        self.assertTrue(report["oddCoverageRegistration"]["exact"])
        self.assertFalse(report["footprintMatchesTarget"])
        self.assertEqual(report["footprintArea"], 63.5)
        self.assertEqual(report["partialFootprintCells"], 1)
        self.assertEqual(report["visibleColors"], "unverified")

    def test_crossed_cell_diagonals_are_fully_split(self):
        segments = [((x, x - 1), (x + 1, x)) for x in range(1, 8)]
        segments += [((x, 6 - x), (x + 1, 5 - x)) for x in range(6)]
        fold = self.fold(segments)
        center = fold["vertices_coords"].index([3.5, 2.5])
        self.assertEqual(sum(center in edge for edge in fold["edges_vertices"]), 4)
        self.assertEqual(len(fold["faces_vertices"]), 4)
        self.assertEqual(set(fold["edges_assignment"]), {"B", "U"})
        self.assertEqual(sum(map(sum, coverage_cells(fold).values())), 256)

    def test_center_book_fold_has_empty_odd_region_and_32_cell_footprint(self):
        fold = self.fold([((4, y), (4, y + 1)) for y in range(8)])
        report = projection(fold, "0" * 64)
        self.assertEqual(report["oddCoverageCells"], 0)
        self.assertTrue(report["oddCoverageRegistration"]["exact"])
        self.assertEqual(report["maxLayers"], 2)
        self.assertEqual(report["footprintArea"], 32)

    def test_malformed_and_conflicting_tiles_are_rejected(self):
        for text, corners in [
            ("0" * 97, [0] * 4),
            ("99" * 49, [0] * 4),
            ("00" * 49, [0, 1]),
        ]:
            with (
                self.subTest(text=text, corners=corners),
                self.assertRaises(ValueError),
            ):
                make_fold(text, corners, self.source)
        east_west = self.catalog.index([0, 0, 1, 0, 0, 0, 1, 0])
        with self.assertRaisesRegex(ValueError, "adjacent tiles disagree"):
            make_fold(f"{east_west:02d}" + "00" * 48, [0] * 4, self.source)


if __name__ == "__main__":
    unittest.main()
