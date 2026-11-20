"""Draw paper landmarks and their rigid flat-fold projections from exported faces."""

from collections import Counter, defaultdict, deque
from html import escape
from math import dist

from audit_folded_state import point_segment_distance


def edges(face):
    return zip(face, face[1:] + face[:1])


def as_complex(points):
    return [complex(x, y) for x, y in points]


def face_transforms(fold):
    """Fit an isometry per face by reflecting across each active shared crease."""
    vertices = as_complex(fold["vertices_coords"])
    faces = fold["faces_vertices"]
    assignments = {
        tuple(sorted(edge)): a
        for edge, a in zip(fold["edges_vertices"], fold["edges_assignment"])
    }
    incidence = defaultdict(list)
    for fid, face in enumerate(faces):
        for edge in edges(face):
            incidence[tuple(sorted(edge))].append(fid)
    frames = {0: (1 + 0j, 0j, False)}
    queue = deque([0])
    while queue:
        fid = queue.popleft()
        rotation, offset, reversed_side = frames[fid]
        for i, j in edges(faces[fid]):
            key = tuple(sorted((i, j)))
            for other in incidence[key]:
                if other in frames:
                    continue
                if assignments[key] == "F":
                    frames[other] = frames[fid]
                elif assignments[key] in ("M", "V"):
                    a, b = vertices[i], vertices[j]
                    axis = (b - a) / (b - a).conjugate()
                    origin = a - axis * a.conjugate()
                    if reversed_side:
                        axis, origin = axis.conjugate(), origin.conjugate()
                    frames[other] = (
                        rotation * axis,
                        offset + rotation * origin,
                        not reversed_side,
                    )
                else:
                    raise ValueError("unexpected interior edge assignment")
                queue.append(other)
    if len(frames) != len(faces):
        raise ValueError("exported face graph is disconnected")
    return frames


def transform(point, frame):
    rotation, offset, reversed_side = frame
    return rotation * (point.conjugate() if reversed_side else point) + offset


def folded_vertices(fold):
    vertices = as_complex(fold["vertices_coords"])
    frames = face_transforms(fold)
    result = [None] * len(vertices)
    for fid, face in enumerate(fold["faces_vertices"]):
        for i in face:
            z = transform(vertices[i], frames[fid])
            point = (z.real, z.imag)
            if result[i] is not None and dist(result[i], point) > 1e-5:
                raise ValueError("inconsistent folded coordinates on a shared vertex")
            result[i] = point
    if None in result:
        raise ValueError("export contains vertices outside its faces")
    return result


def inside(point, poly):
    """Boundary-inclusive crossing test for an exported paper face."""
    x, y = point
    odd = False
    for (ax, ay), (bx, by) in edges(poly):
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if (
            abs(cross) < 1e-7
            and min(ax, bx) - 1e-8 <= x <= max(ax, bx) + 1e-8
            and min(ay, by) - 1e-8 <= y <= max(ay, by) + 1e-8
        ):
            return True
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            odd = not odd
    return odd


def folded_view(fold, landmarks):
    paper = fold["vertices_coords"]
    faces = fold["faces_vertices"]
    vertices = folded_vertices(fold)
    frames = face_transforms(fold)
    mapped = {}
    for name, xy in landmarks.items():
        point = tuple(1000 * v for v in xy)
        for fid, face in enumerate(faces):
            if inside(point, [paper[i] for i in face]):
                z = transform(complex(*point), frames[fid])
                mapped[name] = [z.real, z.imag]
                break
        else:
            raise ValueError(
                f"{name}: material landmark lies outside the exported faces"
            )
    return [(0, vertices[i], vertices[j]) for i, j in fold["edges_vertices"]], mapped


def layer_polygons(model):
    bounds = model["foldedBounds"]

    def coord(p):
        return complex(
            bounds["minX"] + p["x"] * (bounds["maxX"] - bounds["minX"]),
            bounds["minY"] + p["y"] * (bounds["maxY"] - bounds["minY"]),
        )

    return [
        (cell, list(map(coord, cell["polygonNormalized"])))
        for cell in model["visibleRegions"]
    ]


def visible_view(fold, model, landmarks):
    """Register the projection to Oriedita's layer cells, allowing either handedness."""
    wire, projected = folded_view(fold, landmarks)
    vertices = folded_vertices(fold)
    faces = fold["faces_vertices"]
    paper = fold["vertices_coords"]
    rings, lookup = {}, {}
    for face in model.get("faces", []):
        center = face["flatCentroid"]
        matches = [
            i
            for i, ids in enumerate(faces)
            if inside((center["x"], center["y"]), [paper[j] for j in ids])
        ]
        if len(matches) != 1:
            return wire, projected, "Folded projection / all layers"
        lookup[face["faceId"]] = matches[0]
    if not lookup or not model.get("visibleRegions") or not model.get("foldedBounds"):
        return wire, projected, "Folded projection / all layers"
    regions = []
    for cell, poly in layer_polygons(model):
        regions.append((cell["topFace"], poly))
        for fid in cell["stackTopToBottom"]:
            if fid not in lookup:
                return wire, projected, "Folded projection / all layers"
            rings.setdefault(lookup[fid], set()).update(poly)
    if not rings or len(rings) != len(faces):
        return wire, projected, "Folded projection / all layers"
    # A complete paper face is the union of cells whose stacks contain it.
    # Its farthest vertex pair survives subdivision and determines a rigid frame.
    anchor = min(rings, key=lambda fid: len(rings[fid]))
    polys = [[complex(*vertices[i]) for i in face] for face in faces]
    a, b = max(
        ((a, b) for a in polys[anchor] for b in polys[anchor]),
        key=lambda ab: abs(ab[0] - ab[1]),
    )
    solutions = []
    tol = 1e-5
    for u in rings[anchor]:
        for v in rings[anchor]:
            if abs(abs(v - u) - abs(b - a)) > tol:
                continue
            for flip in (False, True):
                delta = (b - a).conjugate() if flip else b - a
                rot = (v - u) / delta
                frame = rot, u - rot * (a.conjugate() if flip else a), flip
                if all(
                    all(
                        min(abs(transform(p, frame) - t) for t in ring) < tol
                        for p in polys[fid]
                    )
                    for fid, ring in rings.items()
                ):
                    solutions.append(
                        {
                            name: transform(complex(*p), frame)
                            for name, p in projected.items()
                        }
                    )
    if not solutions or any(
        abs(z - sol[name]) > tol
        for name, z in solutions[0].items()
        for sol in solutions[1:]
    ):
        return wire, projected, "Folded projection / all layers"

    def xy(z):
        return [z.real, z.imag]

    # Keep the layer boundaries from the selected solver solution. Labels mark
    # material positions, including coincident or covered points.
    lines = [(0, xy(p), xy(q)) for _, ring in regions for p, q in edges(ring)]
    return lines, {k: xy(z) for k, z in solutions[0].items()}, "Oriedita layer cells"


def outline_checks(lines, landmarks):
    """Classify points against singly incident edges of Oriedita's layer cells."""

    def key(p):
        return tuple(round(x, 6) for x in p)

    counts = Counter(tuple(sorted((key(a), key(b)))) for _, a, b in lines)
    boundary = [edge for edge, count in counts.items() if count == 1]
    if not boundary:
        return {}
    return {
        name: min(point_segment_distance(p, a, b) for a, b in boundary) <= 1e-5
        for name, p in landmarks.items()
    }


def svg_view(segments, landmarks, title, caption, reservations=None, model=None):
    """A numbered key keeps coincident material landmarks readable."""
    points = [p for _, a, b in segments for p in (a, b)]
    xs, ys = zip(*points)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    scale = 320 / max(max(xs) - min(xs), max(ys) - min(ys))

    def screen(p):
        return (207 + (p[0] - cx) * scale, 217 + (p[1] - cy) * scale)

    height = max(441, 105 + len(landmarks) * 27)
    width = max(660, 485 + max((len(n) * 15 for n in landmarks), default=0))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#fafaf7"/>',
        '<g font-family="sans-serif" fill="#182b30">',
        f'<text x="22" y="30" font-size="20" font-weight="bold">{escape(title)}</text>',
    ]
    colors = {0: "#697b80", 1: "#20353a", 2: "#b44149", 3: "#3469a3"}
    if model:
        for cell, poly in layer_polygons(model):
            coords = " ".join(
                "{:.3f},{:.3f}".format(*screen((p.real, p.imag))) for p in poly
            )
            color = "#c0e1d5" if cell.get("frontViewSide") == "front" else "#e3e8e9"
            parts.append(f'<polygon points="{coords}" fill="{color}"/>')
    for polygon in (reservations or {}).values():
        coords = " ".join("{:.3f},{:.3f}".format(*screen(p)) for p in polygon)
        parts.append(f'<polygon points="{coords}" fill="#7cae99" fill-opacity=".14"/>')
    for assignment, a, b in segments:
        x, y = screen(a)
        u, v = screen(b)
        parts.append(
            f'<path d="M{x:.3f} {y:.3f} L{u:.3f} {v:.3f}" stroke="{colors[assignment]}" fill="none"/>'
        )
    groups = []
    for i, (name, point) in enumerate(landmarks.items(), 1):
        px = screen(point)
        group = next((g for g in groups if dist(g[0], px) < 1), None)
        if group is None:
            group = (px, [])
            groups.append(group)
        group[1].append(str(i))
        parts.append(
            f'<text x="410" y="{80 + 27 * i}" font-size="16">{i}. {escape(name)}</text>'
        )
    for (x, y), indices in groups:
        label = "/".join(indices)
        parts.extend(
            [
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="#006857"/>',
                f'<rect x="{x + 3:.2f}" y="{y - 19:.2f}" width="{len(label) * 9 + 4}" height="16" rx="3" fill="#005445"/>',
                f'<text x="{x + 5:.2f}" y="{y - 7:.2f}" font-size="12" fill="white">{label}</text>',
            ]
        )
    parts.extend(
        [
            f'<text x="22" y="{height - 18}" font-size="12">{escape(caption)}</text>',
            "</g></svg>",
        ]
    )
    return "\n".join(parts)
