"""Core data types shared by detection, benchmarking and serving."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

KINDS = ("scratch", "dent", "stain")


@dataclass
class Defect:
    """One detected defect region. Bounding boxes are `(x, y, w, h)` pixels."""

    id: int
    kind: str
    bbox: tuple[int, int, int, int]
    area_px: int
    score: float
    elongation: float
    contrast: float

    @property
    def centroid(self) -> tuple[float, float]:
        x, y, w, h = self.bbox
        return (x + w / 2.0, y + h / 2.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "bbox": list(self.bbox),
            "area_px": int(self.area_px),
            "score": round(float(self.score), 3),
            "elongation": round(float(self.elongation), 3),
            "contrast": round(float(self.contrast), 2),
            "centroid": [round(c, 2) for c in self.centroid],
        }


@dataclass
class InspectionResult:
    """Result of a single inspection. `mask` is uint8 (0/255), not serialised by default."""

    defects: list[Defect]
    image_size: tuple[int, int]  # (width, height) of the input image
    scale: float  # working image / input image
    elapsed_ms: float
    mask: np.ndarray | None = field(default=None, repr=False)

    @property
    def counts(self) -> dict[str, int]:
        out = {k: 0 for k in KINDS}
        for d in self.defects:
            out[d.kind] = out.get(d.kind, 0) + 1
        out["total"] = len(self.defects)
        return out

    def to_dict(self, include_mask_png_b64: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "defect_count": len(self.defects),
            "counts": self.counts,
            "defects": [d.to_dict() for d in self.defects],
            "image_size": list(self.image_size),
            "working_scale": round(float(self.scale), 4),
            "elapsed_ms": round(float(self.elapsed_ms), 2),
        }
        if include_mask_png_b64 is not None:
            payload["mask_png_b64"] = include_mask_png_b64
        return payload
