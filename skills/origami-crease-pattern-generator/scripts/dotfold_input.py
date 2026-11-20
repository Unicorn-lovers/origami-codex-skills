#!/usr/bin/env python3
"""Read the occupied cells of an 8×8 dotFoldSolver silhouette in screen order."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SIZE = 8


def _text_rows(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) == 1 and re.fullmatch(r"[01]{64}", lines[0]):
        bits = lines[0]
        return [bits[i : i + SIZE] for i in range(0, len(bits), SIZE)]
    if len(lines) != SIZE or any(len(line) != SIZE for line in lines):
        raise ValueError(
            "The text mask needs eight rows of eight cells, or one 64-digit binary string."
        )
    symbols = set("".join(lines))
    if symbols <= {"0", "1"}:
        return lines
    if symbols <= {".", "#"}:
        return [line.translate(str.maketrans(".#", "01")) for line in lines]
    raise ValueError(
        "Use 0/1 or ./# consistently in the text mask (1 or # marks an occupied cell)."
    )


def _png_rows(path: Path, foreground: str | None) -> tuple[list[str], str, str | None]:
    try:
        from PIL import Image, ImageChops
    except ImportError as exc:
        raise ValueError(
            "Reading a PNG requires Pillow. A .txt mask needs only Python."
        ) from exc

    if foreground is not None:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", foreground):
            raise ValueError(
                "Supply the foreground as a six-digit RGB color such as '#204060'."
            )
        foreground = foreground.lower()
    try:
        with path.open("rb") as stream:
            # Pillow decodes some 16-bit PNG modes to 8-bit RGB automatically.
            header = stream.read(25)
            if header[:8] != b"\x89PNG\r\n\x1a\n" or len(header) < 25:
                raise ValueError("The file does not contain a PNG image.")
            if header[24] > 8:
                raise ValueError(
                    "Use a PNG with at most 8 bits per channel to preserve its exact colors."
                )
            stream.seek(0)
            with Image.open(stream) as image:
                if image.n_frames != 1:
                    raise ValueError("Choose one frame and export it as a static PNG.")
                if image.getexif().get(274, 1) != 1:
                    raise ValueError(
                        "Apply the saved orientation and export the upright pixel grid."
                    )
                width, height = image.size
                if width != height or width % SIZE:
                    raise ValueError(
                        f"The {width}×{height} PNG must be an 8×8 grid of equally sized square cells."
                    )
                rgba = image.convert("RGBA")
    except Image.DecompressionBombError as exc:
        raise ValueError(
            "The PNG exceeds Pillow's image size limit. Export the original 8×8 grid."
        ) from exc

    # Hidden RGB values are irrelevant when alpha is zero. Make them identical
    # before checking whether each visible grid cell has a uniform color.
    alpha = rgba.getchannel("A")
    levels = alpha.getcolors(2)
    if levels is None or any(level not in (0, 255) for _, level in levels):
        raise ValueError(
            "The PNG contains partial transparency. Use fully opaque or fully transparent pixels."
        )
    if any(level == 0 for _, level in levels):
        rgba.paste((0, 0, 0, 0), mask=ImageChops.invert(alpha))

    side = width // SIZE
    cells = []
    for row in range(SIZE):
        for col in range(SIZE):
            x, y = col * side, row * side
            colors = rgba.crop((x, y, x + side, y + side)).getcolors(1)
            if colors is None:
                raise ValueError(
                    f"Cell at row {row + 1}, column {col + 1} contains multiple colors. Export a solid-cell grid."
                )
            _, (r, g, b, a) = colors[0]
            cells.append(f"#{r:02x}{g:02x}{b:02x}" if a else "transparent")

    palette = set(cells)
    if palette == {"transparent"}:
        raise ValueError("The PNG has no occupied cells.")
    if len(palette) > 2:
        raise ValueError(
            "The PNG contains more than two visible cell values. Supply a two-color silhouette mask."
        )
    if "transparent" in palette:
        solid = next(iter(palette - {"transparent"}))
        if foreground is not None and foreground != solid:
            raise ValueError(
                f"The visible pixels are {solid}. Transparent pixels are the background."
            )
        foreground = solid
    elif foreground is None:
        if not palette <= {"#000000", "#ffffff"}:
            raise ValueError(
                f"Choose the occupied color with --foreground from {', '.join(sorted(palette))}."
            )
        foreground = "#000000"
    elif foreground not in palette:
        raise ValueError(
            f"The selected foreground {foreground} is absent from the PNG."
        )

    bits = "".join("1" if cell == foreground else "0" for cell in cells)
    rows = [bits[i : i + SIZE] for i in range(0, len(bits), SIZE)]
    return rows, foreground, next(iter(palette - {foreground}), None)


def load_target(path: Path, *, foreground: str | None = None) -> dict:
    """Return binary rows, the solver argument and the source color mapping."""
    path = Path(path)
    if path.suffix.lower() == ".png":
        rows, foreground, background = _png_rows(path, foreground)
    elif path.suffix.lower() == ".txt":
        if foreground is not None:
            raise ValueError(
                "--foreground applies only to PNG input. In text, 1 or # marks an occupied cell."
            )
        rows, background = _text_rows(path), None
    else:
        raise ValueError("Use a .png image or .txt mask for the 8×8 silhouette.")
    bits = "".join(rows)
    if "1" not in bits:
        raise ValueError("The target has no occupied cells.")
    return {
        "rows": rows,
        "bits": bits,
        "foreground": foreground,
        "background": background,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="8×8 text mask or solid-cell PNG")
    parser.add_argument("--foreground", help="occupied RGB color, e.g. '#204060'")
    args = parser.parse_args()
    try:
        target = load_target(args.target, foreground=args.foreground)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(target, indent=2))


if __name__ == "__main__":
    main()
