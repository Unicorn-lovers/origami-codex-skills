"""Bounded local flat-foldability CSP for a 16-by-16 unit grid.

Indices traverse the 15-by-15 interior in screen row order. Direction zero is
north, then northeast, east, ... . All times are absolute monotonic deadlines.
"""

from collections import deque
from functools import cache, lru_cache
from itertools import combinations, product
from math import gcd
from time import monotonic

SIZE = 16
INNER = SIZE - 1
COUNT = INNER * INNER
DIRECTIONS = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))


def _kawasaki(bits):
    rays = [d for d, present in enumerate(bits) if present]
    # Alternating sectors sum to pi, i.e. four eighth-turns.
    return not rays or (
        len(rays) % 2 == 0 and sum(b - a for a, b in zip(rays[::2], rays[1::2])) == 4
    )


TILE_CATALOG = tuple(t for t in product((0, 1), repeat=8) if _kawasaki(t))
TILE_CODES = {bits: i for i, bits in enumerate(TILE_CATALOG)}
ALL = (1 << len(TILE_CATALOG)) - 1
# Element [direction][bit] is the set of compatible tile indices.
EDGE_TILES = tuple(
    tuple(
        sum(1 << i for i, tile in enumerate(TILE_CATALOG) if tile[d] == b)
        for b in (0, 1)
    )
    for d in range(8)
)


def _inside(x, y):
    return 0 < x < SIZE and 0 < y < SIZE


def _cell(x, y):
    return (y - 1) * INNER + x - 1


def _neighbors(x, y):
    return tuple(
        (d, _cell(x + dx, y + dy))
        for d, (dx, dy) in enumerate(DIRECTIONS)
        if _inside(x + dx, y + dy)
    )


NEIGHBORS = tuple(_neighbors(x, y) for y in range(1, SIZE) for x in range(1, SIZE))


def _perimeter(i):
    side, t = divmod(i, SIZE)
    return ((t, 0), (SIZE, t), (SIZE - t, SIZE), (0, SIZE - t))[side]


def _boundary_data(folds):
    if len(folds) != 4 * SIZE or any(
        type(f) is not int or (f != 8 if i % SIZE == 0 else not 0 <= f <= 7)
        for i, f in enumerate(folds)
    ):
        raise ValueError(
            "expected 64 perimeter codes, with 8 at corners and 0..7 on sides"
        )
    corners = []
    for i in range(0, 4 * SIZE, SIZE):
        cap = (folds[i + 1] >> 2) & 1
        if cap != folds[i - 1] & 1:
            return None
        corners.append(cap)
    domains = [ALL] * COUNT
    starts = set()
    for i, fold in enumerate(folds):
        side, along = divmod(i, SIZE)
        x, y = _perimeter(i)
        directions = (
            [(3 + 2 * side, 0)]
            if not along
            else [(3 + 2 * side + bit, (fold >> bit) & 1) for bit in range(3)]
        )
        for direction, present in directions:
            d = direction % 8
            dx, dy = DIRECTIONS[d]
            if _inside(x + dx, y + dy):
                domains[_cell(x + dx, y + dy)] &= EDGE_TILES[(d + 4) % 8][present]
                if present:
                    starts.add((x, y, d))
    return domains, starts, tuple(corners)


PERIMETER = tuple(_perimeter(i) for i in range(4 * SIZE))


def _folded_perimeter(folds):
    # A face's isometry sends original ray k to rotation + sign*k (mod 8).
    # Walking clockwise crosses the inward rays in backward-to-forward order.
    x = y = rotation = 0
    sign = 1
    result = []
    for i, code in enumerate(folds):
        result.append((x, y))
        side = i // SIZE
        for bit in (2, 1, 0):
            if code & (1 << bit):
                axis = 3 + 2 * side + bit
                rotation = (rotation + sign * 2 * axis) % 8
                sign = -sign
        dx, dy = DIRECTIONS[(rotation + sign * (2 + 2 * side)) % 8]
        x += dx
        y += dy
    if (x, y, rotation, sign) == (0, 0, 0, 1):
        return tuple(result)
    return None


def _folded_rays(tile):
    # Fix one face as a reference; only relative angles are used.
    directions = [0]
    sign = 1
    for ray in range(1, 8):
        directions.append((directions[-1] + sign) % 8)
        if tile[ray]:
            sign = -sign
    return directions


FOLDED_RAYS = tuple(_folded_rays(t) for t in TILE_CATALOG)


def _angle(d, e):
    gap = abs(d - e)
    return min(gap, 8 - gap)


@cache
def _angle_tiles(d, e, angle):
    return sum(
        1 << i
        for i, rays in enumerate(FOLDED_RAYS)
        if _angle(rays[d], rays[e]) == angle
    )


def _chords():
    for i, j in combinations(range(len(PERIMETER)), 2):
        x, y = PERIMETER[i]
        u, v = PERIMETER[j]
        dx, dy = u - x, v - y
        steps = gcd(abs(dx), abs(dy))
        step_x, step_y = dx // steps, dy // steps
        interior = tuple(
            (x + k * step_x, y + k * step_y)
            for k in range(1, steps)
            if _inside(x + k * step_x, y + k * step_y)
        )
        yield i, j, dx * dx + dy * dy, steps, interior


CHORDS = tuple(_chords())


@lru_cache(maxsize=32)
def _metric_domains(rim):
    # A flat folding cannot increase the distance between points. Equality
    # fixes every point on the intervening paper segment by interpolation.
    fixed = dict(zip(PERIMETER, rim))
    for i, j, length2, steps, points in CHORDS:
        x, y = rim[i]
        dx, dy = rim[j][0] - x, rim[j][1] - y
        after = dx * dx + dy * dy
        if after > length2:
            return None
        if after == length2 and points:
            if dx % steps or dy % steps:
                return None  # Unit-grid lattice points map to the integer grid.
            for k, point in enumerate(points, 1):
                xy = (x + k * (dx // steps), y + k * (dy // steps))
                if fixed.setdefault(point, xy) != xy:
                    return None

    domains = [ALL] * COUNT
    for (x, y), (u, v) in fixed.items():
        if not _inside(x, y):
            continue
        rays = []
        for d, (dx, dy) in enumerate(DIRECTIONS):
            neighbor = fixed.get((x + dx, y + dy))
            if neighbor is None:
                continue
            delta = (neighbor[0] - u, neighbor[1] - v)
            length2 = delta[0] ** 2 + delta[1] ** 2
            if length2 > dx * dx + dy * dy:
                return None
            if length2 == dx * dx + dy * dy:
                rays.append((d, DIRECTIONS.index(delta)))
        cell = _cell(x, y)
        for (d, a), (e, b) in combinations(rays, 2):
            domains[cell] &= _angle_tiles(d, e, _angle(a, b))
        if not domains[cell]:
            return None
    return tuple(domains)


def _straight_lines(starts):
    """Try whole lines that are directly supported by both perimeter endpoints."""
    preferred = [[0] * 8 for _ in range(COUNT)]
    paired = 0
    for x, y, d in starts:
        dx, dy = DIRECTIONS[d]
        u, v = x + dx, y + dy
        line = []
        while _inside(u, v):
            line.append(_cell(u, v))
            u += dx
            v += dy
        back = (d + 4) % 8
        if (u, v, back) in starts:
            paired += 1
            for cell in line:
                preferred[cell][d] = preferred[cell][back] = 1
    return [tuple(row) for row in preferred], paired == len(starts)


def _propagate(domains, changed):
    """A forced edge bit cuts down the adjacent domain until a fixed point."""
    queue = deque(changed)
    while queue:
        cell = queue.popleft()
        domain = domains[cell]
        if not domain:
            return False
        for d, neighbor in NEIGHBORS[cell]:
            off, on = EDGE_TILES[d]
            if not domain & off:
                compatible = EDGE_TILES[(d + 4) % 8][1]
            elif not domain & on:
                compatible = EDGE_TILES[(d + 4) % 8][0]
            else:
                continue
            reduced = domains[neighbor] & compatible
            if reduced != domains[neighbor]:
                if not reduced:
                    return False
                domains[neighbor] = reduced
                queue.append(neighbor)
    return True


def _check_time(deadline):
    if monotonic() >= deadline:
        raise TimeoutError("16-by-16 tile search reached its deadline")


def solve_tiles(boundary_folds, deadline, limit):
    """Yield (CPSTR, corners) satisfying all shared rays and boundary values.

    CPSTR uses 225 two-digit Kawasaki tile IDs, corners use TL, TR, BR, BL.
    Exhaustion and the result limit return normally. Deadline expiry raises
    TimeoutError. Candidates still require global layer and target checks.
    """
    data = _boundary_data(boundary_folds)
    if data is None or limit <= 0:
        return
    _check_time(deadline)
    domains, starts, corners = data
    rim = _folded_perimeter(boundary_folds)
    if rim is None:
        return
    allowed = _metric_domains(rim)
    _check_time(deadline)
    if allowed is None:
        return
    domains = [a & b for a, b in zip(domains, allowed)]
    consistent = _propagate(domains, range(COUNT))
    _check_time(deadline)
    if not consistent:
        return

    preferred, paired = _straight_lines(starts)
    first = None
    yielded = 0
    if paired and all(
        p in TILE_CODES and domain & (1 << TILE_CODES[p])
        for p, domain in zip(preferred, domains)
    ):
        # These lines agree at every shared edge by construction.
        first = "".join(f"{TILE_CODES[p]:02d}" for p in preferred)
        _check_time(deadline)
        yield first, corners
        yielded = 1
        if yielded >= limit:
            return

    priority = {}
    for p in set(preferred):
        priority[p] = sorted(
            range(len(TILE_CATALOG)),
            key=lambda i: (
                sum(a != b for a, b in zip(p, TILE_CATALOG[i])),
                sum(TILE_CATALOG[i]),
                i,
            ),
        )

    def visit(current):
        _check_time(deadline)
        best_cell = None
        smallest = len(TILE_CATALOG) + 1
        for cell, domain in enumerate(current):
            count = domain.bit_count()
            if 1 < count < smallest:
                smallest = count
                best_cell = cell
                if count == 2:
                    break
        if best_cell is None:
            cp = "".join(f"{domain.bit_length() - 1:02d}" for domain in current)
            if cp != first:
                yield cp, corners
            return
        for tile in priority[preferred[best_cell]]:
            _check_time(deadline)
            if current[best_cell] & (1 << tile):
                trial = current.copy()
                trial[best_cell] = 1 << tile
                if _propagate(trial, [best_cell]):
                    yield from visit(trial)

    for candidate in visit(domains):
        yield candidate
        yielded += 1
        if yielded >= limit:
            return
