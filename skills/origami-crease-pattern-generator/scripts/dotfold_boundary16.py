"""Enumerate boundary folds for a 16×16 sheet on the DotFold unit lattice.

A walk uses each target boundary edge once. For a shorter boundary the search
also tries one or two doubled chords, each straight or with a single bend.
These additions preserve the occupied cells modulo two. Layer visibility and
completion of the interior tile grid are separate tests.
"""

from collections import Counter, defaultdict
from time import monotonic

SIZE = 16
LENGTH = 4 * SIZE
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))
PAPER = tuple(
    [(i, 0) for i in range(SIZE)]
    + [(SIZE, i) for i in range(SIZE)]
    + [(SIZE - i, SIZE) for i in range(SIZE)]
    + [(0, SIZE - i) for i in range(SIZE)]
)


def _edge(a, b):
    return (a, b) if a < b else (b, a)


def outline_edges(bits):
    if not isinstance(bits, str) or len(bits) != SIZE**2 or set(bits) - {"0", "1"}:
        raise ValueError("expected 256 binary digits in row-major order")
    edges = set()
    for index, cell in enumerate(bits):
        if cell == "1":
            y, x = divmod(index, SIZE)
            square = [(x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)]
            edges.symmetric_difference_update(
                _edge(a, b) for a, b in zip(square, square[1:] + square[:1])
            )
    return edges


def _chords(outline, budget, deadline):
    """Find doubled seams that join two contour vertices without touching others."""
    vertices = {point for edge in outline for point in edge}
    chords = set()

    def follow(start, point, direction, edges, can_turn):
        if monotonic() >= deadline or len(edges) == budget:
            return
        dx, dy = DIRECTIONS[direction]
        end = (point[0] + dx, point[1] + dy)
        if not (0 <= end[0] <= SIZE and 0 <= end[1] <= SIZE):
            return
        edge = _edge(point, end)
        if edge in outline:
            return
        edges.append(edge)
        if end in vertices:
            if start < end:
                chords.add(tuple(sorted(edges)))
        else:
            follow(start, end, direction, edges, can_turn)
            if can_turn:
                for delta in (1, -1):
                    follow(start, end, (direction + delta) % 4, edges, False)
        edges.pop()

    for start in sorted(vertices):
        if monotonic() >= deadline:
            break
        for direction in range(4):
            follow(start, start, direction, [], True)
    return sorted(chords, key=lambda chord: (len(chord), chord))


def _augmentations(outline, deadline):
    budget = (LENGTH - len(outline)) // 2
    if budget == 0:
        yield ()
        return
    by_length = defaultdict(list)
    for chord in _chords(outline, budget, deadline):
        if len(chord) == budget:
            yield chord
        else:
            by_length[len(chord)].append(chord)
    for length in sorted(by_length):
        other = budget - length
        if length > other:
            break
        for first in by_length[length]:
            for second in by_length.get(other, ()):
                if monotonic() >= deadline:
                    return
                if length == other and second <= first:
                    continue
                if set(first).isdisjoint(second):
                    yield first + second


def _circuits(outline, extra, deadline):
    remaining = Counter(outline)
    for edge in extra:
        remaining[edge] += 2
    neighbors = defaultdict(list)
    for edge in sorted(remaining):
        a, b = edge
        neighbors[a].append((b, edge))
        neighbors[b].append((a, edge))

    # Reject disconnected graphs before branching at shared vertices.
    start = min(neighbors, key=lambda p: (p[1], p[0]))
    reached = {start}
    stack = [start]
    while stack:
        for other, _ in neighbors[stack.pop()]:
            if other not in reached:
                reached.add(other)
                stack.append(other)
    if len(reached) != len(neighbors):
        return

    path = [start]

    def walk():
        if monotonic() >= deadline:
            return
        vertex = path[-1]
        if len(path) == LENGTH + 1:
            if vertex == start and path[-2] != path[1]:
                yield tuple(path[:-1])
            return
        for other, edge in neighbors[vertex]:
            # None of the supported boundary codes can reverse by 180 degrees.
            if remaining[edge] == 0 or (len(path) > 1 and path[-2] == other):
                continue
            remaining[edge] -= 1
            path.append(other)
            yield from walk()
            path.pop()
            remaining[edge] += 1

    yield from walk()


def _turns(path):
    turns = []
    straight = {}
    for index, (x, y) in enumerate(path):
        px, py = path[index - 1]
        nx, ny = path[(index + 1) % LENGTH]
        turn = (x - px) * (ny - y) - (y - py) * (nx - x)
        if turn == 0:
            # Two straight strands on perpendicular axes cross transversely.
            horizontal = y == ny
            if straight.setdefault((x, y), horizontal) != horizontal:
                return ()
        turns.append(turn)
    return tuple(turns)


def _distance2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


# Same-side pairs automatically contract by the triangle inequality.
CHORD_LIMITS = tuple(
    (i, j, _distance2(a, PAPER[j]))
    for i, a in enumerate(PAPER)
    for j in range(i + 1, LENGTH)
    if i // SIZE != j // SIZE
)


def _turn_words(path):
    turns = _turns(path)
    if not turns or any(sum(t != 0 for t in turns[k::2]) % 2 for k in (0, 1)):
        return
    # Starting corners a whole side apart differ only by rotation of the sheet.
    for offset in range(SIZE):
        word = turns[offset:] + turns[:offset]
        if not all(word[::SIZE]):
            continue
        points = path[offset:] + path[:offset]
        if any(
            _distance2(points[i], points[j]) > limit for i, j, limit in CHORD_LIMITS
        ):
            continue
        # Reversing all turn signs only exchanges the initial paper side.
        yield tuple(t * word[0] for t in word)


def _folds(word, deadline):
    folds = []

    def assign(side):
        if monotonic() >= deadline:
            return
        i = len(folds)
        if i == LENGTH:
            if side == 1 and folds[-1] & 1 == folds[1] >> 2:
                yield tuple(folds)
            return
        turn = word[i] * side
        if i % SIZE == 0:
            options = (8,) if turn == 1 else ()
        elif turn == 0:
            options = (0,)
        elif turn == 1:
            options = (1, 3, 6)
        else:
            options = (4,)
        for code in options:
            if folds and folds[-1] == 3 and code in (4, 6):
                continue  # equivalent to the 1,6 or 1,4 boundary pair
            if i > 1 and i % SIZE == 1 and folds[-2] & 1 != code >> 2:
                continue  # the two neighbors must agree on their shared diagonal
            folds.append(code)
            yield from assign(-side if code in (1, 4) else side)
            folds.pop()

    yield from assign(1)


def boundary_assignments(bits, deadline, *, outline=None):
    """Yield 64 integer codes clockwise from top-left until a monotonic deadline."""
    if outline is None:
        outline = outline_edges(bits)
    if not outline or len(outline) > LENGTH or monotonic() >= deadline:
        return
    seen = set()
    for extra in _augmentations(outline, deadline):
        for path in _circuits(outline, extra, deadline):
            for word in _turn_words(path):
                if word not in seen:
                    seen.add(word)
                    yield from _folds(word, deadline)
            if monotonic() >= deadline:
                return
