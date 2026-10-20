"""AWS Lambda entry point: image in -> defect JSON out.

Supports two event shapes:

* API Gateway HTTP API / REST proxy (`event["body"]`, optional `isBase64Encoded`),
* direct invocation `{"image_base64": "..."}` or `{"image_b64": "..."}`.

S3 object input is intentionally *not* implemented here: it would need boto3, which is
not part of this package. Such an event returns 501 with an explicit message instead of
pretending to succeed.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from fieldlens import __version__
from fieldlens.annotate import annotate
from fieldlens.detect import DEFAULT_PARAMS, Params, inspect_array
from fieldlens.imageio import ImageDecodeError, decode_base64, decode_image, encode_png

HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "X-FieldLens-Version": __version__,
}


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {"statusCode": status, "headers": HEADERS, "body": json.dumps(payload)}


def inspect_bytes(data: bytes, include_mask: bool = False, max_dim: int | None = None) -> dict[str, Any]:
    img = decode_image(data)
    params = Params(**{**DEFAULT_PARAMS.__dict__, "max_dim": int(max_dim)}) if max_dim else DEFAULT_PARAMS
    result = inspect_array(img, params)
    payload = result.to_dict()
    payload["version"] = __version__
    payload["engine"] = "opencv-matched-filter"
    if include_mask and result.mask is not None:
        payload["mask_png_b64"] = base64.b64encode(encode_png(result.mask)).decode("ascii")
        payload["annotated_png_b64"] = base64.b64encode(encode_png(annotate(img, result))).decode("ascii")
    return payload


def handler(event: dict, context: Any = None) -> dict[str, Any]:  # noqa: ARG001 - Lambda contract
    if not isinstance(event, dict):
        return _response(400, {"error": "event must be an object"})

    # S3 notification shape -> explicit refusal, no silent stub.
    if "Records" in event or "s3" in event:
        return _response(
            501,
            {
                "error": "S3 input is not implemented in this Lambda package",
                "hint": "POST the image bytes (base64) or add a boto3 fetch step before calling fieldlens",
            },
        )

    query = event.get("queryStringParameters") or {}
    include_mask = str(query.get("include_mask", event.get("include_mask", ""))).lower() in ("1", "true", "yes")
    max_dim = query.get("max_dim", event.get("max_dim"))

    try:
        if "body" in event:
            body = event["body"]
            if body is None:
                return _response(400, {"error": "empty body"})
            if isinstance(body, str) and event.get("isBase64Encoded"):
                data = base64.b64decode(body)
            elif isinstance(body, str):
                # raw JSON payload from a direct invoke, otherwise treat as base64 image
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    b64 = parsed.get("image_base64") or parsed.get("image")
                    if not b64:
                        return _response(400, {"error": "JSON body requires image_base64"})
                    data = base64.b64decode(b64)
                    include_mask = include_mask or str(parsed.get("include_mask", "")).lower() in ("1", "true")
                    max_dim = parsed.get("max_dim", max_dim)
                else:
                    data = base64.b64decode(body)
            else:
                return _response(400, {"error": "unsupported body type"})
        else:
            b64 = event.get("image_base64") or event.get("image_b64")
            if not b64:
                return _response(400, {"error": "provide 'body' (API Gateway) or 'image_base64'"})
            data = base64.b64decode(b64)

        payload = inspect_bytes(data, include_mask=include_mask, max_dim=max_dim)
    except ImageDecodeError as exc:
        return _response(400, {"error": str(exc)})
    except (ValueError, TypeError, base64.binascii.Error) as exc:
        return _response(400, {"error": f"invalid payload: {exc}"})

    return _response(200, payload)


# Convenience for local runs: `python3 lambda_handler.py image.png`
if __name__ == "__main__":  # pragma: no cover
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 lambda_handler.py <image>")
    evt = {"body": base64.b64encode(Path(sys.argv[1]).read_bytes()).decode("ascii"), "isBase64Encoded": False}
    out = handler(evt)
    print(json.dumps(json.loads(out["body"]), indent=2))
