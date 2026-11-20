#!/usr/bin/env python3
"""Measure frontal, pointed-eared face cues on a registered folded silhouette."""

import argparse
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from base_preview import edges, layer_polygons, visible_view

ROLES = ("left_ear", "right_ear", "nose", "left_cheek", "right_cheek")
# These are adjustable design targets for a triangular-eared face.
# Each pair gives a comparison threshold and a more distinct silhouette target.
LIMITS = {
    "ear_angle_max_deg": (95.0, 45.0),
    "ear_flank_drop_min": (0.015, 0.065),
    "ear_spacing_min": (0.35, 0.8),
    "notch_depth_min": (0.09, 0.25),
    "symmetry_error_max": (0.07, 0.005),
    "muzzle_width_ratio_max": (0.65, 0.35),
    "nose_angle_max_deg": (105.0, 55.0),
}
CUES = {
    "ear_peaks": "Two triangular ear peaks",
    "forehead_notch": "Dip between the ears",
    "bilateral": "Balanced left and right silhouette",
    "muzzle_taper": "Cheeks narrow toward the nose",
}


def dot(a, b):
    return (a.conjugate() * b).real


def closest(p, a, b):
    ab = b - a
    if abs(ab) == 0:
        return a
    t = min(1, max(0, dot(p - a, ab) / abs(ab) ** 2))
    return a + t * ab


def outer_ring(model):
    """Trace a single outline, splitting T-junction edges before cancelling seams."""
    polygons = [poly for _, poly in layer_polygons(model)]
    points = {
        complex(round(p.real, 7), round(p.imag, 7)) for poly in polygons for p in poly
    }
    if len(points) < 3:
        raise ValueError("no complete folded silhouette")
    counts = Counter()
    key = lambda z: (z.real, z.imag)
    for poly in polygons:
        for a, b in edges(poly):
            if abs(b - a) < 1e-7:
                continue
            on_edge = sorted(
                (p for p in points if abs(p - closest(p, a, b)) < 2e-6),
                key=lambda p: dot(p - a, b - a),
            )
            for u, v in itertools.pairwise(on_edge):
                counts[tuple(sorted((u, v), key=key))] += 1
    neighbors = defaultdict(list)
    for (u, v), n in counts.items():
        if n == 1:
            neighbors[u].append(v)
            neighbors[v].append(u)
        elif n != 2:
            raise ValueError("ambiguous folded-cell boundary")
    if not neighbors or any(len(v) != 2 for v in neighbors.values()):
        raise ValueError("open or branching folded-cell boundary")
    ring = [next(iter(neighbors))]
    previous, point = None, ring[0]
    while True:
        nxt = next(neighbor for neighbor in neighbors[point] if neighbor != previous)
        if nxt == ring[0]:
            break
        ring.append(nxt)
        previous, point = point, nxt
    if len(ring) != len(neighbors):
        raise ValueError("the selected view has multiple boundary loops")
    return ring


def bounds_for(profile):
    thresholds = profile.get("thresholds", {})
    preferred = profile.get("preferred", {})
    if (set(thresholds) | set(preferred)) - LIMITS.keys():
        raise ValueError("unknown shape threshold")
    limits = {}
    for name, (threshold, ideal) in LIMITS.items():
        a, b = thresholds.get(name, threshold), preferred.get(name, ideal)
        if not all(type(x) in (float, int) and math.isfinite(x) for x in (a, b)):
            raise ValueError(f"{name} thresholds must be finite numbers")
        if (b - a) * (ideal - threshold) <= 0:
            raise ValueError(f"{name} preferred value must improve on its threshold")
        limits[name] = (a, b)
    return limits


def corner(ring, tip, span=0.15):
    """Measure the two sides at a fixed arc distance from a named material tip."""
    segments = list(edges(ring))
    i = min(range(len(ring)), key=lambda j: abs(tip - closest(tip, *segments[j])))
    anchor = closest(tip, *segments[i])
    offset = abs(tip - anchor)

    def walk(direction):
        pos = anchor
        remaining = span
        idx = i if direction == -1 else (i + 1) % len(ring)
        for _ in range(len(ring) + 1):
            delta = ring[idx] - pos
            if abs(delta) >= remaining:
                return (pos + delta * remaining / abs(delta)) - anchor
            remaining -= abs(delta)
            pos = ring[idx]
            idx = (idx + direction) % len(ring)
        raise ValueError("outline is too short to measure a corner")

    before, after = walk(-1), walk(1)
    angle = math.degrees(
        math.acos(max(-1, min(1, dot(before, after) / (abs(before) * abs(after)))))
    )
    # Clockwise and anticlockwise traces must agree on a concave corner.
    winding = sum((a.conjugate() * b).imag for a, b in edges(ring))
    if (before.conjugate() * after).imag * winding > 0:
        angle = 360 - angle
    return offset, angle, -max(before.imag, after.imag)


def crossings(ring, at, vertical=False):
    result = []
    for a, b in edges(ring):
        x1, y1 = (a.imag, a.real) if vertical else (a.real, a.imag)
        x2, y2 = (b.imag, b.real) if vertical else (b.real, b.imag)
        if (y1 <= at < y2) or (y2 <= at < y1):
            result.append(x1 + (at - y1) * (x2 - x1) / (y2 - y1))
    if len(result) < 2:
        raise ValueError("silhouette section unavailable")
    return min(result), max(result)


def assess_ring(ring, points, profile):
    required = profile.get("required", list(CUES))
    if (
        not isinstance(required, list)
        or not required
        or len(set(required)) != len(required)
        or not set(required) <= CUES.keys()
    ):
        raise ValueError("required must list supported cue names")
    limits = bounds_for(profile)
    roles = {name: profile.get("landmarks", {}).get(name, name) for name in ROLES}
    missing = [name for name in roles.values() if name not in points]
    if missing:
        raise ValueError("missing material landmarks: " + ", ".join(missing))
    p = {role: complex(*points[name]) for role, name in roles.items()}
    if not all(math.isfinite(z.real) and math.isfinite(z.imag) for z in p.values()):
        raise ValueError("material landmark coordinates must be finite")
    center = (p["left_ear"] + p["right_ear"]) / 2
    up = center - p["nose"]
    if abs(up) < 1e-7:
        raise ValueError("ear midpoint and nose coincide")
    right = -1j * up
    if dot(right, p["right_ear"] - p["left_ear"]) < 0:
        right = -right

    def align(z):
        z = z - p["nose"]
        return complex(dot(z, right), dot(z, up)) / abs(up) ** 2

    ring = [align(z) for z in ring]
    local = {role: align(z) for role, z in p.items()}
    ears = [local["left_ear"], local["right_ear"]]
    cheeks = [local["left_cheek"], local["right_cheek"]]
    report = {}

    def cue(name, measures, additional_ok=True):
        merits, passes = [], []
        for metric, value in measures.items():
            bound, best = limits[metric]
            t = (value - bound) / (best - bound)
            passes.append(t >= -1e-7)
            merits.append(min(1, max(0, 0.5 + t / 2)))
        report[name] = {
            "label": CUES[name],
            "passed": all(passes) and additional_ok,
            "score": round(100 * min(merits), 2) if additional_ok else 0.0,
            "measurements": {k: round(v, 6) for k, v in measures.items()},
            "outside_threshold": [
                metric for metric, ok in zip(measures, passes) if not ok
            ],
        }

    # Coordinates use nose at zero and ear midpoint at unit height.
    tips = [corner(ring, ear) for ear in ears]
    cue(
        "ear_peaks",
        {
            "ear_angle_max_deg": max(t[1] for t in tips),
            "ear_flank_drop_min": min(t[2] for t in tips),
            "ear_spacing_min": ears[1].real - ears[0].real,
        },
        additional_ok=all(t[0] < 1e-5 for t in tips),
    )
    _, brow = crossings(ring, 0, vertical=True)
    cue("forehead_notch", {"notch_depth_min": min(e.imag for e in ears) - brow})

    def mirror(p):
        return complex(-p.real, p.imag)

    # Sample also within edges so staggered diagonals cannot hide behind close vertices.
    samples = [a + (b - a) * n / 4 for a, b in edges(ring) for n in range(4)]
    contour_error = max(
        min(abs(mirror(z) - closest(mirror(z), a, b)) for a, b in edges(ring))
        for z in samples
    )
    paired_error = max(abs(mirror(pair[0]) - pair[1]) for pair in (ears, cheeks))
    cue("bilateral", {"symmetry_error_max": max(contour_error, paired_error)})
    height = sum(c.imag for c in cheeks) / 2
    lower_width = upper_width = 0
    if height > 1e-6:
        try:
            x0, x1 = crossings(ring, 0.25 * height)
            lower_width = x1 - x0
            x0, x1 = crossings(ring, 0.75 * height)
            upper_width = x1 - x0
        except ValueError:
            pass
    cheek_offsets = [corner(ring, c)[0] for c in cheeks]
    nose_offset, nose_angle, _ = corner(ring, 0j)
    cue(
        "muzzle_taper",
        {
            "muzzle_width_ratio_max": lower_width / upper_width if upper_width else 1.0,
            "nose_angle_max_deg": nose_angle,
        },
        additional_ok=(
            upper_width > 1e-6
            and all(o < 1e-5 for o in [*cheek_offsets, nose_offset])
            and min(z.imag for z in ring) >= -1e-5
            and cheeks[0].real < 0 < cheeks[1].real
        ),
    )
    failed = [name for name in required if not report[name]["passed"]]
    return {
        "status": "revise" if failed else "pass",
        "score": round(sum(report[k]["score"] for k in required) / len(required), 2),
        "failed_cues": failed,
        "cues": report,
        "frame": {
            "nose": [p["nose"].real, p["nose"].imag],
            "height": abs(up),
            "up": [up.real / abs(up), up.imag / abs(up)],
            "right": [right.real / abs(up), right.imag / abs(up)],
        },
    }


def undetermined(reason):
    return {
        "status": "undetermined",
        "score": None,
        "reason": str(reason),
        "cues": {},
        "failed_cues": [],
    }


def evaluate(model, folded_landmarks, profile, *, view="Oriedita layer cells"):
    try:
        if view != "Oriedita layer cells":
            raise ValueError(
                "material landmarks could not be registered to layer cells"
            )
        return assess_ring(outer_ring(model), folded_landmarks, profile)
    except (ValueError, KeyError, IndexError, ZeroDivisionError, TypeError) as exc:
        return undetermined(exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("fold", "model", "features", "profile"):
        parser.add_argument(argument, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    def read(path):
        return json.loads(path.read_text(encoding="utf-8"))

    try:
        fold, model, features, profile = (
            read(path) for path in (args.fold, args.model, args.features, args.profile)
        )
        _, points, view = visible_view(fold, model, features)
        result = evaluate(model, points, profile, view=view)
    except (
        OSError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
        ZeroDivisionError,
    ) as exc:
        result = undetermined(exc)
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
