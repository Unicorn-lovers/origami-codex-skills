"""Search privately installed source patterns and start an attributed working copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

from pattern_geometry import prepare_geometry


CATALOGS = ("catalog/archives.jsonl", "pdf-records.jsonl", "catalog/local.jsonl", "catalog/designs.jsonl")
# The imported archives also supply subject tags. These terms bridge Japanese briefs
# and titles that were deposited in English; exact titles and arbitrary words also work.
ALIASES = (
    ("cat", "cats", "kitten", "kittens", "ねこ", "ネコ", "猫", "仔猫", "子猫"),
    ("dog", "dogs", "puppy", "犬", "イヌ", "いぬ", "子犬"),
    ("rabbit", "bunny", "hare", "兎", "うさぎ", "ウサギ"), ("fox", "狐", "きつね", "キツネ"),
    ("bird", "birds", "鳥", "とり"), ("crane", "鶴", "ツル", "つる"),
    ("dragon", "ドラゴン", "竜", "龍"), ("horse", "horses", "equine", "馬", "ウマ"), ("wolf", "狼", "オオカミ"),
    ("fish", "魚", "さかな"), ("frog", "蛙", "カエル"), ("bat", "コウモリ", "蝙蝠"),
    ("butterfly", "蝶", "チョウ"), ("insect", "昆虫", "虫"), ("wing", "wings", "翼", "羽"),
    ("flower", "flowers", "花"), ("modular", "ユニット", "くす玉"), ("tessellation", "テセレーション"),
)


def normalized(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w]+|_", " ", text).split())


def contains(text, term):
    if re.search(r"[一-龯ぁ-ヿ]", term):
        return term in text
    return f" {term} " in f" {text} "


def registry():
    home = Path(os.environ.get("CODEX_HOME") or Path.home()/".codex")
    return home/"origami-pattern-library.json"


def library_path(explicit):
    value = explicit or os.environ.get("ORIGAMI_PATTERN_LIBRARY")
    if not value and registry().is_file():
        value = json.loads(registry().read_text(encoding="utf-8"))["library"]
    if not value:
        raise ValueError("no pattern library registered; use register DIRECTORY or --library DIRECTORY")
    return Path(value).expanduser().resolve(strict=True)


def records(root):
    seen = set()
    derivatives = {}
    for name in ("catalog/local.jsonl", "catalog/designs.jsonl"):
        src = root/name
        if src.is_file():
            for line in src.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    item = json.loads(line)
                    if item.get("parent_id") and item.get("cp_ready"):
                        derivatives.setdefault(item["parent_id"], []).append(item["id"])
    verified = {}
    for report in (root/"verified").glob("*/base-validation/report.json"):
        work = report.parent.parent
        try:
            manifest = json.loads((work/"source.json").read_text(encoding="utf-8"))
            run = json.loads(report.read_text(encoding="utf-8"))
            status = run["oriedita"]
            if (manifest["selected_file_sha256"] == work.name and run.get("success")
                    and status["calculation"]["violationCount"] == 0 and status["calculation"]["started"]
                    and status["completed"] and status["foldedModelReturned"]
                    and run["input_sha256"] == manifest["base_cp_sha256"] == digest(work/"base.cp")
                    and (report.parent/"folded-figure.png").is_file() and (report.parent/"folded-model.json").is_file()):
                verified[(manifest["id"], work.name)] = str(report.relative_to(root))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    for name in CATALOGS:
        path = root/name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item["id"] in seen:
                    raise ValueError(f"duplicate catalog ID {item['id']}")
                seen.add(item["id"])
                if item["id"] in derivatives:
                    item["derived_pattern_ids"] = derivatives[item["id"]]
                report = verified.get((item["id"], item.get("sha256")))
                if report:
                    item.update(validation_status="oriedita_flat_state_completed", validation_report=report)
                yield item
    if not seen:
        raise ValueError(f"no pattern records in {root}")


def origin(item):
    return item.get("source_type") or "archive"


def record_path(root, item):
    return (root / item["path"]).resolve()


def summary(root, item):
    fields = ("id", "title", "kind", "format", "subjects", "assignment_status",
              "geometry_status", "page", "page_end", "crop_box", "folding_sequence_id", "sequence_pages",
              "parent_id", "derived_pattern_ids", "validation_status", "validation_report")
    return {**{k: item[k] for k in fields if k in item}, "source": origin(item),
            "cp_ready": bool(item.get("cp_ready")), "path": str(record_path(root, item))}


def search(root, args):
    subject = normalized(args.subject)
    if not subject:
        raise ValueError("enter a subject or source ID")
    # A compound design can have an existing exact title or need a host model.
    host = re.sub(r"^(?:(?:winged|horned)\s+|(?:翼|羽根?|角|ツノ)(?:の|が)(?:生えた|ついた|付いた|ある))", "", subject)
    host = re.sub(r"(?:\s+with\s+(?:wings|horns)|に(?:翼|羽根?|角|ツノ)(?:を(?:つける|付ける|生やす))?)$", "", host).strip() or subject
    host = normalized(args.base) if args.base else host
    asks_for_wings = bool(re.search(r"\b(?:wings?|winged)\b|羽|翼", subject))
    aliases = next((tuple(normalized(x) for x in group) for group in ALIASES
                    if host in {normalized(x) for x in group}), (host,))
    aliases = set(aliases)
    page_index = Path(__file__).resolve().parents[1]/"assets/catalogs/illustrated-models.jsonl"
    for line in page_index.read_text(encoding="utf-8").splitlines():
        page = json.loads(line)
        names = {normalized(page[k]) for k in ("model", "title_en") if page.get(k)}
        if host in names:
            aliases.update(names)
    matches = []
    for item in records(root):
        if args.source and origin(item) != args.source:
            continue
        if args.ready and not item.get("cp_ready"):
            continue
        exact_id = item["id"].casefold() == args.subject.casefold()
        if not args.sequences and not exact_id and item.get("kind") == "folding_sequence":
            continue
        title = normalized(item["title"])
        tags = {normalized(s) for s in item.get("subjects", [])}
        title_match = any(contains(title, word) for word in aliases)
        tag_match = not tags.isdisjoint(aliases)
        exact_title = title == subject
        if not (exact_id or exact_title or tag_match or title_match):
            continue
        # A title can mention a cat's eye or a cat costume without representing a cat.
        # Keep qualified models discoverable by title while respecting explicit tags.
        if "cat" in aliases and item.get("subject_detail") and not (tag_match or exact_id or exact_title):
            continue
        named_variant = host != subject and (contains(title, subject) or
                        (asks_for_wings and tag_match and bool(tags & {"wing", "wings", "winged", "翼", "羽"})))
        score = (exact_id, named_variant, bool(item.get("cp_ready")), exact_title,
                 item.get("validation_status") == "oriedita_flat_state_completed",
                 title in aliases, tag_match, item.get("kind") != "folding_sequence",
                 item.get("format") == "cp", -item.get("segments", 0))
        matches.append((score, item))
    matches.sort(key=lambda pair: pair[1]["id"])
    matches.sort(key=lambda pair: pair[0], reverse=True)
    first = [summary(root, v) for _, v in matches[:args.limit]]
    result = {"subject": args.subject, "base_subject": host, "count": len(matches), "matches": first}
    if not args.ready and not args.source:
        visible = {v["id"] for v in first}
        books = [v for _, v in matches if origin(v) == "book" and v["id"] not in visible]
        if books:
            result["also_in_book"] = [summary(root, v) for v in books[:args.limit]]
    return result


def find_record(root, id_):
    for item in records(root):
        if item["id"].casefold() == id_.casefold():
            return item
    raise ValueError(f"unknown source ID {id_}")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def register(directory, jar=None):
    root = library_path(directory)
    count = sum(1 for _ in records(root))
    target = registry()
    target.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
    config["library"] = str(root)
    if jar:
        path = Path(jar).expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError("the Oriedita JAR must be a file")
        config["oriedita_jar"] = str(path)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as f:
        tmp = Path(f.name)
    try:
        write_json(tmp, config)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    return {"library": str(root), "records": count, "registration": str(target)}


def checkout(root, args):
    item = find_record(root, args.id)
    src = record_path(root, item)
    actual = digest(src)
    expected = item.get("sha256") or item.get("source_sha256")
    if expected and actual != expected.lower():
        raise ValueError(f"source hash mismatch for {item['id']}")
    out = Path(args.out_dir).resolve()
    if out.exists():
        raise ValueError(f"working directory already exists: {out}")
    ready = bool(item.get("cp_ready"))
    if args.validate_base and not ready:
        raise ValueError("inspect the reference or resolve the fold assignments before validating")
    manifest = {**item, "source_path": str(src), "selected_file_sha256": actual, "cp_ready": ready}
    manifest.setdefault("source_sha256", actual)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as temp:
        stage = Path(temp)/"work"
        stage.mkdir()
        if ready:
            data = src.read_bytes()
            if hashlib.sha256(data).hexdigest() != actual:
                raise ValueError("source changed during checkout")
            cp, flat = prepare_geometry(data, item["format"])
            (stage/"base.cp").write_bytes(cp)
            (stage/"candidate.cp").write_bytes(cp)
            manifest.update(base_cp_sha256=hashlib.sha256(cp).hexdigest(), omitted_flat_edges=flat)
        write_json(stage/"source.json", manifest)
        # Claim the destination without overwriting another concurrent checkout.
        out.mkdir()
        try:
            for artifact in stage.iterdir():
                artifact.rename(out/artifact.name)
        except OSError:
            shutil.rmtree(out)
            raise
    if args.validate_base:
        cmd = ["node", str(Path(__file__).with_name("validate_cp.mjs")), str(out/"base.cp"),
               "--out-dir", str(out/"base-validation"), "--isolated"]
        if args.jar:
            cmd.extend(["--jar", args.jar])
        subprocess.run(cmd, check=True, stdout=sys.stderr)
    return {"source": str(out/"source.json"), "base_cp": str(out/"base.cp") if ready else None,
            "candidate_cp": str(out/"candidate.cp") if ready else None,
            "reference": str(src), "page": item.get("page"), "page_end": item.get("page_end"),
            "crop_box": item.get("crop_box")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", help="override the registered private library")
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register")
    reg.add_argument("directory")
    reg.add_argument("--jar", help="remember a working Oriedita bridge JAR on this machine")
    s = sub.add_parser("search")
    s.add_argument("subject")
    s.add_argument("--base", help="underlying subject for a compound design")
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--ready", action="store_true", help="only source geometry that can be prepared as CP")
    s.add_argument("--source", choices=("archive", "book", "local"))
    s.add_argument("--sequences", action="store_true", help="also return step-by-step diagrams")
    sub.add_parser("show").add_argument("id")
    c = sub.add_parser("checkout")
    c.add_argument("id")
    c.add_argument("--out-dir", required=True)
    c.add_argument("--validate-base", action="store_true")
    c.add_argument("--jar")
    args = parser.parse_args()
    try:
        if args.command == "register":
            result = register(args.directory, args.jar)
        else:
            root = library_path(args.library)
            if args.command == "search":
                if args.limit < 1:
                    raise ValueError("--limit must be positive")
                result = search(root, args)
            elif args.command == "show":
                item = find_record(root, args.id)
                result = {**item, "resolved_path": str(record_path(root, item))}
            else:
                result = checkout(root, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (KeyError, TypeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"pattern library: {exc}\n")


if __name__ == "__main__":
    main()
