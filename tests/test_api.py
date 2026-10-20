"""HTTP API: all three input encodings, mask rendering and error paths."""

from __future__ import annotations

import base64

import cv2
from fastapi.testclient import TestClient

from fieldlens.api import create_app
from fieldlens.imageio import encode_png

client = TestClient(create_app())


def _png_bytes(sample) -> bytes:
    return encode_png(sample["image"])


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["engine"] == "opencv-matched-filter"


def test_inspect_raw_png(scratch_sample) -> None:
    resp = client.post("/inspect", content=_png_bytes(scratch_sample), headers={"Content-Type": "image/png"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["defect_count"] >= 1
    assert body["defects"][0]["kind"] in ("scratch", "dent", "stain")
    assert body["image_size"] == list(scratch_sample["image"].shape[1::-1])
    assert "elapsed_ms" in body


def test_inspect_json_base64_with_mask(stain_sample) -> None:
    payload = {
        "image_base64": base64.b64encode(_png_bytes(stain_sample)).decode("ascii"),
        "include_mask": True,
    }
    resp = client.post("/inspect", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["defect_count"] >= 1
    raw = base64.b64decode(body["mask_png_b64"])
    decoded = cv2.imdecode(__import__("numpy").frombuffer(raw, __import__("numpy").uint8), cv2.IMREAD_GRAYSCALE)
    assert decoded is not None and decoded.shape == stain_sample["image"].shape[:2]


def test_inspect_multipart(scratch_sample) -> None:
    files = {"file": ("plate.png", _png_bytes(scratch_sample), "image/png")}
    resp = client.post("/inspect", files=files, data={"include_mask": "true"})
    assert resp.status_code == 200
    assert resp.json()["defect_count"] >= 1


def test_inspect_rejects_garbage() -> None:
    resp = client.post("/inspect", content=b"not an image at all", headers={"Content-Type": "image/png"})
    assert resp.status_code == 400
    assert "detail" in resp.json()


def test_inspect_rejects_empty_body() -> None:
    resp = client.post("/inspect", content=b"", headers={"Content-Type": "image/png"})
    assert resp.status_code == 400


def test_inspect_json_without_image_field() -> None:
    resp = client.post("/inspect", json={"include_mask": True})
    assert resp.status_code == 400
