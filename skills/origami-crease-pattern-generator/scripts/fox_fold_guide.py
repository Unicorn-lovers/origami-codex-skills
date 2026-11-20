#!/usr/bin/env python3
"""Draw a printable Japanese folding guide from one generated fox-face plan."""

import argparse
import json
from html import escape
from pathlib import Path

from fox_face import geometry


def text(x, y, label, size=15, **extra):
    attrs = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in extra.items())
    return (
        f'<text x="{x}" y="{y}" font-size="{size}" {attrs}>{escape(str(label))}</text>'
    )


def panel(x, y, title, body, diagram):
    lines = [
        f'<g transform="translate({x},{y})">',
        '<rect width="354" height="394" rx="10" fill="#fffdfa" stroke="#d4d4c8"/>',
        text(16, 32, title, 19, font_weight="bold"),
        *diagram,
    ]
    lines.extend(text(16, 290 + 23 * i, line) for i, line in enumerate(body))
    return "".join(lines) + "</g>"


def diagram(elements, *, center_y=148, scale=112):
    def coord(p):
        return (177 + scale * p[0], center_y + scale * p[1])

    def point(p):
        x, y = coord(p)
        return f"{x:.2f},{y:.2f}"

    result = []
    for kind, *args in elements:
        if kind == "paper":
            polygon, color = args
            pts = " ".join(map(point, polygon))
            result.append(
                f'<polygon points="{pts}" fill="{color}" stroke="#574c44" stroke-width="1.5" stroke-linejoin="round"/>'
            )
        elif kind in ("valley", "mountain", "guide"):
            a, b = args
            color, dash = {
                "valley": ("#146aa1", "7 4"),
                "mountain": ("#813d3b", "11 3 2 3"),
                "guide": ("#858681", "2 4"),
            }[kind]
            result.append(
                f'<path d="M{point(a)} L{point(b)}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"/>'
            )
        elif kind == "arrow":
            a, control, b = args
            result.append(
                f'<path d="M{point(a)} Q{point(control)} {point(b)}" fill="none" stroke="#265b53" stroke-width="2.5" marker-end="url(#arrow)"/>'
            )
        elif kind == "tag":
            p, label, dx, dy = args
            x, y = coord(p)
            result.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.7" fill="#403c37"/>')
            result.append(
                text(round(x + dx, 2), round(y + dy, 2), label, 13, font_weight="bold")
            )
    return result


def downward_panels(plan):
    params = plan["parameters"]
    geometry(params)  # Use the same domain and collision limits as the generated CP.
    p, s, d = (params[k] for k in ("ear_root", "ear_slope", "muzzle_depth"))
    q = (1 - p) / (1 - s)
    ear = (1 - 2 * (1 - p) / (1 + s * s), -2 * s * (1 - p) / (1 + s * s))
    L, R, N = (-1, 0), (1, 0), (0, 1)
    H = (0, 0)
    lp, rp = (-p, 0), (p, 0)
    lq, rq = (q - 1, q), (1 - q, q)
    le = (-ear[0], ear[1])
    m1, m2 = (-d, 1 - d), (d, 1 - d)
    np = (0, 1 - 2 * d)
    orange = "#e5a170"
    ear_color = "#edb38b"
    cream = "#fff3d9"
    simple = [("paper", [L, R, N], orange)]
    ears = [
        ("paper", [lp, rp, rq, N, lq], orange),
        ("paper", [lp, lq, le], ear_color),
        ("paper", [rp, rq, ear], ear_color),
    ]
    center_pct = f"{100 * p:.1f}%"
    slope_pct = f"{100 * q:.1f}%"
    muzzle_pct = f"{100 * d:.1f}%"
    pages = [
        panel(
            34,
            124,
            "1　対角線で二枚重ねにする",
            [
                "色の面を上にして、正方形を図の向きに置く。",
                "左右の角を結ぶ線を山折りにし、上の角を",
                "紙の後ろへ回して、下の角に重ねる。",
                "上辺は輪、下の先端は二枚に開く。",
            ],
            diagram(
                [
                    ("paper", [L, (0, -1), R, N], orange),
                    ("mountain", L, R),
                    ("arrow", (0.03, -0.94), (0.82, -0.23), (0.08, 0.94)),
                    ("tag", (0, -1), "D", 7, -3),
                    ("tag", N, "B", 7, 9),
                    ("tag", L, "C", -15, 4),
                    ("tag", R, "A", 6, 4),
                ],
                center_y=156,
                scale=93,
            ),
        ),
        panel(
            406,
            124,
            "2　左右の耳の折り位置を取る",
            [
                "上辺の中点を O とする。O から左右の端へ、",
                f"それぞれ半辺の {center_pct} の位置に P をとる。",
                f"斜辺は、左右の端から下の先端へ {slope_pct}",
                "の位置に Q をとる。左右の P と Q を結ぶ。",
            ],
            diagram(
                [
                    *simple,
                    ("guide", H, N),
                    ("valley", lp, lq),
                    ("valley", rp, rq),
                    ("tag", H, "O", -5, -8),
                    ("tag", rp, "P", -4, -8),
                    ("tag", rq, "Q", 7, 9),
                ],
                center_y=129,
            ),
        ),
        panel(
            34,
            538,
            "3　二枚一緒に耳を折り上げる",
            [
                "片側ずつ、外の角を二枚重ねのまま持つ。",
                "P–Q を手前に谷折りし、外の角が上へ",
                "突き出るまで平らに倒す。反対側も折る。",
                "二つの耳の高さをそろえ、下の先端を残す。",
            ],
            diagram(
                [
                    *ears,
                    ("valley", lp, lq),
                    ("valley", rp, rq),
                    (
                        "arrow",
                        (0.99, -0.01),
                        (1.03, -0.48),
                        (ear[0] + 0.035, ear[1] - 0.025),
                    ),
                    ("tag", rp, "P", 4, 15),
                    ("tag", rq, "Q", 7, 8),
                ],
                center_y=117,
            ),
        ),
        panel(
            406,
            538,
            "4　手前の一枚で鼻先を返す",
            [
                "下の先端から上に、元の三角形の高さの",
                f"{muzzle_pct} だけ測り、上辺と平行な線で折る。",
                "手前の一枚だけを上へ谷折りして裏色を出す。",
                "奥の一枚の角が、顔の下端の鼻先に残る。",
            ],
            diagram(
                [
                    *ears,
                    ("paper", [m1, N, m2], cream),
                    ("paper", [m1, np, m2], cream),
                    ("valley", m1, m2),
                    ("arrow", (0.012, 1.045), (0.38, 0.96), (0.043, np[1] + 0.01)),
                ],
                center_y=117,
            ),
        ),
    ]
    return pages


def ruff_panels(plan):
    p = plan["parameters"]
    geometry(p, route="ruff")
    slope, brow = p["ear_slope"], p["brow_height"]
    q = 1 / (1 + slope)
    ear = ((slope * slope - 1) / (slope * slope + 1), -2 * slope / (1 + slope * slope))
    left, right, tip, nose = (-1, 0), (1, 0), (0, -1), (0, 0)
    lq, rq = (q - 1, -q), (1 - q, -q)
    le = (-ear[0], ear[1])
    lp, rp = (brow - 1, -brow), (1 - brow, -brow)
    orange, cream = "#df945e", "#fff1d6"

    # Both sides of the temporary lower edge reverse. The old paper corners
    # become the ear points, and its midpoint remains stationary as the nose.
    def face(top):
        return [
            ("paper", [nose, lq, le], orange),
            ("paper", [nose, rq, ear], orange),
            ("paper", [nose, lq, *top, rq], cream),
        ]

    return [
        panel(
            34,
            124,
            "1　色を内側にして半分に折る",
            [
                "色の面を上にして、紙をひし形に置く。",
                "下の角 D を上の角 B に重ねて谷折りする。",
                "長い辺が下、二枚の自由な角が上に来る。",
                "この底辺の谷折りは、後で山に返す。",
            ],
            diagram(
                [
                    ("paper", [left, tip, right, (0, 1)], orange),
                    ("valley", left, right),
                    ("arrow", (0.02, 0.94), (0.70, 0.10), (0.06, -0.90)),
                    ("tag", tip, "B", 7, -3),
                    ("tag", (0, 1), "D", 7, 9),
                    ("tag", left, "A", -15, 4),
                    ("tag", right, "C", 6, 4),
                ],
                center_y=156,
                scale=93,
            ),
        ),
        panel(
            406,
            124,
            "2　耳の根元に折り筋をつける",
            [
                "底辺の中点 O が鼻先になる。",
                f"左右の角から頂点へ、各斜辺の {100 * q:.1f}% の",
                "位置に Q をとる。二枚重ねで O–Q に",
                "折り筋をつけて戻す。反対側も同様。",
            ],
            diagram(
                [
                    ("paper", [left, tip, right], cream),
                    ("guide", nose, tip),
                    ("valley", nose, lq),
                    ("valley", nose, rq),
                    ("tag", nose, "O", -4, 16),
                    ("tag", rq, "Q", 7, -3),
                ],
                center_y=231,
            ),
        ),
        panel(
            34,
            538,
            "3　左右の角を返して耳を立てる",
            [
                "底辺の右端を開き、O–Q の二本の筋を",
                "色の面から見て谷にする。O と右端を結ぶ",
                "筋を山に返し、先端を上に向けて閉じる。",
                "左端も同じ。O は下端のまま動かさない。",
            ],
            diagram(
                [
                    *face([tip]),
                    ("guide", nose, rq),
                    ("guide", nose, lq),
                    (
                        "arrow",
                        (0.99, -0.02),
                        (1.05, -0.69),
                        (ear[0] + 0.035, ear[1] - 0.015),
                    ),
                    ("tag", nose, "O", -4, 16),
                    ("tag", rq, "Q", 7, -3),
                ],
                center_y=230,
            ),
        ),
        panel(
            406,
            538,
            "4　額の二枚を表と裏に返す",
            [
                f"O から三角形の高さの {100 * brow:.1f}% 上に、",
                "底辺と平行な折り線をとる。上の二枚を",
                "分け、手前の一枚は手前へ、奥の一枚は",
                "背面へ折り下げる。両耳の先を自由に保つ。",
            ],
            diagram(
                [
                    *face([lp, rp]),
                    ("paper", [lp, rp, (0, 1 - 2 * brow)], orange),
                    ("valley", lp, rp),
                    ("arrow", (0.04, -0.98), (0.37, -0.67), (0.05, 1 - 2 * brow)),
                    ("tag", nose, "O", -4, 16),
                ],
                center_y=230,
            ),
        ),
    ]


def generate(plan):
    pages = ruff_panels(plan) if plan.get("route") == "ruff" else downward_panels(plan)
    name = plan["name"]
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 794 1123">',
            '<defs><marker id="arrow" viewBox="0 0 8 8" markerWidth="5" markerHeight="5" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#265b53"/></marker></defs>',
            '<rect width="794" height="1123" fill="#f6f5f0"/>',
            '<g fill="#252f2d" font-family="Hiragino Sans, Yu Gothic, Meiryo, Noto Sans CJK JP, sans-serif">',
            text(34, 58, "正面を向いたキツネの顔", 32, font_weight="bold"),
            text(
                35,
                92,
                f"正方形1枚　／　設計 {name}　／　色と白の両面紙を使います。",
                16,
            ),
            *pages,
            text(34, 980, "折り筋の見方", 19, font_weight="bold"),
            '<path d="M36 1012 h68" stroke="#813d3b" stroke-width="2" stroke-dasharray="11 3 2 3"/>',
            text(112, 1018, "山折り", 16),
            '<path d="M210 1012 h68" stroke="#146aa1" stroke-width="2" stroke-dasharray="7 4"/>',
            text(286, 1018, "谷折り", 16),
            text(
                34,
                1062,
                "展開図上の角は、左上から時計回りに A・B・C・D。図1は紙を回転した向き。",
                15,
            ),
            text(
                34,
                1091,
                "長さは割合で示しています。折った後は、正面から両耳・額・鼻先の見え方を確かめます。",
                15,
            ),
            "</g></svg>",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="materialized fox-face plan.json")
    parser.add_argument(
        "--output", type=Path, required=True, help="new printable A4 SVG"
    )
    args = parser.parse_args()
    try:
        svg = generate(json.loads(args.plan.read_text(encoding="utf-8")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as f:
            f.write(svg)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"fox_fold_guide: {exc}\n")


if __name__ == "__main__":
    main()
