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


def test_s3_event_without_boto3_returns_501(monkeypatch) -> None:
    """No silent success when the runtime cannot read S3."""

    def missing():
        raise ModuleNotFoundError("No module named 'boto3'")

    monkeypatch.setattr("lambda_handler._s3_client", missing)
    event = {"Records": [{"s3": {"bucket": {"name": "b"}, "object": {"key": "plates/x.png"}}}]}
    resp = handler(event, None)
    assert resp["statusCode"] == 501
    assert "boto3" in json.loads(resp["body"])["error"]


def test_s3_event_reads_object_with_stubbed_client(monkeypatch, dent_sample) -> None:
    data = encode_png(dent_sample["image"])

    class _Body:
        def read(self) -> bytes:
            return data

    class _S3:
        def get_object(self, Bucket: str, Key: str) -> dict:
            assert (Bucket, Key) == ("plates", "dir/a+b.png")
            return {"Body": _Body()}

    monkeypatch.setattr("lambda_handler._s3_client", lambda: _S3())
    event = {"Records": [{"s3": {"bucket": {"name": "plates"}, "object": {"key": "dir/a%2Bb.png"}}}]}
    resp = handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["defect_count"] >= 1
    assert body["source"] == {"bucket": "plates", "key": "dir/a+b.png"}


def test_s3_event_without_key_returns_400() -> None:
    resp = handler({"Records": [{"s3": {"bucket": {"name": "b"}}}]}, None)
    assert resp["statusCode"] == 400
