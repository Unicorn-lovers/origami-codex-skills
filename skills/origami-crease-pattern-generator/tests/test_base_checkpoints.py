"""Exercise the actual bundled CPs against the landmarks in the folding guides."""

import json
import unittest
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def cross(a, b):
    return (a.conjugate() * b).imag


def project_landmark(point, creases):
    # Follow a segment from one fixed reference face to the landmark.
    # Across each active crease the neighboring face is reflected. Compose
    # these reflections in source coordinates, innermost (last crossed) first.
    start = complex(0.123171679, 0.421430245)
    ray = point - start
    crossed = []
    for a, b in creases:
        edge = b - a
        denominator = cross(ray, edge)
        if abs(denominator) < 1e-12:
            continue
        t = cross(a - start, edge) / denominator
        u = cross(a - start, ray) / denominator
        if 1e-9 < t < 1 - 1e-9:
            if min(abs(u), abs(u - 1)) < 1e-9:
                raise ValueError(
                    "Reference ray passes a crease vertex; choose another start"
                )
            if 0 < u < 1:
                crossed.append((t, a, edge))
    for _, a, edge in sorted(crossed, key=lambda hit: hit[0], reverse=True):
        point = a + edge / edge.conjugate() * (point - a).conjugate()
    return point


class BaseFoldCheckpoints(unittest.TestCase):
    def test_projected_landmarks(self):
        fixture = json.loads((ASSETS / "sequences" / "landmarks.json").read_text())
        for base, checks in fixture["distance_checks"].items():
            with self.subTest(base=base):
                rows = (ASSETS / "bases" / (base + ".cp")).read_text().splitlines()
                creases = []
                for row in rows:
                    code, x1, y1, x2, y2 = map(float, row.split())
                    if code in (2, 3):
                        creases.append((complex(x1, y1) / 1000, complex(x2, y2) / 1000))
                projected = {
                    name: project_landmark(complex(*coords), creases)
                    for name, coords in fixture["points"].items()
                }
                for a, b, expected in checks:
                    self.assertAlmostEqual(
                        abs(projected[a] - projected[b]),
                        expected,
                        places=7,
                        msg=f"{base}, {a} to {b}",
                    )
