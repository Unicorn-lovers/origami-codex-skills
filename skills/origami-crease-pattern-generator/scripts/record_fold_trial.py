#!/usr/bin/env python3
"""Locate an actual paper observation on the CP and prepare one revision to try."""

import argparse
import copy
import hashlib
import json
import math
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from base_preview import svg_view


def file_digest(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def plan_digest(plan):
    data = json.dumps(
        plan, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def revised_plan(plan, pointer, value):
    if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        raise ValueError(
            "use a JSON pointer such as /parameters/ear_root or /operations/1/fraction"
        )
    result = copy.deepcopy(plan)
    holder = result
    tokens = pointer[1:].split("/")
    for i, token in enumerate(tokens):
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(holder, list) and re.fullmatch(r"0|[1-9][0-9]*", key):
            key = int(key)
        try:
            current = holder[key]
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError(f"unknown design parameter {pointer}") from exc
        if i + 1 == len(tokens):
            new = json.loads(value)
            if any(
                type(v) not in (float, int) or not math.isfinite(v)
                for v in (current, new)
            ):
                raise ValueError(
                    "change an existing numeric parameter to a finite JSON number"
                )
            if current == new:
                raise ValueError("the proposed value equals the current value")
            holder[key] = new
            return result, {"pointer": pointer, "before": current, "after": new}
        holder = current


def valid_point(xy):
    return (
        isinstance(xy, (list, tuple))
        and len(xy) == 2
        and all(
            type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in xy
        )
    )


def paper_geometry(cp):
    """Render material coordinates in the normalized frame of the rectangular sheet."""
    rows = []
    boundary = []
    for row in cp.read_text().splitlines():
        kind, *coords = row.split()
        x, y, u, v = map(float, coords)
        rows.append((int(kind), (x, y), (u, v)))
        if kind == "1":
            boundary.extend(((x, y), (u, v)))
    if not boundary:
        raise ValueError("the CP needs a paper boundary")
    xs, ys = zip(*boundary)
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0, max(ys) - y0
    if min(w, h) <= 0:
        raise ValueError("the CP boundary has zero extent")
    return rows, (x0, y0, w, h)


def comparison(previous, cp_hash, design_hash, feature, outcome):
    old = load(previous / "trial.json")
    if feature != old["feature"]:
        raise ValueError(
            f"previous observation concerns {old['feature']!r}; compare the same feature"
        )
    if cp_hash == old["candidate_sha256"] and design_hash == old["plan_sha256"]:
        relation = "same_candidate_refold"
    elif design_hash == old.get("proposed_change", {}).get("next_plan_sha256"):
        relation = "proposed_revision_refold"
    else:
        raise ValueError(
            "candidate and plan do not match the previous trial or its proposed next plan"
        )
    return {
        "previous_trial_sha256": file_digest(previous / "trial.json"),
        "relation": relation,
        "cp_changed": cp_hash != old["candidate_sha256"],
        "reported_outcome": outcome,
        "previous_observation": old["observation"],
        "previous_paper": old.get("paper"),
        "previous_location": old["material_point_normalized"],
        "previous_proposal": old.get("proposed_change"),
    }


def record(args):
    cp = args.candidate / "candidate.cp"
    manifest = load(args.candidate / "adaptation.json")
    cp_hash = file_digest(cp)
    if cp_hash != manifest.get("candidate_sha256"):
        raise ValueError(
            "candidate.cp has changed since its material landmarks were recorded"
        )
    anchor = manifest["landmarks_normalized"].get(args.feature)
    if not valid_point(anchor):
        raise ValueError(
            "choose a named feature with normalized material coordinates in adaptation.json"
        )
    point = args.point if args.point is not None else anchor
    if not valid_point(point):
        raise ValueError("material point must have x and y in [0,1]")
    if not args.observation.strip():
        raise ValueError("describe the observed behavior of the paper")
    if bool(args.expect) != bool(args.change) or (
        args.expect and not args.expect.strip()
    ):
        raise ValueError(
            "use --change with --expect to describe how a single revision can be checked"
        )
    if bool(args.previous) != bool(args.outcome):
        raise ValueError(
            "use --previous with --outcome to compare this fold with a prior one"
        )
    source_plan = args.plan or args.candidate / "plan.json"
    plan = load(source_plan)
    design_hash = plan_digest(plan)
    if "plan_sha256" in manifest and manifest["plan_sha256"] != design_hash:
        raise ValueError(
            "the generating plan has changed since this candidate was built"
        )
    if "plan_sha256" not in manifest and "operations" in plan:
        # Old adaptation manifests include a CP digest but no separate plan digest.
        from adapt_base import prepare, write_cp

        with tempfile.TemporaryDirectory() as tmp:
            replay = Path(tmp) / "candidate.cp"
            segments, *_ = prepare(plan)
            write_cp(replay, segments)
            if file_digest(replay) != cp_hash:
                raise ValueError(
                    "this adaptation plan does not regenerate candidate.cp"
                )
    result = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "evidence": "paper_observation_with_photos" if args.photo else "paper_observation",
        "candidate_sha256": cp_hash,
        "plan_sha256": design_hash,
        "feature": args.feature,
        "feature_anchor_normalized": anchor,
        "material_point_normalized": point,
        "paper": args.paper,
        "observation": args.observation.strip(),
        "photos": [],
    }
    next_plan = None
    if args.change:
        next_plan, change = revised_plan(plan, *args.change)
        result["proposed_change"] = {
            **change,
            "expected_observation": args.expect.strip(),
            "next_plan_sha256": plan_digest(next_plan),
        }
    if args.previous:
        result["comparison"] = comparison(
            args.previous, cp_hash, design_hash, args.feature, args.outcome
        )
    segments, (x, y, w, h) = paper_geometry(cp)
    spot = [x + point[0] * w, y + point[1] * h]
    svg = svg_view(
        segments,
        {args.feature: spot},
        "Paper trial",
        "Marker shows the recorded location on the unfolded sheet.",
    )
    photos = []
    for photo in args.photo:
        if photo.suffix.lower() not in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".heic",
            ".heif",
            ".tif",
            ".tiff",
            ".avif",
        }:
            raise ValueError(f"unsupported photo extension on {photo.name}")
        if not photo.is_file() or photo.stat().st_size <= 0:
            raise ValueError(f"missing or empty photo: {photo}")
        photos.append(photo)
    out = args.out_dir
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        staged = Path(tmp) / "trial"
        staged.mkdir()
        for i, photo in enumerate(photos, 1):
            name = f"photo-{i:02d}{photo.suffix.lower()}"
            shutil.copyfile(photo, staged / name)
            result["photos"].append(
                {"file": name, "sha256": file_digest(staged / name)}
            )
        (staged / "location.svg").write_text(svg, encoding="utf-8")
        if next_plan is not None:
            save(staged / "next-plan.json", next_plan)
        save(staged / "trial.json", result)
        # Reserve the destination before moving the finished trial into place.
        out.mkdir(exist_ok=False)
        installed = []
        try:
            for artifact in sorted(
                staged.iterdir(), key=lambda item: item.name == "trial.json"
            ):
                installed.append(artifact.rename(out / artifact.name))
        except OSError:
            for artifact in installed:
                artifact.unlink()
            out.rmdir()
            raise
    return out / "trial.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "candidate",
        type=Path,
        help="folder containing candidate.cp, adaptation.json and plan.json",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        help="original generating plan, when stored outside the candidate folder",
    )
    parser.add_argument(
        "--out-dir", type=Path, required=True, help="new local directory for the trial"
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="exact key from adaptation.json landmarks_normalized",
    )
    parser.add_argument(
        "--point",
        nargs=2,
        type=float,
        metavar=("X", "Y"),
        help="observed location on the original paper, normalized",
    )
    parser.add_argument(
        "--photo",
        type=Path,
        action="append",
        default=[],
        help="copy this real paper photo into the local trial; repeat for more views",
    )
    parser.add_argument(
        "--observation", required=True, help="folder's observation of the named part"
    )
    parser.add_argument("--paper", help="sheet size, material and thickness if known")
    parser.add_argument(
        "--change",
        nargs=2,
        metavar=("JSON_POINTER", "NEW_NUMBER"),
        help="emit next-plan.json with one revised numeric parameter",
    )
    parser.add_argument(
        "--expect", help="observable difference to check in the next paper trial"
    )
    parser.add_argument(
        "--previous", type=Path, help="directory of previous trial of this feature"
    )
    parser.add_argument(
        "--outcome", choices=["improved", "unchanged", "worse", "inconclusive"]
    )
    args = parser.parse_args()
    try:
        print(record(args))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        parser.exit(2, f"record_fold_trial: {exc}\n")


if __name__ == "__main__":
    main()
