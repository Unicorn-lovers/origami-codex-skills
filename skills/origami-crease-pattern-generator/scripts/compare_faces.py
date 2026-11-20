#!/usr/bin/env python3
"""Compare validated frontal face designs at the same paper scale."""

import argparse
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from base_preview import edges, layer_polygons, visible_view
from shape_cues import evaluate


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate(folder, profile):
    validation = folder / "validation"
    report = read_json(validation / "report.json")
    fold_file = validation / "candidate.fold"
    model_file = validation / "folded-model.json"
    digest = sha256(folder / "candidate.cp")
    if not (
        report.get("success")
        and report.get("input_sha256") == digest
        and report.get("evidence_sha256")
        == {"fold": sha256(fold_file), "foldedModel": sha256(model_file)}
    ):
        raise ValueError(
            f"{folder}: revalidate the current CP and solver files together"
        )
    model = read_json(model_file)
    fold = read_json(fold_file)
    _, points, view = visible_view(fold, model, read_json(folder / "features.json"))
    cues = evaluate(model, points, profile, view=view)
    if view != "Oriedita layer cells":
        raise ValueError(
            f"{folder}: orientation could not be registered to the layer solution"
        )
    roles = profile.get("landmarks", {})
    try:
        left, right, nose = (
            complex(*points[roles.get(role, role)])
            for role in ("left_ear", "right_ear", "nose")
        )
    except KeyError as error:
        raise ValueError(f"missing material landmark {error}") from error
    # All comparisons share a single sheet scale. Align the mid-ear-to-nose
    # axis by a rigid motion. Retain the width and height of each folded state.
    vertical = nose - (left + right) / 2
    if abs(vertical) < 1e-8:
        raise ValueError("cannot orient this face from its ear and nose landmarks")
    rotation = 1j / (vertical / abs(vertical))
    return {
        "model": model,
        "rotation": rotation,
        "cues": cues,
        "digest": digest,
        "id": folder.name,
        "features_digest": sha256(folder / "features.json"),
    }


def paper_cells(candidate, back, swap_paper):
    model = candidate["model"]
    face_sides = {face["faceId"]: face["frontViewSide"] for face in model["faces"]}
    cells = []
    for cell, ring in layer_polygons(model):
        face = cell["stackTopToBottom"][-1] if back else cell["topFace"]
        front = (face_sides[face] == "front") != back
        shape = [point * candidate["rotation"] for point in ring]
        if back:
            shape = [-point.conjugate() for point in shape]
        cells.append((face, front != swap_paper, shape))
    return cells


def bounds(cells):
    points = [p for _, _, ring in cells for p in ring]
    return (
        min(p.real for p in points),
        max(p.real for p in points),
        min(p.imag for p in points),
        max(p.imag for p in points),
    )


def render(groups, two_tone, scale, columns):
    tile = 330
    columns = min(columns, len(groups))
    rows = (len(groups) + columns - 1) // columns
    width, height = columns * tile, rows * tile
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#faf8f4"/>',
    ]
    for index, cells in enumerate(groups):
        xmin, xmax, ymin, ymax = bounds(cells)
        center = complex((xmin + xmax) / 2, (ymin + ymax) / 2)
        offset = tile * complex(index % columns + 0.5, index // columns + 0.5)

        def pixel(p, center=center, offset=offset):
            z = (p - center) * scale + offset
            return f"{z.real:.3f},{z.imag:.3f}"

        incidence = defaultdict(list)
        for face, front, ring in cells:
            color = ("#c46330" if front else "#fff3dc") if two_tone else "#4b4947"
            poly = " ".join(pixel(p) for p in ring)
            parts.append(
                f'<polygon points="{poly}" fill="{color}" stroke="{color}" stroke-width=".5"/>'
            )
            for a, b in edges(ring):
                incidence[tuple(sorted((pixel(a), pixel(b))))].append(face)
        if two_tone:
            for (a, b), owners in incidence.items():
                if len(owners) == 1 or len(set(owners)) > 1:
                    parts.append(
                        f'<path d="M{a} L{b}" fill="none" stroke="#674e42" stroke-width="1.15" stroke-linejoin="round"/>'
                    )
    return "\n".join(parts + ["</svg>", ""])


def compare(folders, profile_path, out, back=False, swap_paper=False):
    if len({p.name for p in folders}) != len(folders):
        raise ValueError("candidate directories must have distinct names")
    profile = read_json(profile_path)
    candidates = [load_candidate(p, profile) for p in folders]
    groups = [paper_cells(c, back, swap_paper) for c in candidates]
    extents = [bounds(group) for group in groups]
    scale = 275 / max(max(x1 - x0, y1 - y0) for x0, x1, y0, y1 in extents)
    out.mkdir(parents=True, exist_ok=False)
    columns = 2 if len(groups) == 4 else 3
    for name, two_tone in (("silhouettes", False), ("paper", True)):
        (out / (name + ".svg")).write_text(
            render(groups, two_tone, scale, columns), encoding="utf-8"
        )
    for index, group in enumerate(groups, 1):
        (out / f"view-{index}.svg").write_text(
            render([group], True, scale, 1), encoding="utf-8"
        )
    result = {
        "order": "left to right, then top to bottom",
        "side": "back" if back else "front",
        "orange_paper_side": "back" if swap_paper else "front",
        "profile_sha256": sha256(profile_path),
        "candidates": [
            {
                "position": i,
                "id": candidate["id"],
                "candidate_sha256": candidate["digest"],
                "features_sha256": candidate["features_digest"],
                "evaluation": candidate["cues"],
            }
            for i, candidate in enumerate(candidates, 1)
        ],
    }
    (out / "comparison.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("candidates", type=Path, nargs="+")
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="new directory for blind images and scores",
    )
    parser.add_argument(
        "--back",
        action="store_true",
        help="view from the reverse side of the solved layer stack",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="solve fresh candidate folders with Oriedita before comparing",
    )
    parser.add_argument("--jar", type=Path, help="Oriedita JAR for --validate")
    parser.add_argument("--swap-paper", action="store_true", help="swap the orange and cream sides on every sheet")
    args = parser.parse_args()
    try:
        if args.out_dir.exists():
            raise ValueError(f"output directory already exists: {args.out_dir}")
        if args.validate:
            for folder in args.candidates:
                validation = folder / "validation"
                if (validation / "report.json").is_file():
                    continue  # load_candidate rechecks the CP and both solver artifacts
                command = [
                    "node",
                    str(Path(__file__).with_name("validate_cp.mjs")),
                    str(folder / "candidate.cp"),
                    "--isolated",
                    "--out-dir",
                    str(validation),
                ]
                if args.jar:
                    command.extend(["--jar", str(args.jar)])
                subprocess.run(command, check=True)
        compare(args.candidates, args.profile, args.out_dir, args.back, args.swap_paper)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"compare_faces: {error}\n")


if __name__ == "__main__":
    main()
