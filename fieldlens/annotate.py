"""Annotation rendering: boxes + labels over the original image, mask overlay."""

from __future__ import annotations

import cv2
import numpy as np

from .types import InspectionResult

COLORS = {
    "scratch": (58, 58, 235),
    "dent": (0, 170, 255),
    "stain": (205, 90, 200),
}


def annotate(img: np.ndarray, result: InspectionResult, thickness: int = 2) -> np.ndarray:
    """Return a BGR copy of `img` with defect boxes, ids and scores drawn."""
    out = img.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    for d in result.defects:
        x, y, w, h = d.bbox
        color = COLORS.get(d.kind, (0, 255, 0))
        cv2.rectangle(out, (x, y), (x + w, y + h), color, thickness)
        label = f"{d.id}:{d.kind} z={d.score:.1f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        ty = y - 4 if y - th - 6 >= 0 else y + h + th + 4
        cv2.rectangle(out, (x, ty - th - 3), (x + tw + 4, ty + 2), color, -1)
        cv2.putText(out, label, (x + 2, ty - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (15, 15, 15), 1, cv2.LINE_AA)

    summary = f"defects={len(result.defects)} {result.elapsed_ms:.0f}ms"
    cv2.rectangle(out, (0, 0), (max(180, 9 * len(summary)), 22), (25, 25, 25), -1)
    cv2.putText(out, summary, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
    return out


def mask_overlay(img: np.ndarray, mask: np.ndarray | None) -> np.ndarray:
    """Red-tinted overlay of the binary defect mask on the source image."""
    if mask is None:
        return img.copy()
    base = img.copy()
    if base.ndim == 2:
        base = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    if mask.shape[:2] != base.shape[:2]:
        mask = cv2.resize(mask, (base.shape[1], base.shape[0]), interpolation=cv2.INTER_NEAREST)
    tint = np.zeros_like(base)
    tint[mask > 0] = (0, 0, 255)
    return cv2.addWeighted(base, 1.0, tint, 0.55, 0)
