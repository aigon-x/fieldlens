"""Image IO: encodings, base64 variants and explicit failures."""

from __future__ import annotations

import base64

import cv2
import numpy as np
import pytest

from fieldlens.imageio import (
    ImageDecodeError,
    decode_base64,
    decode_image,
    encode_png,
    encode_png_b64,
    read_image,
    to_gray,
)


def test_png_round_trip() -> None:
    img = np.zeros((32, 48, 3), dtype=np.uint8)
    img[:, :, 1] = 200
    decoded = decode_image(encode_png(img))
    assert decoded.shape == img.shape
    assert np.array_equal(decoded, img)


def test_base64_accepts_data_url() -> None:
    img = np.full((16, 16, 3), 77, dtype=np.uint8)
    b64 = encode_png_b64(img)
    assert np.array_equal(decode_base64(f"data:image/png;base64,{b64}"), img)
    assert np.array_equal(decode_base64(b64), img)


def test_empty_payload_raises() -> None:
    with pytest.raises(ImageDecodeError):
        decode_image(b"")
    with pytest.raises(ImageDecodeError):
        decode_base64("")


def test_garbage_payload_raises() -> None:
    with pytest.raises(ImageDecodeError):
        decode_image(b"\x00\x01\x02 definitely not an image")


def test_missing_file_raises(tmp_path) -> None:
    with pytest.raises(ImageDecodeError):
        read_image(tmp_path / "absent.png")


def test_to_gray_handles_bgra_and_gray() -> None:
    bgra = np.zeros((10, 10, 4), dtype=np.uint8)
    assert to_gray(bgra).shape == (10, 10)
    gray = np.zeros((10, 10), dtype=np.uint8)
    assert to_gray(gray).shape == (10, 10)
    with pytest.raises(ImageDecodeError):
        to_gray(np.zeros((10, 10, 7), dtype=np.uint8))


def test_read_image_round_trip(tmp_path) -> None:
    img = np.full((12, 20, 3), 33, dtype=np.uint8)
    path = tmp_path / "x.png"
    path.write_bytes(encode_png(img))
    read = read_image(path)
    assert read.shape == img.shape
    assert np.array_equal(read, img)


def test_jpeg_is_decodable() -> None:
    img = np.full((24, 24, 3), 120, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    assert decode_image(buf.tobytes()).shape == (24, 24, 3)
