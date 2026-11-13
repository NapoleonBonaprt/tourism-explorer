"""Public WanderClimate application for Render.

Serve a strict set of frontend files, city artwork and the original FastAPI
endpoints on a single HTTPS origin. Never expose the project's CSV/Notebook
or Python source files through the static server.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import app as analytics_app

ROOT = Path(__file__).resolve().parent

PUBLIC_FILES = (
    "index.html",
    "overview.html",
    "climate.html",
    "explorer.html",
    "planner.html",
    "adaptive.html",
    "dashboard-site.css",
    "dashboard-site.js",
    "theme.js",
    "trip-pdf.js",
)

app = FastAPI(
    title="WanderClimate Website",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/", include_in_schema=False)
async def homepage():
    return FileResponse(ROOT / "index.html")


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok", "service": "wanderclimate"}


def register_static_file(filename: str) -> None:
    async def static_endpoint():
        return FileResponse(ROOT / filename)

    app.add_api_route("/" + filename, static_endpoint, methods=["GET"], include_in_schema=False)


for _name in PUBLIC_FILES:
    register_static_file(_name)

# This exposes only city images, the logo and their README, not sensitive data.
app.mount("/assets", StaticFiles(directory=str(ROOT / "assets")), name="assets")

# Keep /docs, /cities, /climate/search and /website/* unchanged.
app.mount("/", analytics_app)
