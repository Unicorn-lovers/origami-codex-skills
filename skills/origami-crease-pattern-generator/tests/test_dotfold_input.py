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

    def test_sixteen_rows_and_bits_preserve_screen_orientation(self):
        rows = ["0" * 15 + "1"] + ["0" * 16] * 14 + ["1" + "0" * 15]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.txt"
            for text in (
                "".join(rows),
                "\n".join(rows).translate(str.maketrans("01", ".#")),
            ):
                path.write_text(text)
                self.assertEqual(load_target(path)["rows"], rows)
                self.assertEqual(load_target(path, size=16)["bits"], "".join(rows))
                with self.assertRaisesRegex(ValueError, "--size"):
                    load_target(path, size=8)

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

    def test_sixteen_opaque_foreground_uses_border_not_average_or_corner(self):
        ink, paper = "#12a3bc", "#fc701a"
        image = Image.new("RGB", (16, 16), paper)
        image.paste(ink, (1, 1, 15, 15))
        image.putpixel((0, 0), (18, 163, 188))
        for scale in (1, 3):
            with self.subTest(scale=scale):
                image.resize((16 * scale, 16 * scale), Image.Resampling.NEAREST).save(
                    self.path
                )
                result = load_target(self.path)
                self.assertEqual(
                    (result["foreground"], result["background"]), (ink, paper)
                )
                self.assertEqual(result["bits"].count("1"), 197)
                override = load_target(self.path, foreground=paper)
                self.assertEqual(
                    override["bits"],
                    result["bits"].translate(str.maketrans("01", "10")),
                )

    def test_sixteen_opaque_border_tie_uses_top_left_and_counts_corners_once(self):
        # Two top corners + 28 noncorners tie the other 30 border cells.
        image = Image.new("RGB", (16, 16), "#204060")
        image.paste("#c08051", (0, 0, 16, 8))
        for flip in (False, True):
            picture = (
                image.transpose(Image.Transpose.FLIP_TOP_BOTTOM) if flip else image
            )
            picture.save(self.path)
            result = load_target(self.path)
            self.assertEqual(result["background"], "#204060" if flip else "#c08051")
            self.assertEqual(result["bits"], "0" * 128 + "1" * 128)
        # Three corners of the top-left color with only 29 of 60 border cells.
        # Counting corners twice would change the majority to a tie.
        image.putpixel((15, 15), (192, 128, 81))
        for x in (1, 2):
            image.putpixel((x, 0), (32, 64, 96))
        image.save(self.path)
        self.assertEqual(load_target(self.path)["foreground"], "#c08051")

    def test_sixteen_opaque_solid_color_uses_all_pixels(self):
        Image.new("RGB", (16, 16), "#204060").save(self.path)
        result = load_target(self.path)
        self.assertEqual(result["foreground"], "#204060")
        self.assertIsNone(result["background"])
        self.assertEqual(result["bits"], "1" * 256)

    def test_transparent_pixels_with_different_hidden_colors(self):
        image = self.grid("#010304", (21, 44, 33, 0), scale=2)
        image.putpixel((0, 0), (3, 9, 14, 0))
        image.save(self.path)
        result = load_target(self.path, size=8)
        self.assertEqual(result["rows"], ROWS)
        self.assertEqual(result["foreground"], "#010304")
        self.assertEqual(result["background"], "transparent")

    def test_native_sixteen_and_ambiguous_enlargement(self):
        image = self.grid(scale=2)
        image.save(self.path)
        rows = load_target(self.path)["rows"]
        self.assertEqual(
            rows, ["".join(bit * 2 for bit in row) for row in ROWS for _ in range(2)]
        )
        self.assertEqual(load_target(self.path, size=8)["rows"], ROWS)
        image.resize((32, 32), Image.Resampling.NEAREST).save(self.path)
        self.assertEqual(load_target(self.path)["rows"], ROWS)
        self.assertEqual(load_target(self.path, size=16)["rows"], rows)
        image.putpixel((15, 15), (0, 0, 0, 255))
        image.resize((48, 48), Image.Resampling.NEAREST).save(self.path)
        self.assertEqual(load_target(self.path)["bits"], "".join(rows)[:-1] + "1")
        with self.assertRaisesRegex(ValueError, "multiple colors"):
            load_target(self.path, size=8)

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
            load_target(self.path, size=8)
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
