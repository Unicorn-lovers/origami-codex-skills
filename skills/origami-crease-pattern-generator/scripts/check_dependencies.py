#!/usr/bin/env python3
"""Check fixed runtime dependencies without downloading or searching source trees."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


def resolve_command(command: str) -> str | None:
    candidate = Path(command).expanduser()
    if candidate.is_absolute() or len(candidate.parts) > 1:
        return str(candidate.resolve()) if candidate.exists() else None
    return shutil.which(command)


def find_oriedita_jar(explicit: Path | None) -> tuple[str | None, str]:
    candidates: list[tuple[Path, str]] = []
    if explicit:
        candidates.append((explicit.expanduser(), "--jar"))
    environment = os.environ.get("ORIEDITA_JAR")
    if environment:
        candidates.append((Path(environment).expanduser(), "ORIEDITA_JAR"))

    home = Path.home()
    fixed_roots = [
        home / "Documents/oriedita/oriedita/target",
        home / "Library/Mobile Documents/com~apple~CloudDocs/Documents/oriedita/oriedita/target",
    ]
    for root in fixed_roots:
        if root.is_dir():
            for jar in sorted(root.glob("oriedita-*.jar"), reverse=True):
                if not jar.name.startswith("original-"):
                    candidates.append((jar, "known install location"))

    for candidate, source in candidates:
        if candidate.is_file():
            return str(candidate.resolve()), source
    return None, "not found in --jar, ORIEDITA_JAR, or known install locations"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="validator configuration used by validate_candidates.mjs")
    parser.add_argument("--jar", type=Path, help="explicit Oriedita JAR")
    parser.add_argument(
        "--require",
        action="append",
        default=[],
        choices=["python3", "node", "java", "oriedita"],
        help="return nonzero when this dependency is missing; repeat as needed",
    )
    args = parser.parse_args()

    checks: dict[str, dict[str, object]] = {}
    for name in ("python3", "node", "java"):
        resolved = shutil.which(name)
        checks[name] = {"available": resolved is not None, "path": resolved}

    jar, jar_source = find_oriedita_jar(args.jar)
    checks["oriedita"] = {"available": jar is not None, "jar": jar, "source": jar_source}

    config_errors: list[str] = []
    validator_commands: list[dict[str, object]] = []
    if args.config:
        try:
            config_path = args.config.expanduser().resolve()
            document = json.loads(config_path.read_text(encoding="utf-8"))
            validators = document.get("validators")
            if not isinstance(validators, list):
                raise ValueError("validators must be an array")
            for validator in validators:
                if not isinstance(validator, dict) or not isinstance(validator.get("command"), list) or not validator["command"]:
                    raise ValueError("every validator requires a command array")
                identifier = str(validator.get("id", "unknown"))
                executable = str(validator["command"][0])
                placeholders = {
                    "{skill_dir}": str(Path(__file__).resolve().parent.parent),
                    "{config_dir}": str(config_path.parent),
                }
                for key, value in placeholders.items():
                    executable = executable.replace(key, value)
                if "{" in executable:
                    resolved = None
                    note = "executable contains a runtime placeholder"
                else:
                    resolved = resolve_command(executable)
                    note = None
                missing_static_paths = []
                for raw_argument in validator["command"][1:]:
                    argument = str(raw_argument)
                    for key, value in placeholders.items():
                        argument = argument.replace(key, value)
                    if any(dynamic in argument for dynamic in ("{input}", "{output_dir}", "{candidate_id}")):
                        continue
                    argument_path = Path(argument).expanduser()
                    if argument_path.is_absolute() and not argument_path.exists():
                        missing_static_paths.append(str(argument_path))
                validator_commands.append({
                    "id": identifier,
                    "executable": executable,
                    "available": resolved is not None and not missing_static_paths,
                    "resolved": resolved,
                    "missing_static_paths": missing_static_paths,
                    "note": note,
                })
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            config_errors.append(str(exc))

    missing_required = [name for name in args.require if not checks[name]["available"]]
    missing_validator_commands = [
        str(record["id"]) for record in validator_commands if not record["available"]
    ]
    report = {
        "success": not missing_required and not missing_validator_commands and not config_errors,
        "checks": checks,
        "validator_commands": validator_commands,
        "config_errors": config_errors,
        "missing_required": missing_required,
        "missing_validator_commands": missing_validator_commands,
        "scope": "Fixed dependency resolution only; no downloads or source-tree search were performed.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
