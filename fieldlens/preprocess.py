"""Pre-processing: resize cap, denoise, CLAHE."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .imageio import to_gray


@dataclass(frozen=True)
class PrepResult:
    gray: np.ndarray  # uint8, working resolution
    enhanced: np.ndarray  # uint8, CLAHE on denoised gray
    scale: float  # working / original
    orig_size: tuple[int, int]  # (w, h)


def resize_to_max(gray: np.ndarray, max_dim: int) -> tuple[np.ndarray, float]:
    """Downscale so the longest side is <= max_dim. Returns (image, scale)."""
    h, w = gray.shape[:2]
    longest = max(h, w)
    if longest <= max_dim:
        return gray, 1.0
    scale = max_dim / float(longest)
    resized = cv2.resize(
        gray, (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def denoise(gray: np.ndarray) -> np.ndarray:
    """Median (salt/pepper) followed by an edge-preserving bilateral pass."""
    med = cv2.medianBlur(gray, 3)
    return cv2.bilateralFilter(med, d=5, sigmaColor=35.0, sigmaSpace=5.0)


def apply_clahe(gray: np.ndarray, clip_limit: float = 2.0, tiles: int = 8) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tiles, tiles))
    return clahe.apply(gray)


def preprocess(bgr: np.ndarray, max_dim: int = 768) -> PrepResult:
    gray = to_gray(bgr)
    h, w = gray.shape[:2]
    resized, scale = resize_to_max(gray, max_dim)
    clean = denoise(resized)
    enhanced = apply_clahe(clean)
    return PrepResult(gray=clean, enhanced=enhanced, scale=scale, orig_size=(w, h))


