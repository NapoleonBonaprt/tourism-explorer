#!/usr/bin/env python3
"""Cache the five original remote city photographs as compact local JPEGs."""
from pathlib import Path
from io import BytesIO
import base64
import hashlib
import os
import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1] / "assets" / "cities"
SOURCES = {
    "cairo": ["https://images.unsplash.com/photo-1572252009286-268acec5ca0a?q=80&w=1400&auto=format&fit=crop"],
    "lisbon": ["https://images.pexels.com/photos/16338753/pexels-photo-16338753.jpeg?auto=compress&cs=tinysrgb&w=1400",
               "https://images.pexels.com/photos/28961818/pexels-photo-28961818.jpeg?auto=compress&cs=tinysrgb&w=1400",
               "https://images.pexels.com/photos/9253/sea-city-landscape-sky.jpg?auto=compress&cs=tinysrgb&w=1400"],
    "paris": ["https://images.unsplash.com/photo-1502602898657-3e91760cbb34?q=80&w=1400&auto=format&fit=crop"],
    "rome": ["https://images.unsplash.com/photo-1552832230-c0197dd311b5?q=80&w=1400&auto=format&fit=crop"],
    "tokyo": ["https://images.unsplash.com/photo-1503899036084-c55cdd92da26?q=80&w=1400&auto=format&fit=crop"],
}

def main():
    failures = []
    for city, urls in SOURCES.items():
        for url in urls:
            try:
                r = requests.get(url, timeout=(8, 25), headers={"User-Agent":"Mozilla/5.0"}, stream=True)
                r.raise_for_status()
                data = bytearray()
                for chunk in r.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 15_000_000:
                        raise ValueError("Image exceeds 15 MB")
                with Image.open(BytesIO(data)) as src:
                    im = ImageOps.exif_transpose(src).convert("RGB")
                    if min(im.size) < 300:
                        raise ValueError("Image too small")
                    im.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                    out = BytesIO()
                    im.save(out, "JPEG", quality=84, optimize=True)
                blob = out.getvalue()
                with Image.open(BytesIO(blob)) as verify:
                    verify.load()
                target = ROOT / (city + ".jpg")
                target.write_bytes(blob)
                print(f"PHOTO_OK {city} {im.size} {len(blob)} {hashlib.sha256(blob).hexdigest()} {url}", flush=True)
                if os.getenv("PHOTO_TRANSFER_LOG") == "1":
                    encoded = base64.b64encode(blob).decode("ascii")
                    for i in range(0, len(encoded), 3072):
                        print(f"PHOTO_CHUNK {city} {i//3072:04d} {encoded[i:i+3072]}", flush=True)
                break
            except Exception as exc:
                print(f"PHOTO_RETRY {city}: {type(exc).__name__}: {exc}", flush=True)
        else:
            failures.append(city)
    if failures:
        raise SystemExit("Unable to retrieve: " + ", ".join(failures))

if __name__ == "__main__":
    main()
