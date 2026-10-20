"""Lambda handler: API Gateway and direct-invoke shapes, plus explicit refusals."""

from __future__ import annotations

import base64
import json

from fieldlens.imageio import encode_png
from lambda_handler import handler


def test_api_gateway_base64_body(scratch_sample) -> None:
    event = {
        "body": base64.b64encode(encode_png(scratch_sample["image"])).decode("ascii"),
        "isBase64Encoded": True,
        "queryStringParameters": {"include_mask": "true"},
    }
    resp = handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["defect_count"] >= 1
    assert "mask_png_b64" in body


def test_direct_invoke_payload(dent_sample) -> None:
    event = {"image_base64": base64.b64encode(encode_png(dent_sample["image"])).decode("ascii")}
    resp = handler(event, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["defect_count"] >= 1


def test_invalid_body_returns_400() -> None:
    resp = handler({"body": "aGVsbG8=", "isBase64Encoded": False}, None)
    assert resp["statusCode"] == 400
    assert "error" in json.loads(resp["body"])


def test_missing_payload_returns_400() -> None:
    resp = handler({"foo": "bar"}, None)
    assert resp["statusCode"] == 400


def test_s3_event_returns_explicit_501() -> None:
    """No silent success for an unimplemented input path."""
    resp = handler({"Records": [{"s3": {"bucket": {"name": "b"}}}]}, None)
    assert resp["statusCode"] == 501
    assert "not implemented" in json.loads(resp["body"])["error"].lower()
