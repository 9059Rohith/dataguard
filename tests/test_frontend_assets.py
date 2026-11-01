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
