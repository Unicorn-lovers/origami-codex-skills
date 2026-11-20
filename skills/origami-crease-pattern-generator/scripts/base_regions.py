"""Check reservations on the unfolded paper using the catalog's convex polygons."""

from __future__ import annotations

import argparse
import json
import math
from itertools import combinations
from pathlib import Path

EPS = 1e-12
BASES = Path(__file__).resolve().parent.parent / "assets" / "bases"


def cross(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def signed_area(polygon):
    return (
        sum(
            a[0] * b[1] - b[0] * a[1]
            for a, b in zip(polygon, polygon[1:] + polygon[:1])
        )
        / 2
    )


def oriented(polygon):
    return polygon if signed_area(polygon) >= 0 else polygon[::-1]


def overlap_polygon(first, second):
    """Clip a convex subject against a convex mask. Boundary contact has zero area."""
    clipped = list(first)
    mask = oriented(second)
    for a, b in zip(mask, mask[1:] + mask[:1]):
        if not clipped:
            break
        source, clipped = clipped, []
        previous = source[-1]
        d0 = cross(a, b, previous)
        for current in source:
            d1 = cross(a, b, current)
            if (d0 < -EPS) != (d1 < -EPS):
                t = max(0, min(1, d0 / (d0 - d1)))
                clipped.append(
                    [previous[i] + t * (current[i] - previous[i]) for i in (0, 1)]
                )
            if d1 >= -EPS:
                clipped.append(current)
            previous, d0 = current, d1
    return clipped


def conflicts(base_map, assignments, parents=None):
    """Report positive-area overlap between independent feature reservations.

    A child explicitly listed in parents shares a directly allocated parent ID;
    it reserves no additional paper until an actual split defines child polygons.
    """
    regions = {**base_map["flaps"], **base_map["surfaces"]}
    for feature, region in assignments.items():
        if region not in regions:
            raise ValueError(f"unknown region for {feature}: {region}")
    parents = parents or {}
    for child, parent in parents.items():
        if (
            child not in assignments
            or parent not in assignments
            or parent in parents
            or assignments[child] != assignments[parent]
        ):
            raise ValueError(
                f"{child} must share the region of a directly assigned parent"
            )
    reserved = [
        (name, region) for name, region in assignments.items() if name not in parents
    ]
    result = []
    for (name_a, id_a), (name_b, id_b) in combinations(reserved, 2):
        clipped = overlap_polygon(regions[id_a]["polygon"], regions[id_b]["polygon"])
        area = abs(signed_area(clipped))
        if area > EPS:
            result.append(
                {
                    "features": [name_a, name_b],
                    "regions": [id_a, id_b],
                    "area_fraction": area,
                    "polygon": clipped,
                }
            )
    return result


def sheet_point(point):
    return (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(
            isinstance(n, (int, float))
            and not isinstance(n, bool)
            and math.isfinite(n)
            and 0 <= n <= 1
            for n in point
        )
    )


def check_catalog(base_dir=BASES):
    maps = json.loads((base_dir / "regions.json").read_text())
    catalog = json.loads((base_dir / "catalog.json").read_text())["bases"]
    if set(maps) != {b["id"] for b in catalog}:
        raise ValueError("base IDs differ between regions and catalog")
    for base in catalog:
        base_id = base["id"]
        group = maps[base_id]
        flaps, surfaces = group["flaps"], group["surfaces"]
        if (
            set(flaps) != {f["id"] for f in base["flaps"]}
            or len(surfaces) != base["broad_surfaces"]
        ):
            raise ValueError(f"{base_id}: incomplete region map")
        if set(surfaces).intersection(flaps):
            raise ValueError(f"{base_id}: region IDs must be unique")
        vertices = set()
        for line in (base_dir / base["cp"]).read_text().splitlines():
            _, x1, y1, x2, y2 = line.split()
            vertices.update(
                [
                    (float(x1) / 1000, float(y1) / 1000),
                    (float(x2) / 1000, float(y2) / 1000),
                ]
            )
        for key, region in {**flaps, **surfaces}.items():
            points = region["polygon"]
            if len(points) < 3 or not all(map(sheet_point, points)):
                raise ValueError(
                    f"{base_id}/{key}: expected at least three sheet points"
                )
            polygon = oriented(points)
            edges = list(zip(polygon, polygon[1:] + polygon[:1]))
            if (
                signed_area(polygon) <= EPS
                or len(set(map(tuple, points))) != len(points)
                or any(cross(a, b, p) < -EPS for a, b in edges for p in polygon)
            ):
                raise ValueError(
                    f"{base_id}/{key}: expected a convex reservation polygon"
                )
            if key in flaps:
                anchors = [region["tip"], region["root"]]
                if (
                    not all(map(sheet_point, anchors))
                    or math.dist(*anchors) < EPS
                    or any(cross(a, b, p) < -EPS for a, b in edges for p in anchors)
                ):
                    raise ValueError(f"{base_id}/{key}: invalid tip or root anchor")
                if not any(math.dist(anchors[0], vertex) < 1e-9 for vertex in vertices):
                    raise ValueError(
                        f"{base_id}/{key}: tip does not identify a CP vertex"
                    )
    return len(maps)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        required=True,
        help="check the bundled region maps",
    )
    parser.parse_args()
    print(f"Checked region maps for {check_catalog()} bases.")
