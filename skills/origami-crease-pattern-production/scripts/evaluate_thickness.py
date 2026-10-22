#!/usr/bin/env python3
"""Calculate an auditable positive-thickness budget from layer counts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def finite_number(value: Any, path: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{path} must be a finite number")
    number = float(value)
    if positive and number <= 0:
        raise ValueError(f"{path} must be greater than zero")
    if nonnegative and number < 0:
        raise ValueError(f"{path} must be nonnegative")
    return number


def integer(value: Any, path: str, *, positive: bool = False) -> int:
    number = finite_number(value, path, positive=positive, nonnegative=not positive)
    if not number.is_integer():
        raise ValueError(f"{path} must be an integer")
    return int(number)


def optional_number(document: dict[str, Any], key: str, path: str, **checks: bool) -> float | None:
    value = document.get(key)
    return None if value is None else finite_number(value, f"{path}.{key}", **checks)


def comparison(value: float, operator: str, limit: float | None) -> dict[str, Any] | None:
    if limit is None:
        return None
    passed = value <= limit if operator == "max" else value >= limit
    return {"operator": operator, "limit": limit, "value": value, "passed": passed}


def record_status(checks: list[dict[str, Any]]) -> str:
    if any(not check["passed"] for check in checks):
        return "fail"
    if checks:
        return "pass"
    return "unassessed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.input.expanduser().resolve()
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("input root must be an object")

    paper = document.get("paper")
    if not isinstance(paper, dict):
        raise ValueError("paper must be an object")

    if paper.get("thickness_mm") is not None:
        nominal = finite_number(paper["thickness_mm"], "paper.thickness_mm", positive=True)
        thickness_source = "measured_or_supplied_caliper"
    else:
        gsm = finite_number(paper.get("gsm"), "paper.gsm", positive=True)
        density = finite_number(paper.get("density_g_cm3"), "paper.density_g_cm3", positive=True)
        nominal = gsm / (1000.0 * density)
        thickness_source = "estimated_from_gsm_and_density"

    factor = finite_number(
        paper.get("effective_thickness_factor", 1.0),
        "paper.effective_thickness_factor",
        positive=True,
    )
    effective = nominal * factor

    sheet_size = paper.get("sheet_size_mm")
    normalized_thickness = None
    if sheet_size is not None:
        if not isinstance(sheet_size, list) or len(sheet_size) != 2:
            raise ValueError("paper.sheet_size_mm must contain [width, height]")
        width = finite_number(sheet_size[0], "paper.sheet_size_mm[0]", positive=True)
        height = finite_number(sheet_size[1], "paper.sheet_size_mm[1]", positive=True)
        normalized_thickness = effective / min(width, height)

    limits = document.get("limits", {})
    if not isinstance(limits, dict):
        raise ValueError("limits must be an object")
    max_stack = optional_number(limits, "max_stack_mm", "limits", positive=True)
    max_ratio = optional_number(limits, "max_stack_to_feature_ratio", "limits", positive=True)
    min_gap = optional_number(limits, "min_gap_margin_mm", "limits")
    min_clearance = optional_number(limits, "min_clearance_margin_mm", "limits")

    regions = document.get("regions", [])
    if not isinstance(regions, list):
        raise ValueError("regions must be an array")
    region_results = []
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            raise ValueError(f"regions[{index}] must be an object")
        path = f"regions[{index}]"
        layers = integer(region.get("layers"), f"{path}.layers", positive=True)
        stack = layers * effective
        feature_width = optional_number(region, "feature_width_mm", path, positive=True)
        available_gap = optional_number(region, "available_gap_mm", path, nonnegative=True)
        ratio = stack / feature_width if feature_width is not None else None
        gap_margin = available_gap - stack if available_gap is not None else None
        checks = [check for check in (
            comparison(stack, "max", max_stack),
            comparison(ratio, "max", max_ratio) if ratio is not None else None,
            comparison(gap_margin, "min", min_gap) if gap_margin is not None else None,
        ) if check is not None]
        region_results.append({
            "id": str(region.get("id", index)),
            "step": region.get("step"),
            "layers": layers,
            "stack_thickness_mm": stack,
            "feature_width_mm": feature_width,
            "stack_to_feature_ratio": ratio,
            "available_gap_mm": available_gap,
            "gap_margin_mm": gap_margin,
            "checks": checks,
            "status": record_status(checks),
        })

    creases = document.get("creases", [])
    if not isinstance(creases, list):
        raise ValueError("creases must be an array")
    crease_results = []
    for index, crease in enumerate(creases):
        if not isinstance(crease, dict):
            raise ValueError(f"creases[{index}] must be an object")
        path = f"creases[{index}]"
        wrap_layers = integer(crease.get("wrap_layers"), f"{path}.wrap_layers")
        required = wrap_layers * effective
        available = optional_number(crease, "available_clearance_mm", path, nonnegative=True)
        margin = available - required if available is not None else None
        checks = [check for check in (
            comparison(margin, "min", min_clearance) if margin is not None else None,
        ) if check is not None]
        crease_results.append({
            "id": str(crease.get("id", index)),
            "step": crease.get("step"),
            "wrap_layers": wrap_layers,
            "required_clearance_mm": required,
            "available_clearance_mm": available,
            "clearance_margin_mm": margin,
            "checks": checks,
            "status": record_status(checks),
        })

    all_records = region_results + crease_results
    failed = [record["id"] for record in all_records if record["status"] == "fail"]
    assessed = [record["id"] for record in all_records if record["status"] in ("pass", "fail")]
    if failed:
        overall = "fail"
    elif assessed:
        overall = "pass"
    else:
        overall = "insufficient_evidence"

    report = {
        "source": str(source),
        "scope": "Screening budget from paper caliper and adopted layer counts; not a physical folding proof",
        "paper": {
            "nominal_thickness_mm": nominal,
            "thickness_source": thickness_source,
            "thickness_basis": paper.get("thickness_basis"),
            "effective_thickness_factor": factor,
            "effective_thickness_mm": effective,
            "sheet_size_mm": sheet_size,
            "normalized_thickness_to_short_side": normalized_thickness,
        },
        "limits": {
            "max_stack_mm": max_stack,
            "max_stack_to_feature_ratio": max_ratio,
            "min_gap_margin_mm": min_gap,
            "min_clearance_margin_mm": min_clearance,
        },
        "regions": region_results,
        "creases": crease_results,
        "summary": {
            "status": overall,
            "assessed_count": len(assessed),
            "unassessed_count": len(all_records) - len(assessed),
            "failed_ids": failed,
            "max_stack_thickness_mm": max((r["stack_thickness_mm"] for r in region_results), default=None),
            "max_required_clearance_mm": max((r["required_clearance_mm"] for r in crease_results), default=None),
        },
    }

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), **report["summary"]}, ensure_ascii=False))
    return 0 if overall != "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())
