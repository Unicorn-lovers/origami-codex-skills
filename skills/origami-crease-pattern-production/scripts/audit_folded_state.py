#!/usr/bin/env python3
"""Audit geometry and named feature tips in a Flat-Folder-style solver state."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def polygon_area(points):
    return abs(sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[i][1] * points[(i + 1) % len(points)][0]
        for i in range(len(points))
    )) / 2


def point_segment_distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return distance(point, a)
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2
    t = min(1.0, max(0.0, t))
    return distance(point, (a[0] + t * dx, a[1] + t * dy))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-7)
    args = parser.parse_args()

    state = json.loads(args.state.read_text(encoding="utf-8"))
    fold = state["fold"]
    vertices = fold["V"]
    folded = fold["Vf"]
    edges = fold["EV"]
    assignments = fold["EA"]
    faces = fold["FV"]
    tolerance = args.tolerance

    adjacency = [set() for _ in vertices]
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    seen = {0}
    stack = [0]
    while stack:
        for neighbor in adjacency[stack.pop()] - seen:
            seen.add(neighbor)
            stack.append(neighbor)

    boundary_edges = [edge for edge, assignment in zip(edges, assignments) if assignment == "B"]
    boundary_degree = {}
    for a, b in boundary_edges:
        boundary_degree[a] = boundary_degree.get(a, 0) + 1
        boundary_degree[b] = boundary_degree.get(b, 0) + 1

    xs = [point[0] for point in vertices]
    ys = [point[1] for point in vertices]
    bounds = (min(xs), min(ys), max(xs), max(ys))
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    paper_area = width * height
    boundary_on_rectangle = all(
        (
            abs(vertices[a][0] - vertices[b][0]) <= tolerance
            and (abs(vertices[a][0] - bounds[0]) <= tolerance or abs(vertices[a][0] - bounds[2]) <= tolerance)
        )
        or (
            abs(vertices[a][1] - vertices[b][1]) <= tolerance
            and (abs(vertices[a][1] - bounds[1]) <= tolerance or abs(vertices[a][1] - bounds[3]) <= tolerance)
        )
        for a, b in boundary_edges
    )

    face_area = 0.0
    max_rigid_error = 0.0
    for face in faces:
        before = [vertices[index] for index in face]
        after = [folded[index] for index in face]
        face_area += polygon_area(before)
        for i in range(len(face)):
            for j in range(i + 1, len(face)):
                max_rigid_error = max(
                    max_rigid_error,
                    abs(distance(before[i], before[j]) - distance(after[i], after[j])),
                )

    cells = state.get("cell", {})
    silhouette_segments = []
    if all(key in cells for key in ("P", "SP", "SC")):
        silhouette_segments = [
            (cells["P"][edge[0]], cells["P"][edge[1]])
            for edge, incident in zip(cells["SP"], cells["SC"])
            if len(incident) == 1
        ]

    feature_records = []
    features = json.loads(args.features.read_text(encoding="utf-8")) if args.features else {}
    for name, paper_point in features.items():
        nearest = min(range(len(vertices)), key=lambda index: distance(vertices[index], paper_point))
        source_error = distance(vertices[nearest], paper_point)
        if source_error > tolerance:
            raise ValueError(f"feature {name!r} is not a CP vertex; nearest error {source_error}")
        folded_point = folded[nearest]
        silhouette_distance = min(
            (point_segment_distance(folded_point, a, b) for a, b in silhouette_segments),
            default=None,
        )
        feature_records.append({
            "name": name,
            "vertex": nearest,
            "paper": vertices[nearest],
            "folded": folded_point,
            "silhouette_boundary_distance": silhouette_distance,
            "on_silhouette": silhouette_distance is not None and silhouette_distance <= tolerance,
        })

    coincident = []
    for i, left in enumerate(feature_records):
        for right in feature_records[i + 1:]:
            if distance(left["folded"], right["folded"]) <= tolerance:
                coincident.append([left["name"], right["name"]])

    report = {
        "source": str(args.state.resolve()),
        "scope": "Zero-thickness folded geometry; not a physical folding test",
        "vertices": len(vertices),
        "edges": len(edges),
        "faces": len(faces),
        "euler_V_minus_E_plus_F": len(vertices) - len(edges) + len(faces),
        "graph_connected": len(seen) == len(vertices),
        "boundary_degrees_all_two": bool(boundary_degree) and all(value == 2 for value in boundary_degree.values()),
        "boundary_on_rectangle": boundary_on_rectangle,
        "paper_area": paper_area,
        "summed_face_area": face_area,
        "max_face_distance_error": max_rigid_error,
        "silhouette_available": bool(silhouette_segments),
        "coincident_feature_tips": coincident,
        "feature_tips_inside_silhouette": [
            record["name"] for record in feature_records
            if silhouette_segments and not record["on_silhouette"]
        ],
        "features": feature_records,
    }
    report["geometry_passed"] = all((
        report["graph_connected"],
        report["boundary_degrees_all_two"],
        report["boundary_on_rectangle"],
        report["euler_V_minus_E_plus_F"] == 1,
        abs(face_area - paper_area) <= tolerance * max(1.0, paper_area),
        max_rigid_error <= tolerance * max(1.0, width, height),
    ))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(args.report.resolve()),
        "geometry_passed": report["geometry_passed"],
        "coincident_feature_tips": coincident,
        "feature_tips_inside_silhouette": report["feature_tips_inside_silhouette"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
