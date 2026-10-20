"""Web layer: static shell, health probe and the JSON inspection contract."""

from __future__ import annotations

import base64
import re

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
    assert 'id="sampleBtn"' in resp.text


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


def test_samples_endpoint_lists_bundled_plates() -> None:
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    samples = resp.json()["samples"]
    assert samples, "the repository ships sample plates"
    assert all(name.endswith(".png") for name in samples)


def test_sample_endpoint_serves_a_real_png() -> None:
    name = client.get("/api/samples").json()["samples"][0]
    resp = client.get(f"/api/sample/{name}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_sample_endpoint_refuses_anything_outside_the_directory() -> None:
    """The name is matched against the listing, never joined into a path."""
    for name in ("..%2F..%2FREADME.md", "missing.png", "%2E%2E%2Fserver.py"):
        assert client.get(f"/api/sample/{name}").status_code == 404


HEX6 = re.compile(r"#([0-9a-fA-F]{6})")


def _root_tokens(html: str) -> dict[str, str]:
    root = re.search(r":root\{(.*?)\}", html, re.S)
    assert root, "the :root token block is missing"
    return {f"--{name}": value.strip() for name, value in
            re.findall(r"--([a-z0-9-]+)\s*:\s*([^;]+);", root.group(1))}


def _rule(html: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", html)
    assert match, f"CSS rule {selector} is missing"
    return match.group(1)


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    parsed = HEX6.fullmatch(color)
    assert parsed, f"expected a six-digit hex colour, got {color!r}"
    digits = parsed.group(1)
    r, g, b = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast(foreground: str, background: str) -> float:
    hi, lo = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_secondary_text_meets_wcag_aa_on_every_surface() -> None:
    """Faint text is 11-12.5 px, so SC 1.4.3 requires 4.5:1 on each surface it lands on."""
    html = client.get("/").text
    tokens = _root_tokens(html)
    for surface in ("--bg", "--panel", "--panel-2", "--panel-3"):
        ratio = _contrast(tokens["--faint"], tokens[surface])
        assert ratio >= 4.5, f"--faint on {surface} is {ratio:.2f}:1, below 4.5:1"


def test_white_labels_sit_on_the_darker_accent() -> None:
    """White on --accent is 3.81:1; every white-labelled surface must use --accent-ink."""
    html = client.get("/").text
    tokens = _root_tokens(html)
    for token in ("--accent-ink", "--accent-ink-hover"):
        ratio = _contrast("#ffffff", tokens[token])
        assert ratio >= 4.5, f"white on {token} is {ratio:.2f}:1, below 4.5:1"
    for selector, token in ((".skip-link", "--accent-ink"), (".btn-accent", "--accent-ink"),
                            (".btn-accent:hover", "--accent-ink-hover")):
        assert f"var({token})" in _rule(html, selector), f"{selector} lost {token}"
