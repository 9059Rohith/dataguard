"""Static field journal artwork and route-local preload metadata."""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

DIRECTORY = Path(__file__).parent
MANIFEST = json.loads((DIRECTORY / "archive-manifest.json").read_text(encoding="utf-8"))
ART_FILES = frozenset(plate["file"] for plate in MANIFEST)
HEROES = {plate["route"]: plate["file"] for plate in MANIFEST if plate["placement"] == "hero"}
BROWSER_ASSETS = frozenset(
    {
        "/console.css",
        "/archive.css",
        "/dashboard.js",
        "/archive.js",
        "/impact.js",
        "/ui-core.js",
        "/fonts/instrument-serif.woff2",
        "/fonts/manrope.woff2",
    }
)
CATALOG = json.dumps(
    [{key: plate[key] for key in ("file", "route", "placement")} for plate in MANIFEST],
    separators=(",", ":"),
)
router = APIRouter(include_in_schema=False)


def preload(page):
    return (
        f'<link rel="preload" as="image" href="/archive-art/{HEROES[page]}" fetchpriority="high" />'
    )


def cacheable_art(path):
    return path.startswith("/archive-art/") and path.removeprefix("/archive-art/") in ART_FILES


def is_browser_asset(path):
    return path in BROWSER_ASSETS or cacheable_art(path)


@router.get("/archive-art/{filename}")
def artwork(filename: str):
    if filename not in ART_FILES:
        raise HTTPException(404, "Field journal artwork not found")
    return FileResponse(DIRECTORY / "archive-art" / filename, media_type="image/svg+xml")


@router.get("/archive.css")
def stylesheet():
    return FileResponse(DIRECTORY / "archive.css", media_type="text/css")


@router.get("/archive.js")
def choreography():
    script = (DIRECTORY / "archive.js").read_text(encoding="utf-8")
    return Response(
        f"globalThis.DataGuardArchiveCatalog={CATALOG};\n{script}", media_type="text/javascript"
    )
