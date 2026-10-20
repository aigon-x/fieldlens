"""Web layer: static shell, health probe and the JSON inspection contract."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from fieldlens.imageio import encode_png
from web.server import create_app

client = TestClient(create_app())


def test_index_serves_the_shell() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert '<meta name="viewport"' in resp.text
    assert 'id="dropzone"' in resp.text
    assert 'aria-live="polite"' in resp.text


def test_health_reports_the_engine() -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["engine"] == "opencv-matched-filter"


def test_inspect_returns_the_json_contract(scratch_sample) -> None:
    files = {"file": ("plate.png", encode_png(scratch_sample["image"]), "image/png")}
    resp = client.post("/api/inspect", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert {"defects", "count", "annotated_png_base64"} <= set(body)
    assert body["count"] == len(body["defects"])
    assert body["defects"], "a plate with one scratch must yield at least one box"
    first = body["defects"][0]
    assert set(first) == {"type", "score", "box"}
    assert first["type"] in ("scratch", "dent", "stain")
    assert len(first["box"]) == 4
    assert all(isinstance(v, int) for v in first["box"])
    png = base64.b64decode(body["annotated_png_base64"])
    assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_inspect_rejects_a_non_image_file() -> None:
    files = {"file": ("notes.txt", b"definitely not an image", "text/plain")}
    resp = client.post("/api/inspect", files=files)
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_inspect_requires_a_file_field() -> None:
    resp = client.post("/api/inspect", files={"note": (None, "x")})
    assert resp.status_code == 400
    assert "file" in resp.json()["detail"]
