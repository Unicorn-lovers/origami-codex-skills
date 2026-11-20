"""Construct candidate CP edits in normalized square-paper coordinates."""

import itertools
import math
from pathlib import Path

EPS = 1e-9
SQUARE = [(0, 0), (1, 0), (1, 1), (0, 1)]
BOUNDARY = [(1, SQUARE[i - 1], p) for i, p in enumerate(SQUARE)]
OPERATION_FIELDS = {
    "shorten_tip": {"flap", "fraction", "assignment"},
    "redirect_tip": {"flap", "target", "assignment"},
    "split_tip": {"flap", "fraction", "assignment"},
    "release_corner": {"flap"},
    "border_graft": {"side", "width", "assignment"},
    "hybrid_quadrant": {"quadrant", "donor"},
}


def _point(value):
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(
            type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1
            for x in value
        )
    ):
        raise ValueError("expected two finite paper coordinates in [0, 1]")
    return tuple(value)


def _fraction(value, limit=1):
    if type(value) not in (int, float) or not 0 < value < limit:
        raise ValueError(f"expected a fraction greater than zero and less than {limit}")
    return value


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in (0, 1))


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _edges(poly):
    return [(poly[i - 1], p) for i, p in enumerate(poly)]


def _clip(a, b, polygon):
    """Return the portion of segment a..b inside a convex polygon as parameters."""
    enter, leave = 0.0, 1.0
    winding = 1 if sum(_cross(c, d) for c, d in _edges(polygon)) > 0 else -1
    direction = _sub(b, a)
    for c, d in _edges(polygon):
        edge = _sub(d, c)
        intercept = winding * _cross(edge, _sub(a, c))
        slope = winding * _cross(edge, direction)
        if abs(slope) < EPS:
            if intercept < -EPS:
                return None
        elif slope > 0:
            enter = max(enter, -intercept / slope)
        else:
            leave = min(leave, -intercept / slope)
    return (enter, leave) if leave - enter > EPS else None


def _intersection(a, b, c, d):
    ab, cd = _sub(b, a), _sub(d, c)
    det = _cross(ab, cd)
    if abs(det) < EPS * math.hypot(*ab) * math.hypot(*cd):
        return None
    t = _cross(_sub(c, a), cd) / det
    u = _cross(_sub(c, a), ab) / det
    if -EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS:
        return max(0.0, min(1.0, t)), max(0.0, min(1.0, u))
    return None


def _canonical(segments):
    """Split at actual intersections and eliminate coincident fragments."""
    cuts = [{0.0, 1.0} for _ in segments]
    for i, (_, a, b) in enumerate(segments):
        ab = _sub(b, a)
        if math.dist(a, b) < EPS:
            raise ValueError("degenerate segment in candidate")
        for j in range(i):
            _, c, d = segments[j]
            hit = _intersection(a, b, c, d)
            if hit is not None:
                cuts[i].add(hit[0])
                cuts[j].add(hit[1])
            elif abs(_cross(ab, _sub(c, a))) < EPS * math.hypot(*ab) and abs(
                _cross(ab, _sub(d, a))
            ) < EPS * math.hypot(*ab):
                for index, origin, vec, ends in (
                    (i, a, ab, (c, d)),
                    (j, c, _sub(d, c), (a, b)),
                ):
                    for endpoint in ends:
                        t = _dot(_sub(endpoint, origin), vec) / _dot(vec, vec)
                        if EPS < t < 1 - EPS:
                            cuts[index].add(t)
    unique = {}
    for (kind, a, b), parameters in zip(segments, cuts):
        points = [
            tuple(round(x, 11) for x in _mix(a, b, t)) for t in sorted(parameters)
        ]
        for c, d in itertools.pairwise(points):
            if math.dist(c, d) < EPS:
                continue
            key = tuple(sorted((c, d)))
            if key in unique and unique[key] != kind:
                raise ValueError("conflicting assignments on coincident segments")
            unique[key] = kind
    return [(kind, a, b) for (a, b), kind in unique.items()]


def _on_boundary(p):
    return any(min(abs(x), abs(1 - x)) < EPS for x in p)


def _hinge(flap, target):
    tip = _point(flap["tip"])
    displacement = _sub(target, tip)
    length = math.hypot(*displacement)
    if length < EPS:
        raise ValueError("tip target must differ from its source")
    center = _mix(tip, target, 0.5)
    dx, dy = displacement
    near = center[0] - 2 * dy / length, center[1] + 2 * dx / length
    far = center[0] + 2 * dy / length, center[1] - 2 * dx / length
    interval = _clip(near, far, flap["polygon"])
    if interval is None:
        raise ValueError("requested hinge misses the flap region")
    a, b = (_mix(near, far, t) for t in interval)
    if not (_on_boundary(a) and _on_boundary(b)):
        raise ValueError(
            "the selected region needs a folded-state hinge across additional faces"
        )
    return a, b


def _assignment(op):
    code = op.get("assignment", "V")
    if code not in ("V", "M"):
        raise ValueError("assignment must be V or M")
    return 3 if code == "V" else 2


def _add_hinge(segments, a, b, assignment):
    # A straight hinge traced over a perpendicular pre-existing fold changes sign.
    crossings = set()
    for kind, c, d in segments:
        if kind == 1:
            continue
        hit = _intersection(a, b, c, d)
        if hit and EPS < hit[0] < 1 - EPS:
            if not EPS < hit[1] < 1 - EPS:
                raise ValueError(
                    "hinge crosses an existing vertex; specify a folded-face construction"
                )
            v, w = _sub(b, a), _sub(d, c)
            if abs(_dot(v, w)) > EPS * math.hypot(*v) * math.hypot(*w):
                raise ValueError(
                    "an oblique crossing needs a reflected hinge in the adjacent face"
                )
            crossings.add(hit[0])
    ts = [0.0, *sorted(crossings), 1.0]
    return segments + [
        (
            assignment if i % 2 == 0 else 5 - assignment,
            _mix(a, b, t),
            _mix(a, b, ts[i + 1]),
        )
        for i, t in enumerate(ts[:-1])
    ]


def _split_lines(flap, fraction):
    """Asymmetric two-fold corner pleat. Its original tip and shoulder form peaks."""
    x, y = _point(flap["tip"])
    if (x, y) not in SQUARE:
        raise ValueError("split_tip requires a square-sheet corner")
    poly = flap["polygon"]
    x_lengths = [abs(p[0] - x) for p in poly if abs(p[1] - y) < EPS]
    y_lengths = [abs(p[1] - y) for p in poly if abs(p[0] - x) < EPS]
    if not x_lengths or not y_lengths:
        raise ValueError("split_tip requires free edges on both sides of the corner")
    scale = min(max(x_lengths), max(y_lengths)) * _fraction(fraction)
    if scale < 10 * EPS:
        raise ValueError("split cap is too small")
    dx, dy = scale * (1 - 2 * x), scale * (1 - 2 * y)
    return [((x + dx, y), (x, y + 0.75 * dy)), ((x + 0.5 * dx, y), (x, y + 0.5 * dy))]


def split_tip_points(flap, fraction):
    """Source-paper coordinates of the two proposed peaks, shoulder then original tip."""
    return [_split_lines(flap, fraction)[0][1], tuple(flap["tip"])]


def _split(segments, flap, op):
    first, second = _split_lines(flap, op.get("fraction", 0.35))
    cap = [flap["tip"], *first]
    if any(kind != 1 and _clip(a, b, cap) for kind, a, b in segments):
        raise ValueError("split_tip requires an uncreased free corner cap")
    kind = _assignment(op)
    return segments + [(kind, *first), (5 - kind, *second)]


def _release(segments, flap):
    poly = flap["polygon"]
    hinges = [
        (a, b)
        for a, b in _edges(poly)
        if not any(
            abs(a[axis] - b[axis]) < EPS and min(abs(a[axis]), abs(1 - a[axis])) < EPS
            for axis in (0, 1)
        )
    ]
    if len(hinges) != 1 or tuple(flap["tip"]) not in SQUARE:
        raise ValueError("release_corner requires a corner cap with a single hinge")
    a, b = hinges[0]
    direction = _sub(b, a)
    remaining, removed = [], 0.0
    for kind, c, d in _canonical(segments):
        if (
            kind != 1
            and _clip(c, d, poly)
            and max(abs(_cross(direction, _sub(p, a))) for p in (c, d)) < EPS
            and all(
                -EPS <= _dot(_sub(p, a), direction) <= _dot(direction, direction) + EPS
                for p in (c, d)
            )
        ):
            removed += math.dist(c, d)
        else:
            if kind != 1 and _clip(c, d, poly):
                raise ValueError("corner has active creases beyond its hinge")
            remaining.append((kind, c, d))
    if abs(removed - math.dist(a, b)) > EPS:
        raise ValueError("no complete active hinge on this corner")
    return remaining


def _graft_frame(op):
    width = _fraction(op.get("width"), 0.5)
    offsets = {
        "left": (width, width / 2),
        "right": (0, width / 2),
        "top": (width / 2, width),
        "bottom": (width / 2, 0),
    }
    side = op.get("side")
    if side not in offsets:
        raise ValueError("border_graft side must be left, right, top or bottom")
    return 1 - width, offsets[side]


def adapted_point(point, operations):
    x, y = point
    for op in operations:
        if op["op"] == "border_graft":
            scale, (u, v) = _graft_frame(op)
            x, y = x * scale + u, y * scale + v
    return (x, y)


def _border_graft(segments, op):
    scale, offset = _graft_frame(op)
    result = [
        (k, adapted_point(a, [op]), adapted_point(b, [op]))
        for k, a, b in segments
        if k != 1
    ]
    low = list(offset)
    high = [value + scale for value in offset]
    for axis in (0, 1):
        before = result.copy()
        for limit in (low[axis], high[axis]):
            if not EPS < limit < 1 - EPS:
                continue

            def mirror(p, limit=limit, axis=axis):
                return tuple(2 * limit - p[i] if i == axis else p[i] for i in (0, 1))

            for kind, a, b in before:
                c, d = mirror(a), mirror(b)
                interval = _clip(c, d, SQUARE)
                if interval is not None:
                    result.append((5 - kind, *(_mix(c, d, t) for t in interval)))
            start, end = low.copy(), high.copy()
            start[axis] = end[axis] = limit
            result.append((_assignment(op), tuple(start), tuple(end)))
        low[axis], high[axis] = 0.0, 1.0
    return result + BOUNDARY


def _hybrid(segments, base_id, op):
    donor_id = op.get("donor")
    folder = Path(__file__).resolve().parent.parent / "assets/bases"
    if donor_id not in {p.stem for p in folder.glob("*.cp")} or donor_id == base_id:
        raise ValueError("donor must name a different bundled base")
    quadrant = op.get("quadrant")
    if quadrant not in ("nw", "ne", "sw", "se"):
        raise ValueError("quadrant must be nw, ne, sw or se")
    left = 0.5 if quadrant[1] == "e" else 0.0
    top = 0.5 if quadrant[0] == "s" else 0.0
    box = [(left + x * 0.5, top + y * 0.5) for x, y in SQUARE]
    donor = []
    for row in (folder / (donor_id + ".cp")).read_text().splitlines():
        k, *coords = row.split()
        x, y, u, v = (float(n) / 1000 for n in coords)
        donor.append((int(k), (x, y), (u, v)))
    result = list(BOUNDARY)
    for source, incoming in ((segments, False), (donor, True)):
        for kind, a, b in source:
            if kind == 1:
                continue
            interval = _clip(a, b, box)
            # Keep original assignments on quadrant seams.
            on_seam = any(max(abs(a[i] - 0.5), abs(b[i] - 0.5)) < EPS for i in (0, 1))
            if interval is None or on_seam:
                if not incoming:
                    result.append((kind, a, b))
                continue
            t, u = interval
            ranges = [(t, u)] if incoming else [(0.0, t), (u, 1.0)]
            result.extend(
                (kind, _mix(a, b, i), _mix(a, b, j)) for i, j in ranges if j - i > EPS
            )
    result = _canonical(result)
    degree = {}
    for _, a, b in result:
        for p in (a, b):
            degree[p] = degree.get(p, 0) + 1
    if any(n == 1 and not _on_boundary(p) for p, n in degree.items()):
        raise ValueError("donor leaves a dangling crease at the replacement seam")
    return result


def apply_operations(segments, operations, base_map, base_id):
    """Return a new candidate. Local operations use original paper anchors before grafting."""
    if not isinstance(operations, list) or not operations:
        raise ValueError("operations must be a non-empty list")
    current = _canonical(list(segments))
    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            raise TypeError("expected an operation object")
        name = op.get("op")
        if not isinstance(name, str) or name not in OPERATION_FIELDS:
            raise ValueError(f"unsupported operation {name}")
        unknown = set(op) - OPERATION_FIELDS[name] - {"op"}
        if unknown:
            raise ValueError(
                f"unknown field(s) for {name}: {', '.join(sorted(unknown))}"
            )
        if name in ("shorten_tip", "redirect_tip", "split_tip", "release_corner"):
            flap = base_map["flaps"].get(op.get("flap"))
            if flap is None:
                raise ValueError(f"unknown flap {op.get('flap')}")
            if name == "release_corner":
                result = _release(current, flap)
            elif name == "split_tip":
                result = _split(current, flap, op)
            else:
                target = (
                    _point(op.get("target"))
                    if name == "redirect_tip"
                    else _mix(
                        flap["tip"], flap["root"], _fraction(op.get("fraction", 0.5))
                    )
                )
                a, b = _hinge(flap, target)
                result = _add_hinge(current, a, b, _assignment(op))
        elif name == "border_graft":
            if i != len(operations) - 1:
                raise ValueError(
                    "border_graft must follow edits in original paper coordinates"
                )
            result = _border_graft(current, op)
        elif name == "hybrid_quadrant":
            if any(t.get("op") != "border_graft" for t in operations[i + 1 :]):
                raise ValueError("only border_graft can follow a quadrant replacement")
            result = _hybrid(current, base_id, op)
        else:
            raise ValueError(f"unsupported operation {name}")
        result = _canonical(result)
        # Compare the normalized graphs independent of edge ordering.
        if set(result) == set(current):
            raise ValueError(f"{name} leaves the crease pattern unchanged")
        current = result
    return current
