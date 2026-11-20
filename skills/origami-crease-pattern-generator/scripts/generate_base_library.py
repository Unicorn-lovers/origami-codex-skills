#!/usr/bin/env python3
"""Generate the bundled traditional-base CP files from exact formulas."""

from __future__ import annotations

import argparse
import math
from pathlib import Path


Point = tuple[float, float]
Segment = tuple[str, Point, Point]
ASSIGNMENT = {"B": 1, "M": 2, "V": 3}


def point(x: float, y: float) -> Point:
    return (1000.0 * x, 1000.0 * y)


def boundary(points: list[Point]) -> list[Segment]:
    return [("B", points[index], points[index + 1]) for index in range(len(points) - 1)]


def square_boundary() -> list[Segment]:
    return boundary([point(0, 0), point(1, 0), point(1, 1), point(0, 1), point(0, 0)])


def split_square_boundary() -> list[Segment]:
    return boundary([
        point(0, 0), point(0.5, 0), point(1, 0), point(1, 0.5),
        point(1, 1), point(0.5, 1), point(0, 1), point(0, 0.5), point(0, 0),
    ])


def preliminary_base() -> list[Segment]:
    center = point(0.5, 0.5)
    return split_square_boundary() + [
        ("M", point(0, 0), center),
        ("M", point(1, 0), center),
        ("M", point(1, 1), center),
        ("M", point(0, 1), center),
        ("V", point(0.5, 0), center),
        ("V", center, point(0.5, 1)),
    ]


def waterbomb_base() -> list[Segment]:
    center = point(0.5, 0.5)
    return split_square_boundary() + [
        ("V", point(0, 0), center),
        ("V", point(1, 0), center),
        ("V", point(1, 1), center),
        ("V", point(0, 1), center),
        ("M", point(0, 0.5), center),
        ("M", center, point(1, 0.5)),
    ]


def blintz_base() -> list[Segment]:
    return split_square_boundary() + [
        ("M", point(0.5, 0), point(1, 0.5)),
        ("M", point(1, 0.5), point(0.5, 1)),
        ("M", point(0.5, 1), point(0, 0.5)),
        ("M", point(0, 0.5), point(0.5, 0)),
    ]


def bird_base() -> list[Segment]:
    t = (math.sqrt(2.0) - 1.0) / 2.0
    p = [
        point(0, 0), point(1, 0), point(1, 1), point(0, 1),
        point(0.5, 0), point(1, 0.5), point(0.5, 1), point(0, 0.5),
        point(0.5, 0.5), point(0.5, t), point(1 - t, 0.5),
        point(0.5, 1 - t), point(t, 0.5),
    ]
    edges = [
        ("V", 0, 8), ("V", 8, 2),
        ("M", 8, 9), ("M", 9, 0), ("M", 9, 1),
        ("M", 8, 10), ("M", 10, 1), ("M", 10, 2),
        ("M", 8, 11), ("M", 11, 2), ("M", 11, 3),
        ("M", 8, 12), ("M", 12, 3), ("M", 12, 0),
        ("V", 9, 10), ("V", 11, 12),
    ]
    return boundary([p[0], p[4], p[1], p[5], p[2], p[6], p[3], p[7], p[0]]) + [
        (assignment, p[start], p[end]) for assignment, start, end in edges
    ]


def fish_base() -> list[Segment]:
    r = 1.0 - 1.0 / math.sqrt(2.0)
    p = [
        point(0, 0), point(1, 0), point(1, 1), point(0, 1),
        point(1 - r, r), point(r, 1 - r), point(1, r), point(r, 1),
    ]
    edges = [
        ("V", 0, 4), ("V", 2, 4), ("M", 1, 4), ("V", 4, 6),
        ("V", 0, 5), ("V", 2, 5), ("M", 3, 5), ("V", 5, 7),
    ]
    return boundary([p[0], p[1], p[6], p[2], p[7], p[3], p[0]]) + [
        (assignment, p[start], p[end]) for assignment, start, end in edges
    ]


def frog_base() -> list[Segment]:
    a = (2.0 - math.sqrt(2.0)) / 4.0
    b = math.sqrt(2.0) / 4.0
    p = [
        point(0, 0), point(1, 0), point(1, 1), point(0, 1), point(0.5, 0.5),
        point(0.5, a), point(0.5, 0), point(b, a), point(1 - b, a),
        point(1 - a, 0.5), point(1, 0.5), point(1 - a, b), point(1 - a, 1 - b),
        point(0.5, 1 - a), point(0.5, 1), point(1 - b, 1 - a), point(b, 1 - a),
        point(a, 0.5), point(0, 0.5), point(a, 1 - b), point(a, b),
    ]
    edges = [
        ("M", 4, 0), ("M", 4, 5), ("V", 5, 6), ("V", 4, 7), ("V", 4, 8),
        ("V", 0, 7), ("V", 1, 8), ("V", 6, 7), ("V", 6, 8),
        ("M", 7, 5), ("M", 5, 8),
        ("M", 4, 9), ("V", 9, 10), ("V", 4, 11), ("V", 4, 12),
        ("V", 1, 11), ("V", 2, 12), ("V", 10, 11), ("V", 10, 12),
        ("M", 11, 9), ("M", 9, 12),
        ("M", 4, 2), ("M", 4, 13), ("V", 13, 14), ("V", 4, 15), ("V", 4, 16),
        ("V", 2, 15), ("V", 3, 16), ("V", 14, 15), ("V", 14, 16),
        ("M", 15, 13), ("M", 13, 16),
        ("M", 4, 17), ("V", 17, 18), ("V", 4, 19), ("V", 4, 20),
        ("V", 3, 19), ("V", 0, 20), ("V", 18, 19), ("V", 18, 20),
        ("M", 19, 17), ("M", 17, 20),
    ]
    return boundary([p[0], p[6], p[1], p[10], p[2], p[14], p[3], p[18], p[0]]) + [
        (assignment, p[start], p[end]) for assignment, start, end in edges
    ]


BASES = {
    "preliminary-base": preliminary_base,
    "waterbomb-base": waterbomb_base,
    "blintz-base": blintz_base,
    "bird-base": bird_base,
    "fish-base": fish_base,
    "frog-base": frog_base,
}


def number(value: float) -> str:
    rounded = round(value, 12)
    if abs(rounded - round(rounded)) < 1e-12:
        return str(int(round(rounded)))
    return f"{rounded:.12f}".rstrip("0").rstrip(".")


def render(segments: list[Segment]) -> str:
    rows = []
    for assignment, start, end in segments:
        rows.append(
            f"{ASSIGNMENT[assignment]} {number(start[0])} {number(start[1])} "
            f"{number(end[0])} {number(end[1])}"
        )
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent.parent / "assets" / "bases")
    parser.add_argument("--check", action="store_true", help="fail when committed CP files differ from generated content")
    args = parser.parse_args()

    failures = []
    for base_id, builder in BASES.items():
        destination = args.output_dir / f"{base_id}.cp"
        expected = render(builder())
        if args.check:
            if not destination.exists() or destination.read_text(encoding="utf-8") != expected:
                failures.append(str(destination))
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(expected, encoding="utf-8")

    if failures:
        for failure in failures:
            print(f"out of date: {failure}")
        return 1
    print(f"{'checked' if args.check else 'generated'} {len(BASES)} base CP files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
