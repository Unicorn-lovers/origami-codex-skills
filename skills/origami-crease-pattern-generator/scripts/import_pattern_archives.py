#!/usr/bin/env python3
"""Import a split, indexed crease-pattern archive into a personal pattern library."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import unicodedata
import zipfile

from pattern_geometry import prepare_geometry


def safe_path(name):
    parts = name.rstrip("/").split("/")
    if (not all(parts) or any(p in (".", "..") for p in parts)
            or "\\" in name or ":" in name or "\0" in name):
        raise ValueError(f"Unsafe archive path: {name!r}")
    return PurePosixPath(*parts)


def file_hash(path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def members(archives):
    files = {}
    for archive in archives:
        for info in archive.infolist():
            name = str(safe_path(info.filename))
            mode = stat.S_IFMT(info.external_attr >> 16)
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError(f"Unsupported archive member: {name}")
            if info.is_dir():
                continue
            if name in files:
                raise ValueError(f"Duplicate archive member: {name}")
            files[name] = (archive, info)
    return files


def read_member(files, name):
    archive, info = files[name]
    return archive.read(info)


def check_manifest(files):
    if "index.jsonl" not in files:
        raise ValueError("Expected an index.jsonl at the root of one archive part")
    entries = [json.loads(line) for line in read_member(files, "index.jsonl").splitlines() if line.strip()]
    expected = {}
    ids = set()
    for entry in entries:
        name = str(safe_path(entry["archive_path"]))
        digest = entry["sha256"].lower()
        if not re.fullmatch(r"[a-f0-9]{64}", digest) or name in expected or entry["id"] in ids:
            raise ValueError(f"Invalid or repeated index entry: {name}")
        if not name.startswith("patterns/") or not entry.get("title") or not entry["id"]:
            raise ValueError(f"Incomplete pattern record: {name}")
        ids.add(entry["id"])
        expected[name] = digest
    actual = {n for n in files if n.startswith("patterns/")}
    if not entries or actual != set(expected):
        raise ValueError(f"Archive parts and index disagree ({len(set(expected)-actual)} missing, {len(actual-set(expected))} unindexed patterns)")
    if "SHA256SUMS.txt" in files:
        sums = {}
        for line in read_member(files, "SHA256SUMS.txt").decode("utf-8-sig").splitlines():
            if not line.strip():
                continue
            digest, name = line.split(None, 1)
            name = str(safe_path(name.lstrip("*")))
            if not re.fullmatch(r"[a-f0-9]{64}", digest) or name in sums:
                raise ValueError(f"Invalid checksum entry: {name}")
            sums[name] = digest
        if any(sums.get(n) != d for n, d in expected.items()) or not sums.keys() <= files.keys():
            raise ValueError("The supplied SHA256SUMS and archive contents disagree")
        expected.update(sums)
    return entries, expected


def install_member(root, name, archive, info, expected_hash):
    path = root / name
    if path.resolve() != path or path.is_symlink():
        raise ValueError(f"Import destination contains a symbolic link: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if expected_hash and path.exists():
        if file_hash(path) != expected_hash:
            raise ValueError(f"Existing file differs from its index: {path}")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
        tmp = Path(target.name)
    try:
        digest = hashlib.sha256()
        with archive.open(info) as source, tmp.open("wb") as out:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
                out.write(chunk)
        hexdigest = digest.hexdigest()
        if expected_hash and hexdigest != expected_hash:
            raise ValueError(f"Checksum mismatch: {name}")
        try:
            os.link(tmp, path)
        except FileExistsError:
            if file_hash(path) != hexdigest:
                raise ValueError(f"Refusing to replace different source material: {path}")
    finally:
        tmp.unlink(missing_ok=True)


# Tags describe the title only. Original titles remain searchable for every subject.
TAGS = {
    "cat": r"\b(?:cats?|kittens?|neko|pussycat|gatos?|chats?|koty|koshka)\b|猫|ねこ|ネコ|(?<!\w)кош(?:ка|ки)|кот(?:ёнок|енок)\b",
    "dog": r"\b(?:dogs?|puppy|puppies|hounds?|perros?|canine|poodle|terrier|retriever|dalmatian)\b|犬|いぬ|イヌ",
    "fox": r"\b(?:fox|foxes|vulpes|kitsune|fennec)\b|狐|きつね|キツネ",
    "bird": r"\b(?:birds?|ravens?|crows?|sparrows?|herons?|eagles?|falcons?|hawks?|owls?|swans?|cranes?|pigeons?|ducks?|geese|goose|vultures?|robins?|warblers?|swallows?)\b|鳥|とり|トリ|鶴|鷲|鷹|フクロウ",
    "dragon": r"\bdragons?\b|龍|竜|ドラゴン",
    "wing": r"\b(?:wings?|winged)\b|翼|羽根|有翼",
    "bat": r"\bbats?\b|コウモリ|蝙蝠",
    "butterfly": r"\b(?:butterfly|butterflies|moths?)\b|蝶|チョウ",
    "fish": r"\b(?:fish|fishes|catfish|angelfish|sharks?|koi|goldfish|tuna|carps?|trout)\b|魚|鮫|サメ",
    "insect": r"\b(?:insects?|beetles?|ants?|bees?|wasps?|mantis|mantises|dragonfl(?:y|ies))\b|昆虫|カブトムシ|クワガタ",
    "equine": r"\b(?:horses?|pony|ponies|pegasus|unicorns?|zebras?)\b|馬|ペガサス|ユニコーン",
    "flower": r"\b(?:flowers?|roses?|lilies|lily|orchids?|tulips?|lotus)\b|花|薔薇|バラ",
    "tessellation": r"\btessell?ations?\b|テセレーション|敷き詰め",
    "modular": r"\b(?:units?|modular|kusudama|sonobe)\b|ユニット|くす玉",
}


def title_terms(title):
    text = unicodedata.normalize("NFKC", title).casefold().replace("_", " ")
    tags = {key for key, pattern in TAGS.items() if re.search(pattern, text)}
    subject_detail = None
    if "cat" in tags:
        for detail, pattern in (
            ("pattern", r"tessell?ation|checkerboard|cat.?s eye|cat.o..lantern"),
            ("character", r"cat\s*(girl|boy|robot)|cat\s*bus|neko bus|gear set|猫バス"),
            ("ear", r"neko mimi|cat ears?|猫耳"),
            ("part", r"\b(?:paw pads|whiskers?|tail)\b|肉球"),
            ("object", r"\bbox\b|置物風の箱"),
            ("head", r"\b(face|head|mask)\b|顔|お面"),
        ):
            if re.search(pattern, text):
                subject_detail = detail
                tags.discard("cat")
                tags.add("cat_" + detail)
                break
    return sorted(tags), subject_detail


def inspect_geometry(path, fmt):
    if fmt not in {"cp", "fold"}:
        return {"cp_ready": False, "assignment_status": "review" if fmt in {"opx", "svg"} else "not_encoded"}
    try:
        prepared, flat = prepare_geometry(path.read_bytes(), fmt)
    except (ValueError, KeyError, TypeError) as exc:
        return {"cp_ready": False, "assignment_status": "review", "geometry_note": str(exc)}
    segments = sum(bool(line.split()) and not line.lstrip().startswith(b"#") for line in prepared.splitlines())
    return {"cp_ready": True, "assignment_status": "assigned", "segments": segments + flat, "flat_edges": flat}


def catalog_record(entry, root):
    fmt = entry["format"].lower()
    path = Path("archives") / entry["archive_path"]
    category = "editable" if fmt in {"cp", "fold"} else "convertible" if fmt == "opx" else "reference"
    tags, detail = title_terms(entry["title"])
    row = {key: entry[key] for key in (
        "id", "title", "format", "sha256", "source_page", "source_url", "asset_url", "author",
        "license", "license_note", "model_key", "variant", "geometry_assignment_hash",
        "pixel_hash", "collection", "bytes",
    ) if entry.get(key) not in (None, "")}
    row.update(path=path.as_posix(), kind=category, subjects=tags, foldability_verified=False)
    row.update(inspect_geometry(root / path, fmt))
    if entry.get("assignment_review_required"):
        row.update(cp_ready=False, assignment_status="review")
    if entry.get("is_partial") or "partial" in str(entry.get("variant", "")).lower():
        row["partial"] = True
    if detail:
        row["subject_detail"] = detail
    return row


def import_archives(library, filenames):
    root = Path(library).expanduser().resolve()
    with contextlib.ExitStack() as stack:
        archives = [stack.enter_context(zipfile.ZipFile(p)) for p in filenames]
        files = members(archives)
        entries, checksums = check_manifest(files)
        for name, (archive, info) in files.items():
            install_member(root / "archives", name, archive, info, checksums.get(name))

    dest = root / "catalog"
    if dest.resolve() != dest:
        raise ValueError(f"Catalog destination contains a symbolic link: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest, delete=False, mode="w", encoding="utf-8") as out:
        staging = Path(out.name)
        try:
            for entry in entries:
                print(json.dumps(catalog_record(entry, root), ensure_ascii=False), file=out)
        except BaseException:
            out.close()
            staging.unlink(missing_ok=True)
            raise
    try:
        os.replace(staging, dest / "archives.jsonl")
    finally:
        staging.unlink(missing_ok=True)
    return len(entries), len(checksums), dest / "archives.jsonl"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", required=True, type=Path, help="Private library directory")
    parser.add_argument("archives", nargs="+", type=Path, help="All ZIP parts in any order")
    args = parser.parse_args()
    try:
        count, _, path = import_archives(args.library, args.archives)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(f"{count} indexed pattern files: {path}")


if __name__ == "__main__":
    main()
