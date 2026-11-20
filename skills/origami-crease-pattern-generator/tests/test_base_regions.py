import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from base_regions import BASES, check_catalog, conflicts, overlap_polygon, signed_area
from rank_bases import (
    build_result,
    map_reservations,
    validate_catalog,
    validate_requirements,
)


class PaperRegionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maps = json.loads((BASES / "regions.json").read_text())

    def test_all_tips_and_catalog_ids_match(self):
        self.assertEqual(check_catalog(), len(self.maps))

    def test_boundary_contact_alone_is_free(self):
        self.assertEqual(
            conflicts(
                self.maps["blintz-base"], {"head": "inward-a1", "body": "surface-a"}
            ),
            [],
        )

    def test_shared_paper_is_measured(self):
        conflicts_found = conflicts(
            self.maps["preliminary-base"], {"head": "flap-a2", "body": "surface-a"}
        )
        self.assertEqual(len(conflicts_found), 1)
        self.assertAlmostEqual(conflicts_found[0]["area_fraction"], 0.25)

    def test_partial_polygon_overlap_in_both_windings(self):
        p = [[0, 0], [1, 0], [0, 1]]
        q = [[0.5, 0], [1, 0], [1, 0.5], [0.5, 0.5]]
        for a in (p, p[::-1]):
            for b in (q, q[::-1]):
                self.assertAlmostEqual(abs(signed_area(overlap_polygon(a, b))), 0.125)

    def test_declared_sharing_and_competing_claims(self):
        group = self.maps["blintz-base"]
        assignments = {"head": "inward-a1", "ear": "inward-a1", "body": "inward-a1"}
        result = conflicts(group, assignments, {"ear": "head"})
        self.assertEqual([c["features"] for c in result], [["head", "body"]])
        self.assertAlmostEqual(result[0]["area_fraction"], 0.125)
        with self.assertRaises(ValueError):
            conflicts(group, {"head": "inward-a1", "ear": "inward-a2"}, {"ear": "head"})

    def test_surface_selection_avoids_reserved_flap(self):
        surfaces = [{"name": "body", "assigned": 1}]
        suggestion = map_reservations(
            self.maps["preliminary-base"],
            [{"name": "head", "assigned": [{"id": "flap-a2"}]}],
            surfaces,
        )
        self.assertEqual(
            suggestion["suggested_assignments"],
            {"head": "flap-a2", "body": "surface-b"},
        )
        self.assertEqual(suggestion["region_conflicts"], [])
        self.assertEqual(surfaces[0]["region_ids"], ["surface-b"])

    def test_ranking_with_and_without_an_explicit_region_file(self):
        path = BASES / "catalog.json"
        data = json.loads(path.read_text())
        req = validate_requirements(
            {
                "features": [{"name": "head", "length": "short"}],
                "surfaces": [{"name": "body"}],
            }
        )
        mapped = build_result(req, validate_catalog(data, path), path, 1)["candidates"][
            0
        ]
        self.assertIn("body", mapped["suggested_assignments"])
        del data["regions"]
        unmapped = build_result(req, validate_catalog(data, path), path, 1)[
            "candidates"
        ][0]
        self.assertNotIn("region_conflicts", unmapped)
        self.assertEqual(mapped["score"], unmapped["score"])


if __name__ == "__main__":
    unittest.main()
