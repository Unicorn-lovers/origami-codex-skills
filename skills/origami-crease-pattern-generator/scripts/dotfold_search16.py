"""Generate bounded one-sheet crease graphs for an exact 16×16 pixel target."""

import time
from itertools import pairwise

from dotfold_boundary16 import boundary_assignments, outline_edges
from dotfold_geometry import bounded_faces, make_fold
from dotfold_grid16 import solve_tiles

SIZE = 16
TILE_SECONDS = 0.8
TILES_PER_BOUNDARY = 3


def simple_folds():
    """A corner turn hides a square of the original face; an edge turn hides a strip."""
    for side in range(4):

        def rotate(x, y, turns=side):
            for _ in range(turns):
                x, y = SIZE - y, x
            return x, y

        for k in range(1, SIZE + 1):
            for corner in (True, False):
                if not corner and 2 * k > SIZE:
                    continue
                width, height = (k, k) if corner else (SIZE, 2 * k)
                mask = 0
                for y in range(height):
                    for x in range(width):
                        u, v = rotate(x + 0.5, y + 0.5)
                        mask |= 1 << (int(v) * SIZE + int(u))
                line = (
                    (rotate(k, 0), rotate(0, k))
                    if corner
                    else (rotate(0, k), rotate(SIZE, k))
                )
                yield mask, line


def disjoint_turns(bits, deadline):
    """Invert disjoint turned regions from the bitmap. All coordinates here use image y."""
    missing = sum(1 << i for i, bit in enumerate(bits) if bit == "0")
    options = [(mask, line) for mask, line in simple_folds() if mask & missing == mask]
    options.sort(key=lambda item: item[0].bit_count(), reverse=True)

    def cover(remaining, chosen):
        if time.monotonic() >= deadline:
            raise TimeoutError
        if not remaining:
            yield chosen
            return
        first = remaining & -remaining
        for mask, line in options:
            if mask & first and mask & remaining == mask:
                yield from cover(remaining ^ mask, (*chosen, line))

    yield from cover(missing, ())


def straight_graph(lines):
    corners = [(0, 0), (SIZE, 0), (SIZE, SIZE), (0, SIZE)]
    points = sorted(set(corners).union(p for line in lines for p in line))
    index = {p: i for i, p in enumerate(points)}
    boundary = []
    for axis in (0, 1):
        for side in (0, SIZE):
            along = [i for i, p in enumerate(points) if p[axis] == side]
            boundary.extend(pairwise(along))
    creases = [(index[a], index[b]) for a, b in lines]
    edges = boundary + creases
    coords = [[x, SIZE - y] for x, y in points]
    return {
        "file_spec": 1.1,
        "file_creator": "16x16 pixel crease search",
        "frame_classes": ["creasePattern"],
        "vertices_coords": coords,
        "edges_vertices": edges,
        "edges_assignment": ["B"] * len(boundary) + ["U"] * len(creases),
        "faces_vertices": bounded_faces(coords, edges, size=SIZE),
    }


def candidates(bits, deadline, stats):
    """Try cheap constructions, then search boundary placements and compatible local tiles."""
    outline = outline_edges(bits)
    stats["targetBoundaryEdges"] = len(outline)
    for lines in disjoint_turns(bits, deadline):
        yield straight_graph(lines), {"method": "disjoint_turns", "imageCreases": lines}
    seen = set()
    for boundary in boundary_assignments(bits, deadline, outline=outline):
        stats["boundaryAssignments"] += 1
        # Share time across different ways of placing the same image boundary.
        slice_end = min(deadline, time.monotonic() + TILE_SECONDS)
        solutions = []
        try:
            # Buffer this slice so layer checks do not use up its tile-solving time.
            solutions.extend(solve_tiles(boundary, slice_end, TILES_PER_BOUNDARY))
        except TimeoutError:
            stats["tileTimeSlicesExpired"] += 1
        for cpstr, corners in solutions:
            key = cpstr, tuple(corners)
            if key in seen:
                continue
            seen.add(key)
            try:
                fold = make_fold(cpstr, corners, size=SIZE)
            except ValueError:
                stats["invalidTileGraphs"] += 1
                continue
            yield (
                fold,
                {
                    "method": "boundary_tiles",
                    "boundary": list(boundary),
                    "cpstr": cpstr,
                    "corners": list(corners),
                },
            )
        if time.monotonic() >= deadline:
            raise TimeoutError
