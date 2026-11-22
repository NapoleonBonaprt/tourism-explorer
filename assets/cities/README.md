# WanderClimate city photos

The website supports **41 destinations**. Photo selection is implemented in
`cityImageCandidates()` in `index.html`.

- **36 destinations** use their original local JPEG files in
  `assets/cities/<city-slug>.jpg`. This includes **Madrid**, restored
  from Git history at the user's request.
- **Five destinations** use their original externally hosted photos:
  **Cairo, Lisbon, Paris, Rome and Tokyo**. Their Pexels/Unsplash URLs
  remain in `CITY_PHOTOS`. These require the external image providers
  to be reachable and may occasionally fail to load.
- The restored original `madrid.jpg` has the **same file contents as
  `barcelona.jpg`** in this repository. This is intentional to reproduce
  the previously used Madrid image exactly, not a corrected Madrid photo.

The six temporary SVG illustrations from the fallback experiment were
removed. The frontend uses the five original external photo sources and the
restored original Madrid JPEG.

## Validate local image integrity

From the project root:

```bash
python scripts/verify_city_assets.py
```

The script checks **36 local JPEGs** for basic completeness, optionally
performs full JPEG decoding with Pillow, and reports duplicate file content.
It lists the five remote-image cities separately and cannot validate their
external URLs without network access.

If a local image file is missing or truncated after deployment,
run `git pull --ff-only origin main` and then re-run the audit.
