#!/usr/bin/env python3
"""Make an editable origami crease pattern from an eight-by-eight pixel target."""

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from dotfold_geometry import crease_svg, make_fold, projection
from dotfold_input import load_target
from dotfold_solver import solve_mask

FLAT_REV = "d50004815fb738d009e5b87b2307fbaefa717ef0"
FLAT_HASH = "9f6faa752a17b9f5424de667e8046c8870782a1dc51c51e0032d4c853e2e5053"
FLAT_FILES = ["package.json"] + [
    f"src/{name}.js"
    for name in (
        "avl",
        "compute",
        "constraints",
        "conversion",
        "io",
        "math",
        "note",
        "solver",
        "svg",
    )
]


def verify_flat(folder):
    h = hashlib.sha256()
    for name in FLAT_FILES:
        h.update(
            name.encode()
            + b"\0"
            + (folder / name).read_bytes().replace(b"\r\n", b"\n")
            + b"\0"
        )
    if h.hexdigest() != FLAT_HASH:
        raise ValueError(f"Flat-Folder sources must match revision {FLAT_REV}")
    return folder


def flat_source(cache, local=None):
    if local:
        return verify_flat(local)
    folder = cache / f"flat-folder-{FLAT_REV}-{FLAT_HASH[:12]}"
    if folder.is_dir():
        return verify_flat(folder)
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as tmp:
        staged = Path(tmp) / "flat"
        (staged / "src").mkdir(parents=True)
        base = (
            f"https://raw.githubusercontent.com/origamimagiro/flat-folder/{FLAT_REV}/"
        )
        for name in FLAT_FILES:
            with urllib.request.urlopen(base + name, timeout=20) as response:
                (staged / name).write_bytes(response.read(1_000_000))
        verify_flat(staged)
        try:
            staged.rename(folder)
        except OSError:
            if not folder.is_dir():
                raise
    return verify_flat(folder)


def put(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def art_svg(target, cells=None):
    ink = target["foreground"] or "#161616"
    bg = target["background"] or "#ffffff"
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="384" height="384" viewBox="0 0 8 8">'
    ]
    if bg != "transparent":
        svg.append(f'<rect width="8" height="8" fill="{bg}"/>')
    if cells is None:
        svg.extend(
            f'<rect x="{i % 8}" y="{i // 8}" width="1" height="1" fill="{ink}"/>'
            for i, v in enumerate(target["bits"])
            if v == "1"
        )
    else:
        for cell in cells:
            points = " ".join(f"{x:.8g},{y:.8g}" for x, y in cell["polygon"])
            color = ink if cell["ink"] else bg
            svg.append(
                f'<polygon points="{points}" fill="{color}" shape-rendering="crispEdges"/>'
            )
    return "\n".join([*svg, "</svg>", ""])


def export_match(work, target, result):
    graph = result.pop("graph")
    graph["frame_classes"] = ["creasePattern"]
    put(work / "assigned.fold", graph)
    put(work / "folded.fold", result.pop("folded"))
    cells = result.pop("cells")
    put(work / "visible-cells.json", cells)
    (work / "folded.svg").write_text(art_svg(target, cells), encoding="utf-8")
    (work / "creases.svg").write_text(crease_svg(graph), encoding="utf-8")
    codes = {"B": 1, "M": 2, "V": 3}
    rows = []
    for (a, b), role in zip(
        graph["edges_vertices"], graph["edges_assignment"], strict=True
    ):
        ends = [graph["vertices_coords"][i] for i in (a, b)]
        coords = [val for x, y in ends for val in (125 * x, 125 * (8 - y))]
        rows.append(" ".join([str(codes[role]), *(f"{v:.10g}" for v in coords)]))
    (work / "candidate.cp").write_text("\n".join(rows) + "\n", encoding="utf-8")


def generate(work, args, target, input_digest):
    put(work / "target.json", target)
    (work / "target.svg").write_text(art_svg(target), encoding="utf-8")
    solver = solve_mask(
        target["bits"],
        cache_dir=args.cache_dir,
        source_dir=args.source_dir,
        timeout=args.timeout,
    )
    native_source = solver.pop("source_dir", None)
    put(work / "solver.json", solver)
    report = {
        "sourceSha256": input_digest,
        "solverRevision": solver["revision"],
        "status": solver["status"],
        "reason": solver.get("reason", ""),
        "physicalTrial": "untested",
    }
    if solver["status"] != "candidate":
        return report
    fold = make_fold(solver["cpstr"], solver["corners"], Path(native_source))
    put(work / "unassigned.fold", fold)
    (work / "creases.svg").write_text(crease_svg(fold), encoding="utf-8")
    report["status"] = "candidate_only"
    try:
        report["projection"] = projection(fold, target["bits"])
    except ValueError as exc:
        report["reason"] = f"Candidate failed its folded geometry check: {exc}"
        return report
    report["layerSolverRevision"] = FLAT_REV
    try:
        node = shutil.which("node")
        if not node:
            raise ValueError("Node.js is required to compute visible layers")
        source = flat_source(args.cache_dir, args.flat_folder_dir)
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "layers.json"
            cmd = [
                node,
                str(Path(__file__).with_name("dotfold_layers.mjs")),
                str(source),
                str(work / "unassigned.fold"),
                str(work / "target.json"),
                str(result_path),
                str(args.max_states),
            ]
            process = subprocess.run(
                cmd, check=False, capture_output=True, text=True, timeout=args.timeout
            )
            if process.returncode:
                raise ValueError(f"Flat-Folder failed: {process.stderr.strip()}")
            result = json.loads(result_path.read_text(encoding="utf-8"))
        if result["status"] == "exact":
            export_match(work, target, result)
            report.update(
                status="exact",
                reason="Visible foreground covers precisely the requested pixels",
            )
        else:
            report["reason"] = result["status"]
        report["layers"] = result
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report["reason"] = f"Layer verification incomplete: {exc}"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="8×8 .txt mask or PNG")
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="new output directory"
    )
    parser.add_argument("--foreground", help="foreground hex RGB for a two-colour PNG")
    default_cache = (
        Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
        / "origami-crease-pattern-generator/dotfold"
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.environ.get("DOTFOLD_CACHE_DIR") or default_cache),
    )
    parser.add_argument(
        "--source-dir", type=Path, help="local pinned dotFoldSolver source"
    )
    parser.add_argument(
        "--flat-folder-dir", type=Path, help="local pinned Flat-Folder repository root"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="seconds for each solver, excluding setup",
    )
    parser.add_argument(
        "--max-states", type=int, default=512, help="maximum layer states to examine"
    )
    args = parser.parse_args()
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0 or args.max_states < 1:
            raise ValueError("timeout and max-states must be positive")
        if args.out_dir.exists():
            raise ValueError(f"output directory already exists: {args.out_dir}")
        input_digest = hashlib.sha256(args.target.read_bytes()).hexdigest()
        target = load_target(args.target, foreground=args.foreground)
        if hashlib.sha256(args.target.read_bytes()).hexdigest() != input_digest:
            raise ValueError("input changed while reading the target")
        args.out_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=args.out_dir.parent) as tmp:
            work = Path(tmp) / "result"
            work.mkdir()
            report = generate(work, args, target, input_digest)
            put(work / "report.json", report)
            # Reserve a new destination; replacing the empty directory publishes
            # the complete bundle atomically on POSIX.
            args.out_dir.mkdir()
            try:
                if os.name == "nt":
                    for item in sorted(work.iterdir(), key=lambda p: p.name == "report.json"):
                        item.rename(args.out_dir / item.name)
                else:
                    os.replace(work, args.out_dir)
            except OSError:
                if not any(args.out_dir.iterdir()):
                    args.out_dir.rmdir()
                raise
        print(
            f"{report['status']}: {report['reason']} ({args.out_dir / 'report.json'})"
        )
        return 0 if report["status"] == "exact" else 1
    except (ValueError, OSError) as exc:
        parser.exit(2, f"dotfold: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
