"""FastAPI service: POST /inspect accepts raw image bytes, JSON base64 or multipart."""

from __future__ import annotations

import base64
import json
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import __version__
from .agent import inspect_adaptive, summarize
from .annotate import annotate
from .detect import DEFAULT_PARAMS, Params, inspect_array
from .imageio import ImageDecodeError, decode_base64, decode_image, encode_png

MAX_UPLOAD_BYTES = 12 * 1024 * 1024


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _params(options: dict) -> Params:
    max_dim = options.get("max_dim")
    if not max_dim:
        return DEFAULT_PARAMS
    try:
        return Params(**{**DEFAULT_PARAMS.__dict__, "max_dim": int(max_dim)})
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid max_dim: {exc}") from exc


async def _load(request: Request) -> tuple[np.ndarray, dict]:
    """Decode the request into (image, options). Raises HTTPException(400/413) on bad input."""
    ctype = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    if not body:
        raise HTTPException(status_code=400, detail="empty body")

    try:
        if ctype == "application/json":
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="JSON body must be an object")
            options = {
                "include_mask": _truthy(payload.get("include_mask", False)),
                "include_annotated": _truthy(payload.get("include_annotated", False)),
                "max_dim": payload.get("max_dim"),
            }
            b64 = payload.get("image_base64") or payload.get("image")
            if not isinstance(b64, str) or not b64:
                raise HTTPException(status_code=400, detail="JSON body requires 'image_base64'")
            return decode_base64(b64), options

        if ctype.startswith("multipart/"):
            form = await request.form()
            upload = form.get("file") or form.get("image")
            if upload is None or not hasattr(upload, "read"):
                raise HTTPException(status_code=400, detail="multipart body requires a 'file' field")
            data = await upload.read()
            options = {
                "include_mask": _truthy(form.get("include_mask", "")),
                "include_annotated": _truthy(form.get("include_annotated", "")),
                "max_dim": form.get("max_dim"),
            }
            return decode_image(data), options

        options = {
            "include_mask": _truthy(request.query_params.get("include_mask", "")),
            "include_annotated": _truthy(request.query_params.get("include_annotated", "")),
            "max_dim": request.query_params.get("max_dim"),
        }
        return decode_image(body), options
    except ImageDecodeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc


def create_app() -> FastAPI:
    app = FastAPI(title="FieldLens", version=__version__, description="Classical-CV surface defect inspection")

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "engine": "opencv-matched-filter",
            "defaults": {"max_dim": DEFAULT_PARAMS.max_dim, "line_angles": DEFAULT_PARAMS.line_angles},
        }

    @app.post("/inspect")
    async def inspect(request: Request) -> JSONResponse:
        img, options = await _load(request)
        result = inspect_array(img, _params(options))
        payload = result.to_dict()
        payload["engine"] = "opencv-matched-filter"
        payload["version"] = __version__
        if options.get("include_mask") and result.mask is not None:
            payload["mask_png_b64"] = base64.b64encode(encode_png(result.mask)).decode("ascii")
        if options.get("include_annotated"):
            payload["annotated_png_b64"] = base64.b64encode(encode_png(annotate(img, result))).decode("ascii")
        return JSONResponse(payload)

    @app.post("/agent/inspect")
    async def agent_inspect(request: Request) -> JSONResponse:
        """Active-perception loop: inspect -> decide -> tune -> re-inspect, with a decision log."""
        img, options = await _load(request)
        result, decisions, outcome = inspect_adaptive(img, _params(options))
        payload = result.to_dict()
        payload["engine"] = "opencv-matched-filter + active-perception"
        payload["version"] = __version__
        payload["agent"] = {"outcome": outcome, "decisions": decisions,
                            "summary": summarize(decisions, outcome)}
        if options.get("include_annotated"):
            payload["annotated_png_b64"] = base64.b64encode(encode_png(annotate(img, result))).decode("ascii")
        return JSONResponse(payload)

    return app


app = create_app()
