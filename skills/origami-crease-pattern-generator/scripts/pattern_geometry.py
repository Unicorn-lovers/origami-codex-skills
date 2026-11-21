"""Prepare Oriedita's three-code validator input without modifying an original."""
import json
import math


def finite_point(point):
    if (not isinstance(point, list) or len(point) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)):
        raise ValueError("expected finite 2D coordinates in the crease-pattern frame")
    return point


def prepare_geometry(data, file_format):
    """Return (CP bytes, count of explicitly flat edges omitted)."""
    if file_format == "cp":
        return prepare_cp(data)
    if file_format == "fold":
        return prepare_fold(json.loads(data))
    raise ValueError("this source requires reconstruction or format-specific import")


def require_paper(kinds):
    if "1" not in kinds or not ({"2", "3"} & kinds):
        raise ValueError("the source needs a paper boundary and assigned mountain or valley folds")


def prepare_cp(data):
    kept, kinds, flat = [], set(), 0
    for n, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if len(fields) != 5 or fields[0] not in {"1", "2", "3", "4"}:
            raise ValueError(f"unsupported CP assignment or row at line {n}")
        x1, y1, x2, y2 = map(float, fields[1:])
        if not all(map(math.isfinite, (x1, y1, x2, y2))) or (x1, y1) == (x2, y2):
            raise ValueError(f"invalid segment at line {n}")
        kinds.add(fields[0])
        if fields[0] == "4":
            flat += 1
        else:
            kept.append(line)
    require_paper(kinds)
    if not flat:
        return data.removeprefix(b"\xef\xbb\xbf"), 0
    return ("\n".join(kept) + "\n").encode(), flat


def prepare_fold(frame):
    if not isinstance(frame, dict):
        raise ValueError("expected a FOLD document")
    classes = frame.get("frame_classes", [])
    if "foldedForm" in classes or "foldedForm" in frame.get("file_classes", []):
        raise ValueError("select an unfolded crease-pattern frame first")
    points = [finite_point(p) for p in frame.get("vertices_coords", [])]
    edges, assignments = frame.get("edges_vertices", []), frame.get("edges_assignment", [])
    if not points or not edges or len(edges) != len(assignments):
        raise ValueError("missing root-frame vertices, edges or assignments")
    xs, ys = zip(*points)
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if not span or min(xs) == max(xs) or min(ys) == max(ys):
        raise ValueError("degenerate paper dimensions")
    # Uniform scaling, no mirror or change of mountain/valley side.
    x0, y0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    points = [((x-x0)*400/span, (y-y0)*400/span) for x, y in points]
    codes = {"B": "1", "M": "2", "V": "3"}
    lines, kinds, flat = [], set(), 0
    for edge, assignment in zip(edges, assignments):
        if (not isinstance(edge, list) or len(edge) != 2
                or any(type(i) is not int or not 0 <= i < len(points) for i in edge)):
            raise ValueError("invalid vertex reference")
        a, b = (points[i] for i in edge)
        if a == b:
            raise ValueError("zero-length edge")
        if assignment == "F":
            flat += 1
            continue
        if assignment not in codes:
            raise ValueError(f"resolve assignment {assignment!r} before validation")
        code = codes[assignment]
        kinds.add(code)
        lines.append(" ".join([code, *(format(v, ".16g") for v in (*a, *b))]))
    require_paper(kinds)
    return ("\n".join(lines) + "\n").encode(), flat
