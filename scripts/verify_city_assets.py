#!/usr/bin/env python3
"""Check city image completeness and detect truncated local photos.

Run from any directory:
    python scripts/verify_city_assets.py

No dependency required for SVG and JPEG marker checks.
Install Pillow for full JPEG decoding/integrity verification.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CITY_DIR = ROOT / "assets" / "cities"

CITY_SLUGS = (
    "alexandria", "amman", "amsterdam", "aswan", "athens", "bangkok",
    "barcelona", "beijing", "berlin", "budapest", "buenos-aires",
    "cairo", "cape-town", "dubai", "florence", "istanbul",
    "kuala-lumpur", "kyoto", "lisbon", "london", "los-angeles",
    "luxor", "madrid", "marrakesh", "mexico-city", "munich",
    "new-york", "paris", "prague", "rio-de-janeiro", "riyadh",
    "rome", "san-francisco", "seoul", "shanghai", "singapore",
    "sydney", "tokyo", "toronto", "venice", "vienna",
)
# All original photos are now cached in the repository.
REMOTE_PHOTO_SLUGS = set()
ILLUSTRATED_SLUGS = set()  # All locally selected visuals use original JPEGs.


def main() -> int:
    try:
        from PIL import Image, ImageFile
    except ImportError:
        Image = None
    failures: list[str] = []
    seen: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []

    for slug in CITY_SLUGS:
        if slug in REMOTE_PHOTO_SLUGS:
            print(f"REMOTE  {slug} (original external photographic source)")
            continue
        ext = "svg" if slug in ILLUSTRATED_SLUGS else "jpg"
        name = f"{slug}.{ext}"
        path = CITY_DIR / name
        if not path.is_file():
            failures.append(f"MISSING  {name}")
            continue
        data = path.read_bytes()
        if len(data) < 100:
            failures.append(f"TOO SMALL  {name}")
            continue
        if ext == "svg":
            try:
                root = ET.fromstring(data)
                if not root.tag.endswith("svg") or not root.attrib.get("viewBox"):
                    raise ValueError("Missing SVG root or viewBox")
            except (ET.ParseError, ValueError) as exc:
                failures.append(f"INVALID SVG  {name}: {exc}")
                continue
        else:
            if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                failures.append(f"TRUNCATED JPEG  {name}: missing JPEG markers")
                continue
            if Image is not None:
                try:
                    with Image.open(path) as im:
                        im.verify()
                    with Image.open(path) as im:
                        im.load()
                        if im.width < 200 or im.height < 150:
                            raise ValueError(f"unexpected dimensions {im.size}")
                except Exception as exc:
                    failures.append(f"INVALID JPEG  {name}: {exc}")
                    continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in seen:
            duplicates.append((seen[digest], name))
        else:
            seen[digest] = name
        print(f"OK      {name} ({len(data):,} bytes)")

    for a, b in duplicates:
        print(f"WARNING duplicate image bytes: {a} and {b}")
    if Image is None:
        print("NOTE: Install Pillow for full JPEG decoding checks.")

    if failures:
        print(f"\nFAILED: {len(failures)} incomplete or invalid city images")
        for issue in failures:
            print(issue)
        return 1

    print(f"\nPASS: {len(CITY_SLUGS) - len(REMOTE_PHOTO_SLUGS)} local visuals verified; {len(REMOTE_PHOTO_SLUGS)} original remote photographic sources configured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
