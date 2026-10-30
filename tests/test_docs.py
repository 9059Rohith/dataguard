import base64
import hashlib
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from dataguard.api import create_app


class ScriptParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inline = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "script" and "src" not in dict(attrs):
            self.current = ""

    def handle_data(self, data):
        if self.current is not None:
            self.current += data

    def handle_endtag(self, tag):
        if tag == "script" and self.current is not None:
            self.inline.append(self.current)
            self.current = None


@pytest.mark.parametrize(
    "path,asset_scope",
    [
        ("/docs", "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/"),
        ("/redoc", "https://cdn.jsdelivr.net/npm/redoc@2/"),
        ("/docs/oauth2-redirect", None),
    ],
)
def test_documentation_csp_authorizes_only_its_bootstrap_and_required_assets(
    tmp_path, path, asset_scope
):
    with TestClient(create_app(f"sqlite:///{tmp_path / 'docs.db'}")) as client:
        response = client.get(path)
        assert response.status_code == 200
        csp = response.headers["content-security-policy"]
        script_policy = next(
            part for part in csp.split(";") if part.strip().startswith("script-src")
        )
        parser = ScriptParser()
        parser.feed(response.text)
        for script in parser.inline:
            digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
            assert f"'sha256-{digest}'" in script_policy
        assert "'unsafe-inline'" not in script_policy
        assert "'unsafe-eval'" not in script_policy
        if asset_scope:
            assert asset_scope in script_policy
        else:
            assert "https:" not in script_policy
        for ordinary_path in ("/", "/health", "/docs/not-a-route"):
            ordinary = client.get(ordinary_path).headers["content-security-policy"]
            assert "script-src 'self';" in ordinary
            assert "cdn.jsdelivr.net" not in ordinary
            assert "'sha256-" not in ordinary
