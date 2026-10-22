#!/usr/bin/env python3
"""Create an embedded SVG contact sheet and one JSON index per source directory."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import mimetypes
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "root"


def image_dimensions(data: bytes, suffix: str) -> tuple[int | None, int | None]:
    try:
        if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
            return struct.unpack(">II", data[16:24])
        if suffix == ".gif" and data[:3] == b"GIF" and len(data) >= 10:
            return struct.unpack("<HH", data[6:10])
        if suffix == ".bmp" and data[:2] == b"BM" and len(data) >= 26:
            width, height = struct.unpack("<ii", data[18:26])
            return abs(width), abs(height)
        if suffix in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8"):
            index = 2
            while index + 9 < len(data):
                if data[index] != 0xFF:
                    index += 1
                    continue
                marker = data[index + 1]
                index += 2
                if marker in {0xD8, 0xD9}:
                    continue
                if index + 2 > len(data):
                    break
                length = int.from_bytes(data[index:index + 2], "big")
                if length < 2 or index + length > len(data):
                    break
                if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                    height = int.from_bytes(data[index + 3:index + 5], "big")
                    width = int.from_bytes(data[index + 5:index + 7], "big")
                    return width, height
                index += length
    except (IndexError, struct.error):
        pass
    return None, None


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(input_dir: Path, output: Path, index_dir: Path, columns: int, thumb_width: int) -> dict[str, object]:
    source = input_dir.expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f"input directory does not exist: {source}")
    images = sorted(
        image_path for image_path in source.rglob("*")
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise ValueError(f"no supported images found under {source}")

    output = output.expanduser().resolve()
    if output.suffix.lower() != ".svg":
        raise ValueError("--output must end in .svg")
    index_dir = index_dir.expanduser().resolve()
    label_height = 44
    thumb_height = round(thumb_width * 0.72)
    cell_height = thumb_height + label_height
    rows = math.ceil(len(images) / columns)

    svg_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{columns * thumb_width}" '
            f'height="{rows * cell_height}" viewBox="0 0 {columns * thumb_width} {rows * cell_height}">'
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font:12px system-ui,sans-serif;fill:#111}.label{fill:#f6f6f6;stroke:#ddd}</style>',
    ]
    first_for_hash: dict[str, str] = {}
    groups: dict[str, list[dict[str, object]]] = {}
    records: list[dict[str, object]] = []

    for index, image_path in enumerate(images):
        relative = image_path.relative_to(source)
        group = relative.parent.as_posix() if relative.parent.as_posix() != "." else "root"
        data = image_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        duplicate_of = first_for_hash.get(digest)
        first_for_hash.setdefault(digest, relative.as_posix())
        width, height = image_dimensions(data, image_path.suffix.lower())
        mime = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(data).decode("ascii")

        column = index % columns
        row = index // columns
        x0 = column * thumb_width
        y0 = row * cell_height
        image_x = x0 + 8
        image_y = y0 + 8
        image_width = thumb_width - 16
        image_height = thumb_height - 16
        label = f"{index + 1:03d} {relative.as_posix()}"
        if len(label) > 54:
            label = label[:51] + "..."
        svg_parts.extend([
            (
                f'<image x="{image_x}" y="{image_y}" width="{image_width}" height="{image_height}" '
                f'preserveAspectRatio="xMidYMid meet" href="data:{html.escape(mime)};base64,{encoded}"/>'
            ),
            f'<rect class="label" x="{x0}" y="{y0 + thumb_height}" width="{thumb_width}" height="{label_height}"/>',
            f'<text x="{x0 + 6}" y="{y0 + thumb_height + 18}">{html.escape(label)}</text>',
        ])

        sidecar = image_path.with_suffix(image_path.suffix + ".txt")
        caption = sidecar.read_text(encoding="utf-8").strip() if sidecar.is_file() else None
        record = {
            "number": index + 1,
            "file": str(image_path),
            "relative_file": relative.as_posix(),
            "source_group": group,
            "width": width,
            "height": height,
            "sha256": digest,
            "duplicate_of": duplicate_of,
            "caption": caption,
        }
        records.append(record)
        groups.setdefault(group, []).append(record)

    svg_parts.append("</svg>")
    output.parent.mkdir(parents=True, exist_ok=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(svg_parts) + "\n", encoding="utf-8")

    group_files = []
    for group, group_records in sorted(groups.items()):
        target = index_dir / f"{safe_name(group)}.json"
        write_json(target, {"source_group": group, "images": group_records})
        group_files.append(str(target))

    manifest = {
        "input": str(source),
        "contact_sheet": str(output),
        "image_count": len(records),
        "source_group_count": len(groups),
        "duplicate_count": sum(record["duplicate_of"] is not None for record in records),
        "group_indexes": group_files,
        "images": records,
    }
    write_json(index_dir / "manifest.json", manifest)
    return manifest


def self_test() -> None:
    temporary = Path(tempfile.mkdtemp(prefix="origami-contact-sheet-test-"))
    try:
        article_a = temporary / "images" / "article-a"
        article_b = temporary / "images" / "article-b"
        article_a.mkdir(parents=True)
        article_b.mkdir(parents=True)
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=")
        gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==")
        original = article_a / "one.png"
        original.write_bytes(png)
        shutil.copy2(original, article_b / "duplicate.png")
        (article_b / "two.gif").write_bytes(gif)
        manifest = run(
            temporary / "images",
            temporary / "contact-sheet.svg",
            temporary / "indexes",
            columns=2,
            thumb_width=160,
        )
        if manifest["image_count"] != 3 or manifest["duplicate_count"] != 1:
            raise RuntimeError(f"unexpected self-test manifest: {manifest}")
        if not (temporary / "contact-sheet.svg").is_file():
            raise RuntimeError("contact sheet was not created")
        print(json.dumps({"success": True, "images": 3, "duplicates": 1}))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?", help="root containing images grouped by source directory")
    parser.add_argument("--output", type=Path, help="embedded SVG contact sheet")
    parser.add_argument("--index-dir", type=Path, help="directory for per-source JSON and manifest.json")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--thumb-width", type=int, default=320)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    if not args.input or not args.output or not args.index_dir:
        parser.error("input, --output, and --index-dir are required")
    if args.columns < 1 or args.columns > 12:
        parser.error("--columns must be between 1 and 12")
    if args.thumb_width < 80 or args.thumb_width > 2000:
        parser.error("--thumb-width must be between 80 and 2000")
    try:
        manifest = run(args.input, args.output, args.index_dir, args.columns, args.thumb_width)
        print(json.dumps({
            "success": True,
            "contact_sheet": manifest["contact_sheet"],
            "image_count": manifest["image_count"],
            "source_group_count": manifest["source_group_count"],
            "duplicate_count": manifest["duplicate_count"],
        }, ensure_ascii=False))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
