import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pattern_geometry import prepare_geometry
from pattern_library import checkout, search


class PatternLibraryTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "catalog").mkdir()
        self.source = b"1 0 0 1 0\n1 1 0 1 1\n1 1 1 0 1\n1 0 1 0 0\n2 0 0 1 1\n4 0 1 1 0\n"
        (self.root / "cat.cp").write_bytes(self.source)
        self.original_hash = hashlib.sha256(self.source).hexdigest()
        cat = dict(id="C1", title="Kitten", path="cat.cp", format="cp", kind="editable",
                   cp_ready=True, subjects=["cat"], sha256=self.original_hash)
        eye = dict(cat, id="T1", title="Cat's Eye Tessellation", subjects=["cat_pattern"], subject_detail="pattern")
        (self.root / "catalog/archives.jsonl").write_text("\n".join(map(json.dumps, (eye, cat))))
        page = dict(id="B1", title="仔猫", path="book.pdf", format="pdf", kind="crease_pattern",
                    page=5, source_type="book", subjects=["cat", "猫"], sequence_pages=[41, 46])
        (self.root / "pdf-records.jsonl").write_text(json.dumps(page))

    def test_search_subject_and_linked_book(self):
        args = argparse.Namespace(subject="羽の生えた猫", base=None, limit=1, source=None, ready=False, sequences=False)
        result = search(self.root, args)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["matches"][0]["id"], "C1")
        self.assertEqual(result["also_in_book"][0]["sequence_pages"], [41, 46])

    def test_local_variant_needs_visible_subject_before_ranking_as_a_match(self):
        candidate = dict(id="D1", title="Winged cat", format="cp", path="cat.cp", cp_ready=True,
                         parent_id="C1", source_type="local", subjects=["cat", "wings"],
                         validation_status="oriedita_flat_state_completed", sha256=self.original_hash)
        (self.root / "catalog/designs.jsonl").write_text(json.dumps(candidate))
        args = argparse.Namespace(subject="winged cat", base=None, limit=1, source=None, ready=True, sequences=False)
        self.assertEqual(search(self.root, args)["matches"][0]["id"], "C1")
        review = dict(id="D1", sha256=self.original_hash, recognition_status="recognized",
                      recognition_image="view.png")
        index = self.root / "catalog/recognition.jsonl"
        index.write_text(json.dumps(review))
        self.assertEqual(search(self.root, args)["matches"][0]["id"], "C1")
        (self.root / "view.png").touch()
        self.assertEqual(search(self.root, args)["matches"][0]["id"], "D1")
        index.write_text(json.dumps(dict(review, recognition_status="not_recognizable")))
        self.assertEqual(search(self.root, args)["matches"][0]["id"], "C1")
        args.subject = "D1"
        self.assertEqual(search(self.root, args)["matches"][0]["recognition_status"], "not_recognizable")

    def test_checkout_preserves_hash_and_omits_only_flat_edges(self):
        dest = self.root / "work"
        args = argparse.Namespace(id="C1", out_dir=dest, validate_base=False)
        checkout(self.root, args)
        manifest = json.loads((dest / "source.json").read_text())
        self.assertEqual(manifest["selected_file_sha256"], self.original_hash)
        self.assertEqual(manifest["omitted_flat_edges"], 1)
        self.assertEqual((dest / "base.cp").read_bytes(), self.source.split(b"4 0")[0])
        (dest / "candidate.cp").write_text("edited")
        with self.assertRaises(ValueError):
            checkout(self.root, args)
        self.assertEqual((self.root / "cat.cp").read_bytes(), self.source)
        (self.root / "cat.cp").write_text("modified source")
        args.out_dir = self.root / "other"
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checkout(self.root, args)
        self.assertFalse(args.out_dir.exists())

    def test_fold_conversion_preserves_orientation_and_requires_assignments(self):
        frame = dict(vertices_coords=[[0,0],[2,0],[2,2],[0,2]],
                     edges_vertices=[[0,1],[1,2],[2,3],[3,0],[0,2],[1,3]],
                     edges_assignment=["B","B","B","B","V","F"])
        cp, flat = prepare_geometry(json.dumps(frame).encode(), "fold")
        self.assertEqual(flat, 1)
        self.assertIn(b"3 -200 -200 200 200", cp)
        frame["edges_assignment"][-1] = "U"
        with self.assertRaisesRegex(ValueError, "assignment"):
            prepare_geometry(json.dumps(frame).encode(), "fold")
        frame["frame_classes"] = ["foldedForm"]
        with self.assertRaisesRegex(ValueError, "unfolded"):
            prepare_geometry(json.dumps(frame).encode(), "fold")
