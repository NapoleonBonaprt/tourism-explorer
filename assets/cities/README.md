# WanderClimate city photos

All 41 destinations have local JPEG photos in `assets/cities/<city-slug>.jpg`.

Cairo, Lisbon, Paris, Rome and Tokyo are cached copies of the original Pexels/Unsplash sources already configured in `index.html`. The website tries the local photo first, then the original remote URL. PDF covers use the local image and crop it to 900 x 560; illustrated covers are used only when a valid local image is missing, or for Madrid.

Madrid's existing JPEG is intentionally retained to preserve the prior website appearance, although its bytes match Barcelona's image. The PDF uses a Madrid-specific illustration instead to avoid misidentifying Barcelona as Madrid.

To refresh the five cached photos with their original sources, run:

```bash
python scripts/cache_original_city_photos.py
python scripts/verify_city_assets.py
```

The download script validates the decoded image and limits its dimensions; the audit checks all 41 JPEGs and reports duplicate content. Sources and fallback URLs are recorded in the script. Internet access is needed only to refresh the cached files, not to generate the PDF.
