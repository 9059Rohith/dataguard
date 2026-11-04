"""Capture the first 500 public Apache GitHub repositories by creation date."""

import argparse
import gzip
import hashlib
import io
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

from dataguard.quality import FIELDS, NoSourceRedirects, digest


def capture():
    opener = urllib.request.build_opener(NoSourceRedirects())
    endpoint = "https://api.github.com/orgs/apache/repos"
    started_at = datetime.now(UTC).isoformat()
    records, pages = [], []
    for page in range(1, 6):
        query = urlencode(
            dict(type="public", sort="created", direction="asc", per_page=100, page=page)
        )
        request = urllib.request.Request(
            f"{endpoint}?{query}",
            headers={
                "Accept": "application/vnd.github+json",
                "Accept-Encoding": "gzip",
                "User-Agent": "DataGuard-Benchmark",
            },
        )
        with opener.open(request, timeout=30) as response:
            raw = response.read(1_500_001)
            if len(raw) > 1_500_000:
                raise ValueError("GitHub response exceeds the page limit")
            observed_at = datetime.now(UTC).isoformat()
            encoding = response.headers.get("Content-Encoding")
            http_date = response.headers.get("Date")
        decoded = raw
        if encoding == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
                decoded = stream.read(1_500_001)
        if len(decoded) > 1_500_000:
            raise ValueError("Decoded GitHub response exceeds the page limit")
        rows = json.loads(decoded)
        if len(rows) != 100 or any(
            row.get("private") is not False
            or not row.get("full_name", "").lower().startswith("apache/")
            for row in rows
        ):
            raise ValueError(f"Unexpected source scope or row count on page {page}")
        normalized = [{field: row.get(field) for field in FIELDS} for row in rows]
        records.extend(normalized)
        pages.append(
            {
                "url": request.full_url,
                "observed_at": observed_at,
                "http_date": http_date,
                "content_encoding": encoding,
                "rows": len(rows),
                "response_bytes": len(raw),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "records_sha256": digest(normalized),
            }
        )
    if len({row["id"] for row in records}) != 500:
        raise ValueError("GitHub pagination returned overlapping repositories")
    return {
        "source": endpoint,
        "scope": "First 500 public Apache repositories returned in creation-date order",
        "collection_started_at": started_at,
        "captured_at": pages[-1]["observed_at"],
        "sha256": digest(records),
        "pages": pages,
        "records": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source = capture()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(source, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"Captured {len(source['records'])} distinct repositories: {source['sha256']}")
