# Oriedita `.cp` format and JSON construction input

## `.cp` rows

Use one segment per line:

```text
<code> <x1> <y1> <x2> <y2>
```

The codes used by this skill are:

- `1`: paper boundary / edge
- `2`: mountain fold
- `3`: valley fold

Coordinates are finite decimal numbers in Oriedita object space. A convenient convention is a 1000×1000 square from `(0, 0)` to `(1000, 1000)`. Keep all crease endpoints inside or on the paper boundary.

The file format does not carry a model name, construction rationale, units, or folding sequence. Store those in a separate note when they matter.

## JSON accepted by `build_cp.py`

```json
{
  "paper": {
    "width": 1000,
    "height": 1000,
    "origin": [0, 0]
  },
  "creases": [
    {"assignment": "M", "a": [0, 0], "b": [1000, 1000]},
    {"assignment": "V", "a": [1000, 0], "b": [0, 1000]}
  ]
}
```

`paper` adds the four boundary edges automatically. `assignment` accepts `M`, `MOUNTAIN`, or `2` for mountain and `V`, `VALLEY`, or `3` for valley. Explicit `EDGE`/`1` segments are also accepted, but normally use the `paper` object instead.

The builder rejects malformed coordinates, non-positive paper dimensions, zero-length segments, exact duplicate segments, unknown assignments, and endpoints outside the declared rectangular paper. It does not prove foldability; run the Oriedita validator afterward.

## Geometry practices

- Compute symmetric points from a shared formula rather than typing approximate mirror coordinates independently.
- Use one consistent scale and coordinate system.
- Make intended intersections coincide numerically. Avoid nearly overlapping points and tiny accidental segments.
- Keep mountain/valley assignments as design data. Swapping assignments can change layer ordering even when the undirected line arrangement is unchanged.
- If importing geometry from an image, treat traced coordinates as a draft until reconstructed and validated.
