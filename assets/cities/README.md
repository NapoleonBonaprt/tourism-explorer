# WanderClimate city images

The site now has **a local visual for all 41 supported destinations**. Images
are served from `assets/cities/` by the FastAPI static-files mount, so normal
page rendering does not depend on Unsplash or Pexels being available.

## Image format and naming

City names use lowercase, hyphen-separated slugs (for example,
`rio-de-janeiro.jpg`).

- **35 destinations:** locally stored JPEG photographs named `<city>.jpg`.
- **6 destinations:** original, city-specific SVG landmark illustrations named
  `<city>.svg`: **Cairo, Lisbon, Madrid, Paris, Rome, Tokyo**. These are
  **illustrations, not photographic representations**. They cover five formerly
  missing local photographs and the incorrect Madrid image.
- The former `madrid.jpg` was identical to `barcelona.jpg` and has been removed.
  Madrid now displays `madrid.svg` instead of a wrong-city photograph.
- Existing optional external photographic fallbacks remain available when
  configured, but the local image is always preferred.

The frontend selects the appropriate local extension in
`index.html` (`cityImageCandidates`). If a file fails to load, existing
remote fallbacks (where configured) or the built-in card illustration remain
available. The site must never show a broken-image icon in the city cards.

## Validate files after cloning or deploying

From the repository root:

```bash
python scripts/verify_city_assets.py
```

The script checks the presence of all 41 primary image files, validates SVG
syntax, checks JPEG start/end markers, and performs a full image integrity
check if Pillow is installed.

If a local photograph has been corrupted or was only partially downloaded,
remove the incomplete local copy and run `git restore assets/cities/<filename>`
from a complete clone or fetch a fresh copy from GitHub. Avoid copying
`*.jpg` files through a text editor.

## Replacing an illustration with a photograph

1. Add a properly licensed local JPEG named `<slug>.jpg` (web-optimized
   landscape format, preferably 1200px or wider and under 500KB when practical).
2. Remove that slug from `LOCAL_CITY_ILLUSTRATIONS` in `index.html`.
3. Verify, commit and push the image and HTML changes together.
4. Deploy with `git pull --ff-only origin main` and reload the website.

Keep attribution and licensing records for any third-party photographs.
