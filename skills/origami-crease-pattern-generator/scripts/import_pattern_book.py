"""Attach a local copy of the indexed illustrated book to a private pattern library."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from pattern_library import digest

BOOK_SHA256 = "3a20fc69d71d9222f2149b588ed890ca65e6f5af3d96998442df55b3963409b1"
INDEX = Path(__file__).resolve().parents[1]/"assets/catalogs/illustrated-models.jsonl"


def attach(src, root):
    if digest(src) != BOOK_SHA256:
        raise ValueError("this PDF differs from the indexed edition; its page and crop coordinates require review")
    books = root/"books"
    books.mkdir(parents=True, exist_ok=True)
    # Content-stable filename keeps repeated imports and moves of the library usable.
    dest = books/"origami_prince_sugowaza_origami_hq.pdf"
    if dest.exists():
        if digest(dest) != BOOK_SHA256:
            raise ValueError(f"existing book is different: {dest}")
    else:
        with tempfile.NamedTemporaryFile(dir=books, delete=False) as f:
            tmp = Path(f.name)
        try:
            shutil.copyfile(src, tmp)
            if digest(tmp) != BOOK_SHA256:
                raise ValueError("source PDF changed while copying")
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
    entries = []
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        row.update(format="pdf", path=str(dest.relative_to(root)), source_sha256=BOOK_SHA256,
                   source_type="book", cp_ready=False, original_path=str(src.resolve()))
        entries.append(row)
    index = root/"pdf-records.jsonl"
    new_by_id = {r["id"]: r for r in entries}
    combined = []
    if index.exists():
        for line in index.read_text(encoding="utf-8-sig").splitlines():
            row = json.loads(line)
            new = new_by_id.pop(row["id"], None)
            if new:
                if row.get("source_sha256") != BOOK_SHA256:
                    raise ValueError(f"book index ID already exists: {row['id']}")
                row.update(new)
            combined.append(row)
    combined.extend(new_by_id.values())
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, delete=False) as out:
        tmp = Path(out.name)
        for row in combined:
            out.write(json.dumps(row, ensure_ascii=False)+"\n")
    try:
        os.replace(tmp, index)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"Registered {len(entries)} page references in {index}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    try:
        attach(args.pdf.expanduser(), args.library.expanduser().resolve())
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"book import: {exc}\n")
