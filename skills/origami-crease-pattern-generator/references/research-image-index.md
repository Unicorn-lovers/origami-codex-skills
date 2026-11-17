# Research image indexing

Use this reference when primary-source research produces enough images that inspecting every original separately would dominate context or tool calls.

Organize images under one directory per article or source item, then run:

```bash
python3 scripts/make_contact_sheet.py downloaded-images \
  --output research/contact-sheet.svg \
  --index-dir research/image-index
```

The script uses only the Python standard library. It hashes images, identifies exact duplicates, records dimensions when the format exposes them, creates one JSON file per source directory, and produces a labeled SVG contact sheet with embedded images. Inspect the contact sheet and JSON first. Open an original image only when it is relevant to a design decision or unreadable at thumbnail scale.

This is an inspection aid, not permission to redistribute source images. Exclude downloaded images from the delivered skill or model package unless licensing clearly permits inclusion.
