"""Web layer for FieldLens: single-page inspector over the existing CV pipeline."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from fieldlens import __version__
from fieldlens.annotate import annotate
from fieldlens.detect import DEFAULT_PARAMS, inspect_array
from fieldlens.imageio import ImageDecodeError, decode_image, encode_png
from fieldlens.quality import assess

WEB_DIR = Path(__file__).resolve().parent
INDEX_HTML = WEB_DIR / "index.html"
SAMPLES_DIR = WEB_DIR.parent / "samples" / "images"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024


def _sample_names() -> list[str]:
    if not SAMPLES_DIR.is_dir():
        return []
    return sorted(path.name for path in SAMPLES_DIR.glob("*.png") if path.is_file())


def create_app() -> FastAPI:
    app = FastAPI(title="FieldLens Web", version=__version__)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        if not INDEX_HTML.is_file():
            raise HTTPException(status_code=500, detail="index.html missing")
        return FileResponse(INDEX_HTML, media_type="text/html")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__, "engine": "opencv-matched-filter"}

    @app.post("/api/report")
    def report(file: UploadFile | None = File(default=None)) -> JSONResponse:
        """Downloadable inspection report: findings, input quality and run metadata."""
        if file is None:
            raise HTTPException(status_code=400, detail="multipart field 'file' is required")
        data = file.file.read()
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=400, detail="empty or oversized upload")
        try:
            image = decode_image(data)
        except ImageDecodeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        result = inspect_array(image, DEFAULT_PARAMS)
        quality = assess(image)
        payload = {
            "schema": "fieldlens.report/1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": {"filename": file.filename, "bytes": len(data)},
            "image_size": list(result.image_size),
            "elapsed_ms": round(float(result.elapsed_ms), 2),
            "input_quality": quality.as_dict(),
            "count": len(result.defects),
            "defects": [
                {"type": d.kind, "score": round(float(d.score), 3), "box": list(d.bbox)}
                for d in result.defects
            ],
        }
        headers = {"Content-Disposition": 'attachment; filename="fieldlens-report.json"'}
        return JSONResponse(payload, headers=headers)

    @app.get("/api/samples")
    def samples() -> dict:
        """Bundled plates, so a first visit has something to inspect."""
        return {"samples": _sample_names()}

    @app.get("/api/sample/{name}")
    def sample(name: str) -> FileResponse:
        # Membership in the directory listing, never a path built from the request.
        if name not in _sample_names():
            raise HTTPException(status_code=404, detail="unknown sample")
        return FileResponse(SAMPLES_DIR / name, media_type="image/png")

    @app.post("/api/inspect")
    def inspect(file: UploadFile | None = File(default=None)) -> JSONResponse:
        # Sync on purpose: decoding and the filter bank are CPU-bound (~100 ms per plate).
        # FastAPI runs a def endpoint in its threadpool, so a slow plate cannot freeze
        # /api/health or the next inspection; an async handler blocked the event loop.
        if file is None:
            raise HTTPException(status_code=400, detail="multipart field 'file' is required")
        data = file.file.read()
        if not data:
            raise HTTPException(status_code=400, detail="empty upload")
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="payload too large")
        try:
            image = decode_image(data)
        except ImageDecodeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        result = inspect_array(image, DEFAULT_PARAMS)
        annotated = encode_png(annotate(image, result))
        payload = {
            "defects": [
                {"type": d.kind, "score": round(float(d.score), 3), "box": list(d.bbox)}
                for d in result.defects
            ],
            "count": len(result.defects),
            "annotated_png_base64": base64.b64encode(annotated).decode("ascii"),
            "input_quality": assess(image).as_dict(),
            "image_size": list(result.image_size),
            "elapsed_ms": round(float(result.elapsed_ms), 2),
            "version": __version__,
        }
        return JSONResponse(payload)

    return app


app = create_app()
