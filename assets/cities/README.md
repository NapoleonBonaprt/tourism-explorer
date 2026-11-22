# WanderClimate city images

The site supports 41 destinations. Images are selected by
`cityImageCandidates()` in `index.html`.

- **35 destinations** use locally stored JPEG photos, named
  `assets/cities/<city-slug>.jpg`.
- **Five destinations** use their **original externally hosted photographs**,
  as requested: Cairo, Lisbon, Paris, Rome and Tokyo. Their original
  Pexels/Unsplash links remain in `CITY_PHOTOS` within `index.html`.
  These images need an internet connection; they may fail if the external
  provider is unavailable. The site has a built-in illustrated fallback
  for failed destination-card images.
- **Madrid** uses its local `madrid.svg` landmark illustration because
  the previous `madrid.jpg` was an accidental duplicate of Barcelona.

The original five photos were restored after the temporary local SVG
illustrations were removed. No new photographs have been invented or
substituted for those five images.

## Verify the local images

From the repository root, run:

```bash
python scripts/verify_city_assets.py
```

This checks all **36 locally served visuals** for missing files, basic JPEG
completeness, SVG correctness and duplicates. If Pillow is installed,
it also verifies full JPEG decoding. The script lists the five remote-only
destinations separately; it does not test live third-party image URLs.

To replace a remote image with a properly licensed local photograph in the
future, commit it to `assets/cities/<slug>.jpg` and update
`cityImageCandidates()` in `index.html`.
