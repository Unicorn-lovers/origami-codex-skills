"""Build the pinned dotFoldSolver and run its connected or disconnected pipeline."""

import hashlib
import io
import math
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

REPOSITORY = "https://github.com/sakusaku858/dotFoldSolver"
REVISION = "96e04662b6b981c5baae11420a825086a47352b8"
# Order is part of the normalized source digest.
SOURCE_FILES = (
    "BoundaryGraph.cpp",
    "BoundaryGraph.h",
    "TileDrawer.py",
    "boundary_extractor.hpp",
    "dotToGraph.cpp",
    "foldsToEdges.cpp",
    "foldsToEdges.h",
    "ftcp.cpp",
    "ftcp.h",
    "loopToFolds.cpp",
    "loopToFolds.h",
    "path_filter.cpp",
    "shortest_euler_walk.cpp",
    "solve_non_connect.cpp",
)
SOURCE_DIGEST = "287df7500ef01ab0a3d9e6f4b1d87e1f7bee3e91c3e1ca33bc807ed8cd2f76d9"
ADAPTER = Path(__file__).with_name("dotfold_native") / "disconnected.cpp"
BINARY_SUFFIX = ".exe" if os.name == "nt" else ""


def _read_sources(source_dir):
    if source_dir is None:
        url = f"https://codeload.github.com/sakusaku858/dotFoldSolver/tar.gz/{REVISION}"
        with urllib.request.urlopen(url, timeout=30) as response:
            archive = response.read(16 * 1024 * 1024)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as files:
            sources = {}
            for name in SOURCE_FILES:
                member = files.getmember(f"dotFoldSolver-{REVISION}/{name}")
                if not member.isfile() or member.size > 1_000_000:
                    raise ValueError(f"Invalid upstream source file {name}")
                sources[name] = files.extractfile(member).read()
    else:
        source = Path(source_dir).expanduser()
        sources = {name: (source / name).read_bytes() for name in SOURCE_FILES}
    digest = hashlib.sha256()
    for name, contents in sources.items():
        contents = contents.replace(b"\r\n", b"\n")
        sources[name] = contents
        digest.update(name.encode() + b"\0" + contents + b"\0")
    if digest.hexdigest() != SOURCE_DIGEST:
        raise ValueError(f"Source files do not match dotFoldSolver revision {REVISION}")
    return sources


def _serial_core(source):
    # The Windows-only memory/path helpers are unused by both search drivers.
    for signature in ("void PrintMemoryUsage", "std::string GetExeDirectory"):
        source, count = re.subn(
            rf"^{re.escape(signature)}\(\) \{{.*?^\}}",
            "",
            source,
            flags=re.MULTILINE | re.DOTALL,
        )
        if count != 1:
            raise ValueError(f"Unexpected upstream definition: {signature}")
    source = re.sub(
        r"^#include <(?:windows.h|sys/time.h|psapi.h|format)>.*$",
        "",
        source,
        flags=re.MULTILINE,
    )
    # Use the deterministic single-thread execution of the same DP. No workers
    # run in this build, so the locks that protect parallel writes are no-ops.
    source = re.sub(r"^#pragma omp .*?$", "", source, flags=re.MULTILINE)
    return source.replace(
        "#include <omp.h>",
        """
using omp_lock_t = int;
inline void omp_init_lock(omp_lock_t *) {}
inline void omp_destroy_lock(omp_lock_t *) {}
inline void omp_set_lock(omp_lock_t *) {}
inline void omp_unset_lock(omp_lock_t *) {}
""",
    )


def _build(destination, sources):
    source = destination / "source"
    source.mkdir()
    for name, contents in sources.items():
        (source / name).write_bytes(contents)
    core = destination / "ftcp_serial.cpp"
    core.write_text(_serial_core(sources["ftcp.cpp"].decode()), encoding="utf-8")
    compiler = shutil.which(os.environ.get("CXX", "c++"))
    if not compiler:
        raise ValueError(
            "A C++17 compiler (c++ or CXX) is required for the first build"
        )
    # Upstream relies on transitive includes for INT_MAX and std::inserter.
    common = [
        compiler,
        "-std=c++17",
        "-O2",
        "-include",
        "climits",
        "-include",
        "iterator",
        "-I",
        str(source),
    ]
    core_objects = []
    targets = {
        "dotToGraph": ["dotToGraph.cpp", "BoundaryGraph.cpp", "loopToFolds.cpp"],
        "disconnected": [ADAPTER],
        "shortest_euler_walk": ["shortest_euler_walk.cpp"],
        "path_filter": ["path_filter.cpp"],
    }

    def compile_stage(arguments):
        subprocess.run(
            common + arguments,
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
        )

    for unit in (core, source / "foldsToEdges.cpp"):
        obj = str(destination / (unit.stem + ".o"))
        compile_stage(["-c", str(unit), "-o", obj])
        core_objects.append(obj)
    for name, units in targets.items():
        units = [str(source / unit) for unit in units]
        if name in ("disconnected", "dotToGraph"):
            units += core_objects
        compile_stage(units + ["-o", str(destination / (name + BINARY_SUFFIX))])
    for path in core_objects:
        Path(path).unlink()
    core.unlink()


def prepare_solver(*, cache_dir=None, source_dir=None):
    """Return the installed directory containing native binaries and pinned source/."""
    base = (
        Path(
            cache_dir
            or os.environ.get("DOTFOLD_CACHE_DIR")
            or (
                Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
                / "origami-crease-pattern-generator"
                / "dotfold"
            )
        )
        .expanduser()
        .resolve()
    )
    base.mkdir(parents=True, exist_ok=True)
    version = hashlib.sha256(
        Path(__file__).read_bytes() + ADAPTER.read_bytes()
    ).hexdigest()[:12]
    system = f"{platform.system()}-{platform.machine()}"
    final = base / f"{REVISION}-{system}-{version}"
    if final.is_dir():
        return final
    with tempfile.TemporaryDirectory(dir=base, prefix=".build-") as workspace:
        staged = Path(workspace) / "install"
        staged.mkdir()
        _build(staged, _read_sources(source_dir))
        try:
            staged.rename(final)
        except OSError:
            if not final.is_dir():  # A concurrent builder may have published first.
                raise
    return final


def _perimeter(mask):
    rows = [f"0{mask[i : i + 8]}0" for i in range(0, 64, 8)]
    rows = ["0" * 10, *rows, "0" * 10]
    return sum(
        sum(
            rows[y + dy][x + dx] == "0" for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))
        )
        for y in range(1, 9)
        for x in range(1, 9)
        if rows[y][x] == "1"
    )


def _candidate(output):
    tiles = re.findall(r"^CPSTR:[ \t]*(.*)$", output, re.MULTILINE)
    corners = re.findall(r"^CORNERS:[ \t]*(.*)$", output, re.MULTILINE)
    if tiles in ([""], ["No CP"]) or (not tiles and "No CP" in output.splitlines()):
        return None
    if len(tiles) != 1 or not re.fullmatch(r"(?:[0-2][0-9]|3[0-5]){49}", tiles[0]):
        raise ValueError("Solver returned missing or malformed CPSTR")
    if len(corners) != 1 or not re.fullmatch(
        r"[01](?:[ \t]+[01]){3}", corners[0].strip()
    ):
        raise ValueError("Solver returned missing or malformed CORNERS")
    return {"cpstr": tiles[0], "corners": list(map(int, corners[0].split()))}


def solve_mask(mask, *, cache_dir=None, source_dir=None, timeout=60):
    """Run a normalized binary 8×8 target. timeout is a wall budget for native search.

    The first use builds a cached executable separately. stdout and stderr retain
    native evidence for each outcome, including partial output on timeout.
    """
    if not isinstance(mask, str) or not re.fullmatch(r"[01]{64}", mask):
        raise ValueError("Expected exactly 64 row-major binary pixels")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Expected a positive finite search timeout")
    result = {
        "input64": mask,
        "revision": REVISION,
        "repository": REPOSITORY,
        "status": "error",
        "branch": None,
        "loop_length": None,
        "stdout": "",
        "stderr": "",
        "reason": "",
        "perimeter": _perimeter(mask),
        "commands": [],
    }
    try:
        binaries = prepare_solver(cache_dir=cache_dir, source_dir=source_dir)
    except (
        OSError,
        ValueError,
        KeyError,
        EOFError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as exc:
        diagnostic = getattr(exc, "stderr", "") or ""
        if isinstance(diagnostic, bytes):
            diagnostic = diagnostic.decode(errors="replace")
        result.update(reason=f"Native setup failed: {exc}", stderr=diagnostic)
        return result
    result["source_dir"] = str(binaries / "source")
    deadline = time.monotonic() + timeout

    try:
        with tempfile.TemporaryDirectory(prefix="dotfold-run-") as work:

            def run(program, *args):
                result["commands"].append([program, *args])
                proc = subprocess.run(
                    [str(binaries / (program + BINARY_SUFFIX)), *args],
                    cwd=work,
                    check=False,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=max(0, deadline - time.monotonic()),
                )
                result["stdout"] += proc.stdout
                result["stderr"] += proc.stderr
                if proc.returncode:
                    raise ValueError(f"{program} exited with status {proc.returncode}")
                return proc.stdout

            measured = run("dotToGraph", "-mode=calcLength", mask)
            match = re.search(r"^LOOP_LENGTH:\s*(\d+)\s*$", measured, re.MULTILINE)
            if not match:
                raise ValueError("Missing LOOP_LENGTH from upstream preflight")
            length = int(match[1])
            result["loop_length"] = length
            if length != 32:
                reason = (
                    "No connecting walk found within the upstream depth limit"
                    if length == 2**31 - 1
                    else f"Upstream requires circuit length 32, got {length}"
                )
                result.update(status="unsupported", reason=reason)
                return result
            if result["perimeter"] == length:
                result["branch"] = "connected"
                output = run("dotToGraph", "-mode=findCP", mask, "1")
            else:
                result["branch"] = "disconnected"
                run("disconnected", "edges", mask)
                walks = run("shortest_euler_walk", "edges.txt", "solutions.txt")
                if "Found 0 shortest walks." in walks.splitlines():
                    result.update(
                        status="no_candidate", reason="Upstream found no boundary walks"
                    )
                    return result
                # path_filter assumes every path has 32 vertices.
                with (Path(work) / "solutions.txt").open() as paths:
                    if any(len(line.split()) != 32 for line in paths):
                        raise ValueError("Unexpected length in upstream boundary walks")
                run("path_filter")
                output = run("disconnected", "tiles")
            candidate = _candidate(output)
            if candidate is None:
                result.update(
                    status="no_candidate",
                    reason="Upstream search returned no crease pattern",
                )
            else:
                result.update(status="candidate", **candidate)
    except subprocess.TimeoutExpired as exc:
        for field, stream in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            if stream:
                result[field] += (
                    stream.decode(errors="replace")
                    if isinstance(stream, bytes)
                    else stream
                )
        result.update(
            status="timeout", reason=f"Native search exceeded {timeout:g} seconds"
        )
    except (OSError, ValueError) as exc:
        result.update(status="error", reason=str(exc))
    return result
