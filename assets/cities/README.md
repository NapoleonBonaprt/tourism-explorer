# WanderClimate city photos

All 41 destinations have local JPEG photos in `assets/cities/<city-slug>.jpg`.

Cairo, Lisbon, Paris, Rome and Tokyo are cached copies of the original Pexels/Unsplash sources already configured in `index.html`. The website tries the local photo first, then the original remote URL. PDF covers use the local image and crop it to 900 x 560; illustrated covers are used only for other destinations when a valid local image is missing. Cairo, Lisbon, Paris, Rome, Tokyo, Madrid and Barcelona require a photo; a failed photo load is reported rather than silently exporting an illustration.

Madrid's existing JPEG is intentionally retained to preserve the prior website appearance, although its bytes match Barcelona's image. Both PDF covers intentionally use the same current photograph; it is not a verified photograph of Madrid and should eventually be replaced.

To refresh the five cached photos with their original sources, run:

```bash
python scripts/cache_original_city_photos.py
python scripts/verify_city_assets.py
```

The download script validates the decoded image and limits its dimensions; the audit checks all 41 JPEGs and reports duplicate content. Sources and fallback URLs are recorded in the script. No third-party image download is required to generate a PDF; the local files must be accessible to the browser or server.
