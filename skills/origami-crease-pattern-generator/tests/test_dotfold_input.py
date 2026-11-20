"""Exact silhouette import and dotFoldSolver's top-left row order."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dotfold_input import load_target

try:
    from PIL import Image
except ImportError:
    Image = None


ROWS = ["01000000", "00000001", "00000001", "00001110"] + ["00000000"] * 4


class TextTarget(unittest.TestCase):
    def test_equivalent_encodings(self):
        bits = "".join(ROWS)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            for source in [
                bits,
                "\r\n".join(ROWS),
                "\n".join(ROWS).translate(str.maketrans("01", ".#")),
            ]:
                with self.subTest(source=source):
                    path.write_text(source + "\n", encoding="utf-8")
                    result = load_target(path)
                    self.assertEqual(result["rows"], ROWS)
                    self.assertEqual(result["bits"], bits)
                    self.assertIsNone(result["foreground"])
                    self.assertIsNone(result["background"])

    def test_invalid_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            for source in [
                "0" * 64,
                "1" * 63,
                "\n".join(ROWS[1:]),
                "\n".join(ROWS).replace("0", ".", 1),
            ]:
                with self.subTest(source=source):
                    path.write_text(source, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_target(path)
            path.write_text("1" * 64, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "only to PNG"):
                load_target(path, foreground="#000000")


@unittest.skipUnless(Image, "PNG import requires Pillow")
class PngTarget(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "target.png"

    def grid(self, foreground="black", background="white", scale=1):
        image = Image.new("RGBA", (8, 8), background)
        for y, row in enumerate(ROWS):
            for x, bit in enumerate(row):
                if bit == "1":
                    image.paste(foreground, (x, y, x + 1, y + 1))
        return image.resize((8 * scale, 8 * scale), Image.Resampling.NEAREST)

    def test_exact_enlargement_and_black_white_reversal(self):
        self.grid(scale=3).convert("1").save(self.path)
        self.assertEqual(load_target(self.path)["rows"], ROWS)
        reversed_target = load_target(self.path, foreground="#FFFFFF")
        self.assertEqual(
            reversed_target["bits"], "".join(ROWS).translate(str.maketrans("01", "10"))
        )
        self.assertEqual(reversed_target["background"], "#000000")

    def test_explicit_opaque_foreground(self):
        self.grid("#12a3bc", "#fc701a").save(self.path)
        with self.assertRaisesRegex(ValueError, "--foreground"):
            load_target(self.path)
        result = load_target(self.path, foreground="#12A3BC")
        self.assertEqual(
            result,
            {
                "rows": ROWS,
                "bits": "".join(ROWS),
                "foreground": "#12a3bc",
                "background": "#fc701a",
            },
        )
        with self.assertRaisesRegex(ValueError, "absent"):
            load_target(self.path, foreground="#000000")

    def test_transparent_pixels_with_different_hidden_colors(self):
        image = self.grid("#010304", (21, 44, 33, 0), scale=2)
        image.putpixel((0, 0), (3, 9, 14, 0))
        image.save(self.path)
        result = load_target(self.path)
        self.assertEqual(result["rows"], ROWS)
        self.assertEqual(result["foreground"], "#010304")
        self.assertEqual(result["background"], "transparent")

    def test_palette_transparency(self):
        image = Image.new("P", (8, 8))
        image.putpalette([98, 43, 11, 12, 54, 243] + [0] * (768 - 6))
        for y, row in enumerate(ROWS):
            for x, bit in enumerate(row):
                image.putpixel((x, y), int(bit))
        image.save(self.path, transparency=0)
        self.assertEqual(load_target(self.path)["rows"], ROWS)

    def test_unsupported_rasters(self):
        self.grid(scale=2).resize((16, 8)).save(self.path)
        with self.assertRaisesRegex(ValueError, "8×8 grid"):
            load_target(self.path)
        image = self.grid(scale=2)
        image.putpixel((0, 0), (0, 0, 0, 255))
        image.save(self.path)
        with self.assertRaisesRegex(ValueError, "row 1, column 1"):
            load_target(self.path)
        image = self.grid()
        image.putpixel((0, 0), (255, 255, 255, 120))
        image.save(self.path)
        with self.assertRaisesRegex(ValueError, "partial transparency"):
            load_target(self.path)
        image.putpixel((0, 0), (30, 30, 30, 255))
        image.save(self.path)
        with self.assertRaisesRegex(ValueError, "more than two"):
            load_target(self.path)
        Image.new("I;16", (8, 8), 257).save(self.path)
        with self.assertRaisesRegex(ValueError, "8 bits"):
            load_target(self.path)

    def test_empty_and_full_masks(self):
        for color in ["white", (90, 100, 120, 0)]:
            Image.new("RGBA", (8, 8), color).save(self.path)
            with self.assertRaisesRegex(ValueError, "no occupied cells"):
                load_target(self.path)
        Image.new("RGB", (8, 8), "black").save(self.path)
        self.assertEqual(load_target(self.path)["bits"], "1" * 64)
