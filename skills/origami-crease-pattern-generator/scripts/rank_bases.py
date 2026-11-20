#!/usr/bin/env python3
"""Rank bundled origami bases against named flap and surface requirements."""

from __future__ import annotations

import argparse
from functools import lru_cache
from itertools import combinations
import json
from pathlib import Path
from typing import Any

from base_regions import conflicts, overlap_polygon, signed_area


LENGTHS = ("long", "medium", "short")
WIDTHS = ("broad", "medium", "narrow")
PRIORITY_PENALTY = {"essential": 25.0, "supporting": 10.0, "optional": 2.0}
PRIORITY_WEIGHT = {"essential": 3.0, "supporting": 1.0, "optional": 0.25}
DERIVE_PENALTY = {"essential": 8.0, "supporting": 3.0, "optional": 1.0}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def validate_requirements(data: dict[str, Any]) -> dict[str, Any]:
    subject = data.get("subject", "unnamed subject")
    features = data.get("features", [])
    surfaces = data.get("surfaces", [])
    preferences = data.get("preferences", {})
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject must be a non-empty string")
    if not isinstance(features, list) or not features:
        raise ValueError("features must be a non-empty array")
    if not isinstance(surfaces, list):
        raise ValueError("surfaces must be an array")
    if not isinstance(preferences, dict):
        raise ValueError("preferences must be an object")

    normalized_features = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise ValueError(f"features[{index}] must be an object")
        name = feature.get("name")
        length = feature.get("length")
        width = feature.get("width", "narrow")
        priority = feature.get("priority", "supporting")
        derive_from = feature.get("derive_from")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"features[{index}].name must be a non-empty string")
        if length not in LENGTHS:
            raise ValueError(f"features[{index}].length must be one of {', '.join(LENGTHS)}")
        if width not in WIDTHS:
            raise ValueError(f"features[{index}].width must be one of {', '.join(WIDTHS)}")
        if priority not in PRIORITY_PENALTY:
            raise ValueError(f"features[{index}].priority must be essential, supporting, or optional")
        if derive_from is not None and (not isinstance(derive_from, str) or not derive_from.strip()):
            raise ValueError(f"features[{index}].derive_from must be a non-empty feature name")
        normalized_features.append({
            "name": name.strip(),
            "count": positive_int(feature.get("count", 1), f"features[{index}].count"),
            "length": length,
            "width": width,
            "priority": priority,
            "paired": bool(feature.get("paired", False)),
            "derive_from": derive_from.strip() if derive_from is not None else None,
        })

    feature_names = [feature["name"] for feature in normalized_features]
    if len(set(feature_names)) != len(feature_names):
        raise ValueError("feature names must be unique")
    for feature in normalized_features:
        parent = feature["derive_from"]
        if parent is not None and (parent == feature["name"] or parent not in feature_names):
            raise ValueError(f"feature {feature['name']}.derive_from must name a different feature")
    features_by_name = {feature["name"]: feature for feature in normalized_features}
    for feature in normalized_features:
        parent = feature["derive_from"]
        if parent is not None and features_by_name[parent]["derive_from"] is not None:
            raise ValueError(f"feature {feature['name']}.derive_from cannot point to another derived feature")
        if parent is None:
            continue
        parent_feature = features_by_name[parent]
        if LENGTHS.index(parent_feature["length"]) > LENGTHS.index(feature["length"]):
            raise ValueError(f"feature {feature['name']} cannot be longer than its derive_from parent")
        if WIDTHS.index(parent_feature["width"]) > WIDTHS.index(feature["width"]):
            raise ValueError(f"feature {feature['name']} cannot be broader than its derive_from parent")
        if feature["count"] > parent_feature["count"] and WIDTHS.index(feature["width"]) <= WIDTHS.index(parent_feature["width"]):
            raise ValueError(f"feature {feature['name']} must be narrower than its derive_from parent when split into more parts")

    normalized_surfaces = []
    for index, surface in enumerate(surfaces):
        if not isinstance(surface, dict):
            raise ValueError(f"surfaces[{index}] must be an object")
        name = surface.get("name")
        priority = surface.get("priority", "supporting")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"surfaces[{index}].name must be a non-empty string")
        if priority not in PRIORITY_PENALTY:
            raise ValueError(f"surfaces[{index}].priority must be essential, supporting, or optional")
        size = surface.get("size", "broad")
        if size != "broad":
            raise ValueError(f"surfaces[{index}].size must be broad; represent narrow regions as flaps")
        normalized_surfaces.append({
            "name": name.strip(),
            "count": positive_int(surface.get("count", 1), f"surfaces[{index}].count"),
            "size": size,
            "priority": priority,
        })

    symmetry = preferences.get("symmetry")
    if symmetry is not None and symmetry not in {"bilateral", "rotational", "diagonal", "none"}:
        raise ValueError("preferences.symmetry must be bilateral, rotational, diagonal, or none")
    volume = preferences.get("volume")
    if volume is not None and volume not in {"flat", "3d"}:
        raise ValueError("preferences.volume must be flat or 3d")

    return {
        "subject": subject.strip(),
        "features": normalized_features,
        "surfaces": normalized_surfaces,
        "preferences": preferences,
    }


def validate_catalog(data: dict[str, Any], catalog_path: Path) -> list[dict[str, Any]]:
    bases = data.get("bases")
    if not isinstance(bases, list) or not bases:
        raise ValueError("catalog bases must be a non-empty array")
    region_maps = None
    if "regions" in data:
        if not isinstance(data["regions"], str):
            raise ValueError("catalog regions must be a JSON file name")
        region_maps = load_json(catalog_path.parent / data["regions"])
    seen = set()
    for index, base in enumerate(bases):
        if not isinstance(base, dict):
            raise ValueError(f"catalog bases[{index}] must be an object")
        base_id = base.get("id")
        if not isinstance(base_id, str) or not base_id or base_id in seen:
            raise ValueError(f"catalog bases[{index}].id must be unique")
        seen.add(base_id)
        flaps = base.get("flaps")
        if not isinstance(flaps, list) or not flaps:
            raise ValueError(f"catalog {base_id}.flaps must be a non-empty array")
        flap_ids = set()
        for flap_index, flap in enumerate(flaps):
            if not isinstance(flap, dict):
                raise ValueError(f"catalog {base_id}.flaps[{flap_index}] must be an object")
            flap_id = flap.get("id")
            if not isinstance(flap_id, str) or not flap_id or flap_id in flap_ids:
                raise ValueError(f"catalog {base_id} flap ids must be unique")
            flap_ids.add(flap_id)
            if flap.get("length") not in LENGTHS or flap.get("width") not in WIDTHS:
                raise ValueError(f"catalog {base_id}.{flap_id} needs a valid length and width")
            if "pair" in flap and (not isinstance(flap["pair"], str) or not flap["pair"]):
                raise ValueError(f"catalog {base_id}.{flap_id}.pair must be a non-empty string")
        cp_path = catalog_path.parent / str(base.get("cp", ""))
        if not cp_path.is_file():
            raise ValueError(f"catalog {base_id} CP does not exist: {cp_path}")
        if region_maps is not None:
            mapped = region_maps.get(base_id)
            if (not isinstance(mapped, dict) or set(mapped.get("flaps", {})) != flap_ids
                    or len(mapped.get("surfaces", {})) != base.get("broad_surfaces", 0)):
                raise ValueError(f"catalog {base_id}: region IDs or surface count do not match")
    if region_maps is not None:
        return [{**base, "_region_map": region_maps[base["id"]]} for base in bases]
    return bases


def fit_cost(feature: dict[str, Any], flap: dict[str, Any]) -> float | None:
    requested_length = LENGTHS.index(feature["length"])
    available_length = LENGTHS.index(flap["length"])
    requested_width = WIDTHS.index(feature["width"])
    available_width = WIDTHS.index(flap["width"])
    if available_length > requested_length or available_width > requested_width:
        return None
    weight = PRIORITY_WEIGHT[feature["priority"]]
    return weight * (1.5 * (requested_length - available_length) + (requested_width - available_width))


def allocate_profiles(features: list[dict[str, Any]], flaps: list[dict[str, Any]]) -> tuple[float, list[dict[str, Any]], set[int]]:
    units = []
    for feature in features:
        if feature["derive_from"] is not None:
            continue
        for unit_index in range(feature["count"]):
            units.append({**feature, "unit_index": unit_index})
    units.sort(key=lambda item: (
        -PRIORITY_WEIGHT[item["priority"]],
        LENGTHS.index(item["length"]),
        WIDTHS.index(item["width"]),
        item["name"],
    ))

    @lru_cache(maxsize=None)
    def solve(unit_index: int, used_mask: int) -> tuple[float, tuple[int, ...]]:
        if unit_index == len(units):
            return 0.0, ()
        unit = units[unit_index]
        missing_penalty = PRIORITY_PENALTY[unit["priority"]]
        tail_cost, tail_assignment = solve(unit_index + 1, used_mask)
        best = (missing_penalty + tail_cost, (-1,) + tail_assignment)
        for flap_index, flap in enumerate(flaps):
            if used_mask & (1 << flap_index):
                continue
            cost = fit_cost(unit, flap)
            if cost is None:
                continue
            next_cost, next_assignment = solve(unit_index + 1, used_mask | (1 << flap_index))
            candidate = (cost + next_cost, (flap_index,) + next_assignment)
            if candidate[0] <= best[0] + 1e-9:
                best = candidate
        return best

    cost, assignment = solve(0, 0)
    mapped = [{**unit, "flap_index": flap_index} for unit, flap_index in zip(units, assignment)]
    used = {item["flap_index"] for item in mapped if item["flap_index"] >= 0}
    return cost, mapped, used


def map_reservations(region_map, features, surfaces):
    assignments = {}

    def reserve(name, region_id):
        label = name
        index = 1
        while label in assignments:
            index += 1
            label = f"{name} [{index}]"
        assignments[label] = region_id

    for feature in features:
        for flap in feature["assigned"]:
            reserve(feature["name"], flap["id"])

    # Surface slots are interchangeable in this schema. Among sets of the required
    # size, minimize pairwise overlap with reserved flaps and other selected faces.
    available = region_map["surfaces"]
    count = sum(s["assigned"] for s in surfaces)
    flap_polygons = [region_map["flaps"][key]["polygon"] for key in assignments.values()]

    def overlap_area(a, b):
        return abs(signed_area(overlap_polygon(a, b)))

    flap_cost = {key: sum(overlap_area(region["polygon"], p) for p in flap_polygons)
                 for key, region in available.items()}

    def cost(keys):
        return sum(flap_cost[k] for k in keys) + sum(
            overlap_area(available[a]["polygon"], available[b]["polygon"]) for a, b in combinations(keys, 2))

    chosen = min(combinations(sorted(available), count), key=cost)
    ordered = iter(sorted(chosen, key=lambda key: (flap_cost[key], key)))
    for surface in surfaces:
        surface["region_ids"] = [next(ordered) for _ in range(surface["assigned"])]
        for key in surface["region_ids"]:
            reserve(surface["name"], key)
    return {"suggested_assignments": assignments, "region_conflicts": conflicts(region_map, assignments)}


def rank_base(base: dict[str, Any], requirements: dict[str, Any], catalog_path: Path) -> dict[str, Any]:
    flaps = base["flaps"]
    assignment_cost, units, used_flaps = allocate_profiles(requirements["features"], flaps)
    score = 100.0 - assignment_cost
    transformations = []
    results_by_name = {
        feature["name"]: {
            "name": feature["name"],
            "requested": feature["count"],
            "required_length": feature["length"],
            "required_width": feature["width"],
            "assigned": [],
            "derived": 0,
            "derive_from": feature["derive_from"],
            "source_flap_ids": [],
            "missing": 0,
            "priority": feature["priority"],
            "paired": feature["paired"],
        }
        for feature in requirements["features"]
    }
    for unit in units:
        result = results_by_name[unit["name"]]
        if unit["flap_index"] < 0:
            result["missing"] += 1
            continue
        flap = flaps[unit["flap_index"]]
        result["assigned"].append(flap)
        length_steps = LENGTHS.index(unit["length"]) - LENGTHS.index(flap["length"])
        width_steps = WIDTHS.index(unit["width"]) - WIDTHS.index(flap["width"])
        if length_steps:
            transformations.append(f"shorten {flap['id']} for {unit['name']}")
        if width_steps:
            transformations.append(f"narrow or preserve excess width of {flap['id']} for {unit['name']}")

    for feature in requirements["features"]:
        parent_name = feature["derive_from"]
        if parent_name is None:
            continue
        result = results_by_name[feature["name"]]
        parent = results_by_name[parent_name]
        if parent["missing"] == 0:
            result["derived"] = feature["count"]
            result["source_flap_ids"] = [flap["id"] for flap in parent["assigned"]]
            score -= DERIVE_PENALTY[feature["priority"]] * feature["count"]
            transformations.append(f"derive {feature['name']} locally from {parent_name}")
        else:
            result["missing"] = feature["count"]
            score -= PRIORITY_PENALTY[feature["priority"]] * feature["count"]

    for feature in requirements["features"]:
        if not feature["paired"]:
            continue
        result = results_by_name[feature["name"]]
        pair_counts: dict[str, int] = {}
        for flap in result["assigned"]:
            pair = flap.get("pair")
            if pair:
                pair_counts[pair] = pair_counts.get(pair, 0) + 1
        complete_pairs = sum(count // 2 for count in pair_counts.values()) + result["derived"] // 2
        missing_pairs = max(0, feature["count"] // 2 - complete_pairs)
        if missing_pairs:
            score -= 6.0 * missing_pairs
            transformations.append(f"create or realign {missing_pairs} paired group(s) for {feature['name']}")

    unmatched = []
    for feature in requirements["features"]:
        result = results_by_name[feature["name"]]
        if result["missing"]:
            unmatched.append({"name": feature["name"], "count": result["missing"], "priority": feature["priority"]})

    available_surfaces = int(base.get("broad_surfaces", 0))
    surface_results = []
    for surface in sorted(requirements["surfaces"], key=lambda item: -PRIORITY_WEIGHT[item["priority"]]):
        assigned = min(surface["count"], available_surfaces)
        available_surfaces -= assigned
        missing = surface["count"] - assigned
        if missing:
            score -= PRIORITY_PENALTY[surface["priority"]] * missing
            unmatched.append({"name": surface["name"], "count": missing, "priority": surface["priority"], "kind": "surface"})
        surface_results.append({"name": surface["name"], "requested": surface["count"], "assigned": assigned, "missing": missing})

    preferences = requirements["preferences"]
    preferred_symmetry = preferences.get("symmetry")
    if preferred_symmetry and preferred_symmetry not in base.get("symmetry", []):
        score -= 5.0
        transformations.append(f"adapt {base['id']} from its native symmetry to {preferred_symmetry}")
    preferred_volume = preferences.get("volume")
    if preferred_volume and preferred_volume not in base.get("volume_bias", []):
        score -= 3.0

    essential_blockers = [item for item in unmatched if item["priority"] == "essential"]
    return {
        "id": base["id"],
        "name": base["name"],
        "cp": str((catalog_path.parent / base["cp"]).resolve()),
        "score": round(score, 2),
        "matched_features": [results_by_name[feature["name"]] for feature in requirements["features"]],
        "surface_coverage": surface_results,
        **(map_reservations(base["_region_map"], results_by_name.values(), surface_results)
           if "_region_map" in base else {}),
        "remaining_flaps": [flap for index, flap in enumerate(flaps) if index not in used_flaps],
        "essential_blockers": essential_blockers,
        "unmatched": unmatched,
        "estimated_transformations": sorted(set(transformations)),
        "affordances": base.get("affordances", []),
        "tradeoffs": base.get("tradeoffs", []),
        "common_transformations": base.get("common_transformations", []),
        "validation": base.get("validation", {}),
    }


def build_result(requirements: dict[str, Any], catalog: list[dict[str, Any]], catalog_path: Path, top: int) -> dict[str, Any]:
    ranked = [rank_base(base, requirements, catalog_path) for base in catalog]
    ranked.sort(key=lambda item: (
        sum(blocker["count"] for blocker in item["essential_blockers"]),
        -item["score"],
        sum(conflict["area_fraction"] for conflict in item.get("region_conflicts", [])),
        item["id"],
    ))
    selected = ranked[:top]
    for index, item in enumerate(selected, start=1):
        item["rank"] = index
    return {
        "subject": requirements["subject"],
        "screening_only": True,
        "decision_rule": "Inspect the CP and named-feature mapping. Do not adopt a base solely from its score.",
        "surface_assumption": "Mapped candidates report positive overlap between reserved polygons in region_conflicts. With an unmapped catalog, review surface coverage manually.",
        "candidates": selected,
    }


def self_test() -> int:
    catalog_path = Path(__file__).resolve().parent.parent / "assets" / "bases" / "catalog.json"
    catalog = validate_catalog(load_json(catalog_path), catalog_path)
    cases = [
        ({
            "subject": "test quadruped",
            "features": [
                {"name": "legs", "count": 4, "length": "long", "priority": "essential", "paired": True},
                {"name": "head", "count": 1, "length": "medium", "priority": "essential"},
            ],
            "surfaces": [{"name": "body", "count": 1, "size": "broad", "priority": "essential"}],
            "preferences": {"symmetry": "bilateral", "volume": "3d"},
        }, "frog-base"),
        ({
            "subject": "test axial form",
            "features": [
                {"name": "ends", "count": 2, "length": "long", "priority": "essential", "paired": True},
                {"name": "side fins", "count": 2, "length": "medium", "priority": "essential"},
            ],
            "surfaces": [{"name": "body", "count": 1, "size": "broad", "priority": "essential"}],
            "preferences": {"symmetry": "diagonal", "volume": "flat"},
        }, "fish-base"),
        ({
            "subject": "test distributed details",
            "features": [
                {"name": "details", "count": 4, "length": "short", "priority": "essential", "paired": True}
            ],
            "surfaces": [{"name": "center", "count": 1, "size": "broad", "priority": "essential"}],
            "preferences": {"symmetry": "rotational", "volume": "flat"},
        }, "blintz-base"),
    ]
    for payload, expected in cases:
        result = build_result(validate_requirements(payload), catalog, catalog_path, 3)
        assert result["candidates"][0]["id"] == expected
        assert not result["candidates"][0]["essential_blockers"]
        assigned_ids = [
            flap["id"]
            for feature in result["candidates"][0]["matched_features"]
            for flap in feature["assigned"]
        ]
        assert len(assigned_ids) == len(set(assigned_ids))

    broad_tail = validate_requirements({
        "subject": "test broad tail",
        "features": [
            {"name": "tail", "count": 1, "length": "long", "width": "broad", "priority": "essential"}
        ],
        "surfaces": [],
        "preferences": {},
    })
    broad_tail_result = build_result(broad_tail, catalog, catalog_path, len(catalog))
    assert all(candidate["essential_blockers"] for candidate in broad_tail_result["candidates"])
    assert all(not candidate["matched_features"][0]["assigned"] for candidate in broad_tail_result["candidates"])

    local_split = validate_requirements({
        "subject": "test local split",
        "features": [
            {"name": "head", "count": 1, "length": "medium", "width": "broad", "priority": "essential"},
            {"name": "ears", "count": 2, "length": "short", "width": "medium", "priority": "supporting", "paired": True, "derive_from": "head"},
        ],
        "surfaces": [],
        "preferences": {"symmetry": "bilateral"},
    })
    bird = next(base for base in catalog if base["id"] == "bird-base")
    bird_result = rank_base(bird, local_split, catalog_path)
    ears = next(feature for feature in bird_result["matched_features"] if feature["name"] == "ears")
    assert ears["derived"] > 0 and ears["missing"] == 0
    assert ears["source_flap_ids"]

    invalid_split = {
        "subject": "test invalid split",
        "features": [
            {"name": "head", "count": 1, "length": "medium", "width": "medium", "priority": "essential"},
            {"name": "ears", "count": 2, "length": "short", "width": "medium", "priority": "supporting", "derive_from": "head"},
        ],
        "surfaces": [],
        "preferences": {},
    }
    try:
        validate_requirements(invalid_split)
    except ValueError:
        pass
    else:
        raise AssertionError("multi-part local splits must use narrower child features")
    print("rank_bases self-test passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, help="requirements JSON")
    parser.add_argument("--catalog", type=Path, default=Path(__file__).resolve().parent.parent / "assets" / "bases" / "catalog.json")
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if args.input is None:
        parser.error("input is required unless --self-test is used")
    if args.top < 1:
        parser.error("--top must be positive")

    try:
        requirements = validate_requirements(load_json(args.input))
        catalog = validate_catalog(load_json(args.catalog), args.catalog)
        result = build_result(requirements, catalog, args.catalog, args.top)
    except ValueError as error:
        parser.error(str(error))

    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
