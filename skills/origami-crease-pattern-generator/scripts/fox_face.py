#!/usr/bin/env python3
"""Generate a frontal fox-face study from a square folded on one diagonal."""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from adapt_base import write_cp
from base_operations import _canonical

DEFAULT_RECIPE = (
    Path(__file__).resolve().parents[1] / "assets/examples/fox-face/recipe.json"
)


def paper_point(x, y, front=True):
    """Double triangle with forehead endpoints at (±1,0) and muzzle at (0,1)."""
    a, b = (1 + x + y) / 2, (1 + x - y) / 2
    return (a, b) if front else (b, a)


def square_with_diagonal():
    corners = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    return [(1, corners[i - 1], v) for i, v in enumerate(corners)] + [
        (2, (0.0, 0.0), (1.0, 1.0))
    ]


def ruff_geometry(parameters):
    """Reverse both closed corners at the center, then turn down two free brow flaps."""
    if not isinstance(parameters, dict) or set(parameters) != {
        "ear_slope",
        "brow_height",
    }:
        raise ValueError("the ruff needs ear_slope and brow_height")
    slope, brow = parameters["ear_slope"], parameters["brow_height"]
    if (
        not all(type(v) in (int, float) and math.isfinite(v) for v in (slope, brow))
        or not 1 < slope < 4
    ):
        raise ValueError("choose an ear slope between 1 and 4")
    cheek = 1 / (1 + slope)
    ear_height = 2 * slope / (1 + slope * slope)
    if not 0.5 < brow < ear_height:
        raise ValueError("choose a brow above half height and below both ear tips")
    segments = square_with_diagonal()
    for side in (-1, 1):
        for near in (True, False):
            segments.append(
                (
                    3,
                    paper_point(0, 0, near),
                    paper_point(side * (1 - cheek), cheek, near),
                )
            )
    for near in (True, False):
        segments.append(
            (2, paper_point(brow - 1, brow, near), paper_point(1 - brow, brow, near))
        )
    landmarks = {
        "left_ear": paper_point(-1, 0),
        "right_ear": paper_point(1, 0),
        "left_cheek": paper_point(cheek - 1, cheek),
        "right_cheek": paper_point(1 - cheek, cheek),
        "nose": paper_point(0, 0),
        "forehead": paper_point(0, brow, False),
        "blaze": paper_point(0, 1),
    }
    return _canonical(segments), landmarks


def geometry(parameters, route="pointed"):
    if route == "ruff":
        return ruff_geometry(parameters)
    if route != "pointed":
        raise ValueError(f"unknown fox construction: {route}")
    if not isinstance(parameters, dict) or set(parameters) != {
        "ear_root",
        "ear_slope",
        "muzzle_depth",
    }:
        raise ValueError("expected ear_root, ear_slope and muzzle_depth parameters")
    p, s, d = (parameters[k] for k in ("ear_root", "ear_slope", "muzzle_depth"))
    if not all(
        type(v) in (int, float) and math.isfinite(v) and 0 < v < 1 for v in (p, s, d)
    ):
        raise ValueError("parameters must be finite fractions between zero and one")
    # On the right ear hinge, x + s*y = p. Its intersection with the
    # sloping paper edge x+y=1 is the lower material reference.
    q = (1 - p) / (1 - s)
    if q >= 1 - d or 1 - 2 * (1 - p) / (1 + s * s) <= 0:
        raise ValueError("ear folds would cross the muzzle fold or the centerline")
    segs = square_with_diagonal()
    for sign in (-1, 1):
        for front, assignment in ((True, 3), (False, 2)):
            segs.append(
                (
                    assignment,
                    paper_point(sign * p, 0, front),
                    paper_point(sign * (1 - q), q, front),
                )
            )
    # Fold just the near-layer point back up. The far layer keeps the nose
    # point and the turned flap reveals the second paper color.
    segs.append((3, paper_point(-d, 1 - d), paper_point(d, 1 - d)))
    landmarks = {
        "left_ear": paper_point(-1, 0),
        "right_ear": paper_point(1, 0),
        "left_cheek": paper_point(-p, 0),
        "right_cheek": paper_point(p, 0),
        "nose": paper_point(0, 1, False),
        "forehead": paper_point(0, 0),
        "muzzle_patch": paper_point(0, 1),
    }
    return _canonical(segs), landmarks


def write_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_plan(out, plan):
    if not isinstance(plan, dict) or not isinstance(plan.get("name"), str):
        raise TypeError("plan needs a variant name")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", plan["name"]):
        raise ValueError(
            "use letters, numbers, hyphens or underscores for a variant name"
        )
    segments, landmarks = geometry(plan.get("parameters"), plan.get("route", "pointed"))
    out.mkdir(parents=True, exist_ok=False)
    cp = out / "candidate.cp"
    write_cp(cp, segments)
    canonical_plan = json.dumps(
        plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    write_json(out / "plan.json", plan)
    write_json(out / "features.json", landmarks)
    write_json(
        out / "adaptation.json",
        {
            "base": "diagonal triangle",
            "candidate_sha256": hashlib.sha256(cp.read_bytes()).hexdigest(),
            "plan_sha256": hashlib.sha256(canonical_plan.encode("utf-8")).hexdigest(),
            "landmarks_normalized": landmarks,
            "validation": "unverified",
            "physical_trial": "untested",
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--recipe", type=Path, help="JSON list of variant plans under variants"
    )
    group.add_argument(
        "--plan",
        type=Path,
        help="rebuild one materialized plan directly into --out-dir",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="new candidate or comparison directory",
    )
    args = parser.parse_args()
    try:
        data = json.loads(
            (args.plan or args.recipe or DEFAULT_RECIPE).read_text(encoding="utf-8")
        )
        if args.plan:
            write_plan(args.out_dir, data)
        else:
            plans = data["variants"]
            if not isinstance(plans, list) or not plans:
                raise ValueError("recipe needs at least one variant")
            for plan in plans:
                if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", plan["name"]):
                    raise ValueError("invalid variant name")
                geometry(plan["parameters"], plan.get("route", "pointed"))
            if len({plan["name"] for plan in plans}) != len(plans):
                raise ValueError("recipe contains duplicate variant names")
            args.out_dir.mkdir(parents=True, exist_ok=False)
            for plan in plans:
                write_plan(args.out_dir / plan["name"], plan)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        parser.exit(2, f"fox_face: {exc}\n")


if __name__ == "__main__":
    main()
