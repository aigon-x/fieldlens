"""Image decoding/encoding. Accepts paths, raw bytes and base64 payloads."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import cv2
import numpy as np


class ImageDecodeError(ValueError):
    """Raised when the payload is not a decodable image."""


def decode_image(data: bytes) -> np.ndarray:
    """Decode encoded image bytes (PNG/JPEG/BMP/TIFF) into a BGR uint8 array."""
    if not data:
        raise ImageDecodeError("empty payload")
    buf = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ImageDecodeError("unsupported or corrupted image payload")
    return img


def decode_base64(payload: str) -> np.ndarray:
    """Decode a base64 string, tolerating a `data:image/...;base64,` prefix."""
    if not isinstance(payload, str) or not payload.strip():
        raise ImageDecodeError("empty base64 payload")
    text = payload.strip()
    if text.startswith("data:"):
        _, _, text = text.partition(",")
    try:
        raw = base64.b64decode(text, validate=False)
    except Exception as exc:  # binascii.Error subclasses Exception
        raise ImageDecodeError(f"invalid base64 payload: {exc}") from exc
    return decode_image(raw)


def read_image(path: str | os.PathLike[str]) -> np.ndarray:
    """Read an image from disk. Raises ImageDecodeError with the path in the message."""
    p = Path(path)
    if not p.is_file():
        raise ImageDecodeError(f"not a file: {p}")
    return decode_image(p.read_bytes())


def encode_png(img: np.ndarray) -> bytes:
    """Encode a BGR/gray image as PNG bytes."""
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("PNG encoding failed")
    return buf.tobytes()


def encode_png_b64(img: np.ndarray) -> str:
    return base64.b64encode(encode_png(img)).decode("ascii")


def to_gray(img: np.ndarray) -> np.ndarray:
    """Convert BGR/BGRA/gray to a single-channel uint8 image."""
    if img.ndim == 2:
        return img
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    if img.ndim == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    raise ImageDecodeError(f"unsupported image shape: {img.shape}")
