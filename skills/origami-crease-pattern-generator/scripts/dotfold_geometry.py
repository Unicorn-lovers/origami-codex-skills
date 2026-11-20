"""Decode and independently project DotFold's square sheet (unit grid, y up)."""

import ast
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from base_preview import edges, face_transforms, inside, transform

# The solver numbers tiles in screen order. These offsets lift them into FOLD's
# Cartesian plane, starting at north and increasing clockwise.
DIRECTIONS = ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))


def corner_edges(size):
    last = size - 1
    return (
        ((0, last), (1, size)),
        ((last, size), (size, last)),
        ((last, 0), (size, 1)),
        ((0, 1), (1, 0)),
    )


CORNER_EDGES = corner_edges(8)


def tile_catalog(source_dir):
    """Read the pinned checkout's literal tile table without executing its GUI."""
    path = Path(source_dir) / "TileDrawer.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    literals = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "TILE"
            for target in node.targets
        )
    ]
    if len(literals) != 1:
        raise ValueError("TileDrawer.py must contain exactly one literal TILE table")
    table = ast.literal_eval(literals[0])
    if (
        not isinstance(table, list)
        or len(table) != 36
        or any(
            not isinstance(row, list)
            or len(row) != 8
            or any(type(bit) is not int or bit not in (0, 1) for bit in row)
            for row in table
        )
    ):
        raise ValueError("expected 36 tile masks of eight binary directions")
    return table


def edge_key(a, b):
    return (a, b) if a < b else (b, a)


def segment_assignments(cpstr, corners, table, size=8):
    interior = size - 1
    tile_count = interior**2
    if (
        not isinstance(cpstr, str)
        or re.fullmatch(rf"[0-9]{{{2 * tile_count}}}", cpstr) is None
    ):
        raise ValueError(f"CPSTR must contain {tile_count} two-digit tile indices")
    if len(corners) != 4 or any(
        type(bit) is not int or bit not in (0, 1) for bit in corners
    ):
        raise ValueError(
            "CORNERS must contain four binary integers in TL, TR, BR, BL order"
        )

    states = {}
    for i in range(tile_count):
        tile = int(cpstr[2 * i : 2 * i + 2])
        if tile >= len(table):
            raise ValueError(f"tile index {tile} is out of range at position {i}")
        x, y = 1 + i % interior, interior - i // interior
        for (dx, dy), enabled in zip(DIRECTIONS, table[tile]):
            edge = edge_key((x, y), (x + dx, y + dy))
            if states.setdefault(edge, enabled) != enabled:
                raise ValueError(f"adjacent tiles disagree on edge {edge}")
    states.update(zip(corner_edges(size), corners))
    used = {edge for edge in states if states[edge]}
    result = {}
    for (x, y), (u, v) in used:
        # The only possible non-endpoint intersections are the two diagonals
        # of one unit cell. Give both the same explicit midpoint vertex.
        if x != u and y != v and ((x, v), (u, y)) in used:
            middle = ((x + u) / 2, (y + v) / 2)
            result[(x, y), middle] = "U"
            result[middle, (u, v)] = "U"
        else:
            result[(x, y), (u, v)] = "U"
    for i in range(size):
        for side in (0, size):
            result[(side, i), (side, i + 1)] = "B"
            result[(i, side), (i + 1, side)] = "B"
    return result


def bounded_faces(coords, graph, size=8):
    """Walk each planar half-edge with its face on the left."""
    adjacent = defaultdict(list)
    for a, b in graph:
        adjacent[a].append(b)
        adjacent[b].append(a)
    successor = {}
    for vertex, neighbors in adjacent.items():
        x, y = coords[vertex]
        neighbors.sort(key=lambda n: math.atan2(coords[n][1] - y, coords[n][0] - x))
        for i, incoming in enumerate(neighbors):
            successor[incoming, vertex] = (vertex, neighbors[i - 1])
    visited = set()
    faces = []
    area_sum = 0
    for start in successor:
        if start in visited:
            continue
        ring = []
        edge = start
        while edge not in visited:
            visited.add(edge)
            ring.append(edge[0])
            edge = successor[edge]
        area2 = sum(
            coords[a][0] * coords[b][1] - coords[b][0] * coords[a][1]
            for a, b in edges(ring)
        )
        if area2 > 0:
            if len(set(ring)) != len(ring):
                raise ValueError("crease graph contains a non-simple paper face")
            faces.append(ring)
            area_sum += area2 / 2
    if area_sum != size**2 or len(coords) - len(graph) + len(faces) != 1:
        raise ValueError(f"crease graph does not tile the {size}-by-{size} paper")
    return faces


def make_fold(cpstr, corners, source_dir=None, *, size=8):
    """Decode the upstream or generalized solver's row-major tile indices."""
    if size not in (8, 16):
        raise ValueError("paper size must be 8 or 16")
    if source_dir is None:
        from dotfold_grid16 import TILE_CATALOG

        table = TILE_CATALOG
    else:
        table = tile_catalog(source_dir)
    segments = segment_assignments(cpstr, corners, table, size)
    coords = sorted({vertex for edge in segments for vertex in edge})
    ids = {p: i for i, p in enumerate(coords)}
    ordered = sorted(segments)
    graph = [[ids[a], ids[b]] for a, b in ordered]
    return {
        "file_spec": 1.1,
        "file_creator": "origami-crease-pattern-generator",
        "frame_title": "DotFold crease pattern",
        "frame_classes": ["creasePattern"],
        "frame_attributes": ["2D"],
        "frame_unit": "unit",
        "vertices_coords": [list(xy) for xy in coords],
        "edges_vertices": graph,
        "edges_assignment": [segments[key] for key in ordered],
        "faces_vertices": bounded_faces(coords, graph, size),
    }


def sheet_size(fold):
    """DotFold uses a square with its lower-left corner at the origin."""
    return max(x for x, _ in fold["vertices_coords"])


def crease_svg(fold):
    size = sheet_size(fold)
    palette = {
        "B": "#24262a",
        "U": "#586577",
        "M": "#ca3c36",
        "V": "#2875ad",
        "F": "#999",
    }
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="528" height="528" viewBox="-.2 -.2 {size + 0.4:g} {size + 0.4:g}">',
        "<title>DotFold crease pattern</title>",
        f'<g transform="translate(0 {size:g}) scale(1 -1)" stroke-linecap="round">',
        f'<rect width="{size:g}" height="{size:g}" fill="white"/>',
    ]
    for (a, b), assignment in zip(fold["edges_vertices"], fold["edges_assignment"]):
        x, y = fold["vertices_coords"][a]
        u, v = fold["vertices_coords"][b]
        width = ".042" if assignment == "B" else ".025"
        lines.append(
            f'<line x1="{x:g}" y1="{y:g}" x2="{u:g}" y2="{v:g}" '
            f'stroke="{palette[assignment]}" stroke-width="{width}" data-assignment="{assignment}"/>'
        )
    return "\n".join(lines + ["</g>", "</svg>", ""])


def projected_faces(fold):
    """Return folded vertex coordinates and per-face flip flags, without layer order."""
    frames = face_transforms(fold, active_creases=("U", "M", "V"))
    coords = [None] * len(fold["vertices_coords"])
    flipped = []
    incidence = defaultdict(list)
    for fid, face in enumerate(fold["faces_vertices"]):
        flipped.append(frames[fid][2])
        for a, b in edges(face):
            incidence[edge_key(a, b)].append(fid)
            z = transform(complex(*fold["vertices_coords"][a]), frames[fid])
            xy = (round(2 * z.real) / 2, round(2 * z.imag) / 2)
            if abs(z - complex(*xy)) > 1e-8 or (
                coords[a] is not None and coords[a] != xy
            ):
                raise ValueError(
                    "reflection around a vertex does not close on the DotFold grid"
                )
            coords[a] = xy
    for (a, b), kind in zip(fold["edges_vertices"], fold["edges_assignment"]):
        touching = incidence[edge_key(a, b)]
        if kind == "B" and len(touching) == 1:
            continue
        if len(touching) != 2 or (flipped[touching[0]] != flipped[touching[1]]) != (
            kind in ("M", "V", "U")
        ):
            raise ValueError("face reflection is inconsistent across a crease")
    return coords, flipped


def coverage_cells(fold):
    """Compute the layer count on each of four triangular atoms in each unit cell.

    All projected edges lie on grid lines or on 45-degree lines through grid
    points. The two diagonals are therefore sufficient to partition every cell.
    The four interior probes represent the exact areas of these atoms.
    """
    coords, _ = projected_faces(fold)
    counts = defaultdict(lambda: [0] * 4)
    probes = ((0.5, 0.25), (0.75, 0.5), (0.5, 0.75), (0.25, 0.5))
    for face in fold["faces_vertices"]:
        poly = [coords[i] for i in face]
        for (x, y), (u, v) in edges(poly):
            if not (
                x == u
                and x.is_integer()
                or y == v
                and y.is_integer()
                or x - y == u - v
                and (x - y).is_integer()
                or x + y == u + v
                and (x + y).is_integer()
            ):
                raise ValueError("projected face edge is outside the DotFold line grid")
        xs, ys = zip(*poly)
        for x in range(math.floor(min(xs)), math.ceil(max(xs))):
            for y in range(math.floor(min(ys)), math.ceil(max(ys))):
                for i, (dx, dy) in enumerate(probes):
                    if inside((x + dx, y + dy), poly):
                        counts[x, y][i] += 1
    if sum(sum(cell) for cell in counts.values()) != 4 * sheet_size(fold) ** 2:
        raise ValueError("projected faces do not conserve sheet area")
    return counts


# Matrices act on projected Cartesian coordinates (both target and paper y up).
ORIENTATIONS = [
    (1, 0, 0, 1),
    (0, -1, 1, 0),
    (-1, 0, 0, -1),
    (0, 1, -1, 0),
    (-1, 0, 0, 1),
    (0, -1, -1, 0),
    (1, 0, 0, -1),
    (0, 1, 1, 0),
]


def register_cells(cells, target):
    """Maximize unit-cell intersection over translations and square symmetries."""
    best = None
    for matrix in ORIENTATIONS:
        a, b, c, d = matrix
        # Rotate/reflect cell centers and recover their lower-left corners.
        oriented = {
            (a * x + b * y + (a + b - 1) // 2, c * x + d * y + (c + d - 1) // 2)
            for x, y in cells
        }
        offsets = Counter((u - x, v - y) for x, y in oriented for u, v in target)
        matches = max(offsets.values(), default=0)
        if best is None or matches > best[0]:
            offset = min(
                (shift for shift in offsets if offsets[shift] == matches),
                default=(0, 0),
            )
            best = matches, matrix, offset
    matches, matrix, offset = best
    return {
        "exact": matches == len(cells) == len(target),
        "missingCells": len(target) - matches,
        "extraCells": len(cells) - matches,
        "matrix": list(matrix),
        "translation": list(offset),
    }


def projection(fold, bitmap):
    """Compare the exact odd-coverage region to the target in its pixel frame."""
    size = int(sheet_size(fold))
    if (
        not isinstance(bitmap, str)
        or len(bitmap) != size**2
        or re.fullmatch(r"[01]+", bitmap) is None
    ):
        raise ValueError(f"projection expects {size**2} row-major binary digits")
    target = {
        (i % size, size - 1 - i // size) for i, bit in enumerate(bitmap) if bit == "1"
    }
    counts = coverage_cells(fold)
    parity = set()
    for pos, values in counts.items():
        if len({n % 2 for n in values}) != 1:
            raise ValueError("projected paper boundary cuts through a target pixel")
        if values[0] % 2:
            parity.add(pos)
    footprint = {pos for pos in counts if any(counts[pos])}
    full = {pos for pos in footprint if all(counts[pos])}
    footprint_quarters = sum(n > 0 for values in counts.values() for n in values)
    reg = register_cells(parity, target)
    return {
        "paperArea": size**2,
        "targetCells": len(target),
        "oddCoverageCells": len(parity),
        "oddCoverageRegistration": reg,
        "footprintArea": footprint_quarters / 4,
        "partialFootprintCells": len(footprint - full),
        "footprintMatchesTarget": footprint == full
        and register_cells(full, target)["exact"],
        "maxLayers": max(max(v) for v in counts.values()),
        "visibleColors": "unverified",
    }
