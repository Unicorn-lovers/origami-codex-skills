#!/usr/bin/env python3
"""Build a small Oriedita .cp file from a deterministic JSON segment spec."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


ASSIGNMENTS = {
    "1": 1,
    "EDGE": 1,
    "BOUNDARY": 1,
    "2": 2,
    "M": 2,
    "MOUNTAIN": 2,
    "3": 3,
    "V": 3,
    "VALLEY": 3,
}


def parse_point(value: object, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must be a two-number array")
    try:
        point = (float(value[0]), float(value[1]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} contains a non-numeric coordinate") from exc
    if not all(math.isfinite(item) for item in point):
        raise ValueError(f"{label} coordinates must be finite")
    return point


def number(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def canonical_segment(code: int, a: tuple[float, float], b: tuple[float, float]) -> tuple[object, ...]:
    rounded_a = tuple(round(item, 9) for item in a)
    rounded_b = tuple(round(item, 9) for item in b)
    low, high = sorted((rounded_a, rounded_b))
    return (code, *low, *high)


def format_number(value: float) -> str:
    if abs(value) < 5e-13:
        value = 0.0
    return f"{value:.12g}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="JSON construction specification")
    parser.add_argument("output", type=Path, help="output .cp path")
    parser.add_argument("--force", action="store_true", help="replace an existing output file")
    args = parser.parse_args()

    if args.output.suffix.lower() != ".cp":
        parser.error("output must end in .cp")
    if args.output.exists() and not args.force:
        parser.error(f"output already exists: {args.output} (pass --force to replace it)")

    try:
        document = json.loads(args.spec.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("the JSON root must be an object")

        segments: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
        bounds: tuple[float, float, float, float] | None = None
        paper = document.get("paper")
        if paper is not None:
            if not isinstance(paper, dict):
                raise ValueError("paper must be an object")
            origin = parse_point(paper.get("origin", [0, 0]), "paper.origin")
            width = number(paper.get("width"), "paper.width")
            height = number(paper.get("height"), "paper.height")
            if width <= 0 or height <= 0:
                raise ValueError("paper width and height must be positive")
            x0, y0 = origin
            x1, y1 = x0 + width, y0 + height
            bounds = (x0, y0, x1, y1)
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for index in range(4):
                segments.append((1, corners[index], corners[(index + 1) % 4]))

        creases = document.get("creases", [])
        if not isinstance(creases, list):
            raise ValueError("creases must be an array")
        for index, crease in enumerate(creases):
            if not isinstance(crease, dict):
                raise ValueError(f"creases[{index}] must be an object")
            raw_assignment = str(crease.get("assignment", "")).upper()
            if raw_assignment not in ASSIGNMENTS:
                raise ValueError(f"creases[{index}].assignment is unknown: {raw_assignment!r}")
            a = parse_point(crease.get("a"), f"creases[{index}].a")
            b = parse_point(crease.get("b"), f"creases[{index}].b")
            if math.dist(a, b) <= 1e-9:
                raise ValueError(f"creases[{index}] is zero-length")
            if bounds is not None:
                x0, y0, x1, y1 = bounds
                for label, (x, y) in (("a", a), ("b", b)):
                    if x < x0 - 1e-9 or x > x1 + 1e-9 or y < y0 - 1e-9 or y > y1 + 1e-9:
                        raise ValueError(f"creases[{index}].{label} lies outside the declared paper")
            segments.append((ASSIGNMENTS[raw_assignment], a, b))

        if not segments:
            raise ValueError("no paper boundary or crease segments were provided")

        seen: set[tuple[object, ...]] = set()
        for index, (code, a, b) in enumerate(segments):
            key = canonical_segment(code, a, b)
            if key in seen:
                raise ValueError(f"segment {index} duplicates an earlier segment")
            seen.add(key)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            " ".join([str(code), *(format_number(value) for value in (*a, *b))])
            for code, a, b in segments
        ]
        args.output.write_text("\n".join(rows) + "\n", encoding="utf-8")
        counts = {code: sum(1 for item in segments if item[0] == code) for code in (1, 2, 3)}
        print(json.dumps({"output": str(args.output.resolve()), "segments": len(segments), "edge": counts[1], "mountain": counts[2], "valley": counts[3]}, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
