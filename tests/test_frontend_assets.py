import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

from fastapi.testclient import TestClient

from dataguard.api import create_app


def test_editorial_assets_are_self_hosted_and_named_font_access_is_bounded(tmp_path):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'assets.db'}")) as client:
        html = client.get("/console/agent")
        assert html.status_code == 200
        assert "/ui-core.js" in html.text
        assert 'aria-controls="workspace-navigation"' in html.text
        assert "Skip to workspace" in html.text
        for asset in ["/console.css", "/dashboard.js", "/ui-core.js"]:
            response = client.get(asset)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
        for font in ["instrument-serif.woff2", "manrope.woff2"]:
            response = client.get("/fonts/" + font)
            assert response.status_code == 200
            assert response.content[:4] == b"wOF2"
            assert response.headers["content-type"].startswith("font/woff2")
        assert client.get("/fonts/api.py").status_code == 404
        assert client.get("/fonts/unknown.woff2").status_code == 404


def test_archive_routes_preload_one_hero_and_serve_distinct_safe_images(tmp_path):
    manifest = json.loads(
        (Path(__file__).parents[1] / "dataguard" / "archive-manifest.json").read_text("utf-8")
    )
    hashes = set()
    with TestClient(create_app(f"sqlite:///{tmp_path / 'archive.db'}")) as client:
        script = client.get("/archive.js")
        css = client.get("/archive.css")
        assert script.status_code == css.status_code == 200
        assert "IntersectionObserver" in script.text
        assert "prefers-reduced-motion: reduce" in css.text
        for entry in manifest:
            filename = entry["file"]
            assert filename in script.text
            result = client.get("/archive-art/" + filename)
            assert result.status_code == 200
            assert result.headers["content-type"].startswith("image/svg+xml")
            assert result.headers["cache-control"] == "public, max-age=86400"
            assert result.headers["x-content-type-options"] == "nosniff"
            assert result.headers["content-security-policy"].startswith("default-src 'self'")
            root = ElementTree.fromstring(result.content)  # noqa: S314 — local repository artwork
            assert root.tag == "{http://www.w3.org/2000/svg}svg"
            assert not any(
                item.tag.endswith(("}script", "}foreignObject", "}image"))
                or any(key.startswith("on") for key in item.attrib)
                for item in root.iter()
            )
            hashes.add(hashlib.sha256(result.content).digest())
            if entry["placement"] == "hero":
                page = client.get("/console/" + entry["route"])
                assert page.status_code == 200
                assert page.text.count('rel="preload" as="image"') == 1
                assert f'href="/archive-art/{filename}"' in page.text
        assert len(hashes) == len(manifest) >= 20
        assert client.get("/archive-art/archive.py").status_code == 404
        assert client.get("/console/unknown").status_code == 404
