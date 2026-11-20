#!/usr/bin/env python3
"""Generate and validate a named adaptation of a bundled origami base."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from base_operations import adapted_point, apply_operations, split_tip_points
from base_preview import outline_checks, svg_view, visible_view
from base_regions import BASES, conflicts
from generate_base_library import number


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_segments(path):
    segments = []
    for row in path.read_text().splitlines():
        code, *xy = row.split()
        x, y, u, v = (float(coord) / 1000 for coord in xy)
        segments.append((int(code), (x, y), (u, v)))
    return segments


def write_cp(path, segments):
    rows = [
        f"{code} " + " ".join(number(1000 * v) for v in (*a, *b))
        for code, a, b in segments
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def prepare(plan):
    if not isinstance(plan, dict):
        raise TypeError("the plan must be a JSON object")
    base = plan.get("base")
    maps = read_json(BASES / "regions.json")
    if not isinstance(base, str) or base not in maps:
        raise ValueError(f"choose a base from {', '.join(maps)}")
    assignments = plan.get("assignments")
    if (
        not isinstance(assignments, dict)
        or not assignments
        or not all(
            isinstance(k, str) and k.strip() and isinstance(v, str)
            for k, v in assignments.items()
        )
    ):
        raise ValueError("assignments must map feature names to region IDs")
    base_map = maps[base]
    overlap = conflicts(base_map, assignments)
    regions = {**base_map["flaps"], **base_map["surfaces"]}
    polygons = {name: regions[key]["polygon"] for name, key in assignments.items()}
    landmarks = {}
    for name, key in assignments.items():
        poly = polygons[name]
        landmarks[name] = regions[key].get("tip") or [
            sum(t) / len(poly) for t in zip(*poly)
        ]
    operations = plan.get("operations")
    if not isinstance(operations, list) or not all(
        isinstance(op, dict) for op in operations
    ):
        raise ValueError("operations must be an array of edit objects")
    ops = [{k: v for k, v in op.items() if k != "children"} for op in operations]
    source = BASES / (base + ".cp")
    segments = apply_operations(read_segments(source), ops, base_map, base)
    for op in operations:
        if "children" not in op:
            continue
        names = op["children"]
        if (
            op["op"] != "split_tip"
            or not isinstance(names, list)
            or len(names) != 2
            or not all(
                isinstance(n, str) and n.strip() and n not in landmarks for n in names
            )
            or names[0] == names[1]
        ):
            raise ValueError(
                "split_tip children must contain two unique new landmark names"
            )
        flap = base_map["flaps"][op["flap"]]
        for name, key in assignments.items():
            if key == op["flap"]:
                landmarks[name] = flap["root"]
        tips = split_tip_points(flap, op.get("fraction", 0.35))
        landmarks.update(zip(names, tips))
    landmarks = {name: adapted_point(p, ops) for name, p in landmarks.items()}
    polygons = {
        name: [adapted_point(p, ops) for p in poly] for name, poly in polygons.items()
    }
    return segments, landmarks, polygons, overlap, source


def run(args):
    plan = read_json(args.plan)
    segments, landmarks, polygons, overlap, source = prepare(plan)
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cp = out / "candidate.cp"
    write_cp(cp, segments)
    save_json(out / "plan.json", plan)
    save_json(out / "features.json", landmarks)
    (out / "paper.svg").write_text(
        svg_view(
            segments,
            landmarks,
            "Paper landmarks",
            "Shaded areas show the original material reservations.",
            polygons,
        ),
        encoding="utf-8",
    )
    record = {
        "base": plan["base"],
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "candidate_sha256": hashlib.sha256(cp.read_bytes()).hexdigest(),
        "source_region_conflicts": overlap,
        "landmarks_normalized": landmarks,
        "validation": "unverified",
        "physical_trial": "untested",
    }
    report = out / "adaptation.json"
    save_json(report, record)
    if args.geometry_only:
        return 0
    validator = Path(__file__).with_name("validate_cp.mjs")
    command = [
        "node",
        str(validator),
        str(cp),
        "--isolated",
        "--out-dir",
        str(out / "validation"),
    ]
    if args.jar:
        command.extend(["--jar", str(args.jar)])
    status = subprocess.run(command, check=False)
    validation_path = out / "validation" / "report.json"
    validation = read_json(validation_path) if validation_path.exists() else {}
    if status.returncode or not validation.get("success"):
        record["validation"] = "unverified"
        record["validator_exit_code"] = status.returncode
        save_json(report, record)
        raise ValueError(f"validation did not complete successfully; inspect {out}")
    evidence = validation["evidence"]
    record["validation"] = "calculated_flat_fold"
    save_json(report, record)
    model = read_json(Path(evidence["foldedModel"]))
    lines, folded, title = visible_view(
        read_json(Path(evidence["fold"])), model, landmarks
    )
    (out / "folded.svg").write_text(
        svg_view(
            lines,
            folded,
            title,
            "Numbered points follow the material through the fold, including covered layers.",
            model=model if title == "Oriedita layer cells" else None,
        ),
        encoding="utf-8",
    )
    record.update(folded_landmarks=folded, folded_view=title)
    if title == "Oriedita layer cells":
        record["on_projected_outline"] = outline_checks(lines, folded)
    save_json(report, record)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="new directory for this candidate"
    )
    parser.add_argument("--jar", type=Path, help="Oriedita local-control JAR")
    parser.add_argument(
        "--geometry-only",
        action="store_true",
        help="export unverified geometry without Oriedita",
    )
    args = parser.parse_args()
    try:
        return run(args)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"adapt_base: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
