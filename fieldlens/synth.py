"""Deterministic synthetic inspection dataset: clean plates + drawn defects + ground truth.

The generator is the evaluation backbone: every image comes with pixel-accurate
ground truth measured from the *drawn mask*, not from the draw parameters, so the
benchmark cannot be gamed by geometry shortcuts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

KIND_SCRATCH = "scratch"
KIND_DENT = "dent"
KIND_STAIN = "stain"


@dataclass(frozen=True)
class SynthConfig:
    size: int = 384
    clean_prob: float = 0.15
    max_attempts: int = 24
    seed: int = 0


def _background(rng: np.random.Generator, size: int) -> np.ndarray:
    """Metal/plastic-like plate: illumination gradient, vignetting, texture."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    theta = rng.uniform(0.0, 2.0 * np.pi)
    ramp = (np.cos(theta) * xx + np.sin(theta) * yy) / size
    ramp = ramp - ramp.mean()
    illum = 1.0 + rng.uniform(0.05, 0.16) * ramp

    c = (size - 1) / 2.0
    rr = ((xx - c) ** 2 + (yy - c) ** 2) / (c * c + c * c)
    illum = illum * (1.0 - rng.uniform(0.04, 0.15) * rr)

    level = rng.uniform(85.0, 170.0)
    base = level * illum

    style = ("brushed", "speckled", "cast")[int(rng.integers(0, 3))]
    raw = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)
    if style == "brushed":
        tex = cv2.blur(raw, (25, 1))  # horizontal streaks
        tex_amp = rng.uniform(1.4, 3.2)
    elif style == "speckled":
        tex = cv2.GaussianBlur(raw, (0, 0), 1.0) + 0.6 * cv2.GaussianBlur(raw, (0, 0), 6.0)
        tex_amp = rng.uniform(2.0, 4.2)
    else:  # cast: coarse waviness
        tex = cv2.GaussianBlur(raw, (0, 0), 8.0)
        tex_amp = rng.uniform(2.0, 4.0)
    tex = tex / (float(tex.std()) + 1e-6)
    return base + tex * tex_amp


def _mask_bbox(mask: np.ndarray, threshold: float = 0.06) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask > threshold)
    if xs.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return (x0, y0, max(1, x1 - x0 + 1), max(1, y1 - y0 + 1))


def _draw_scratch(rng: np.random.Generator, size: int) -> tuple[np.ndarray, float, float]:
    """Return (alpha mask in 0..1, signed contrast delta, elongation hint)."""
    length = rng.uniform(45.0, 150.0)
    angle = rng.uniform(0.0, np.pi)
    cx = rng.uniform(0.18, 0.82) * size
    cy = rng.uniform(0.18, 0.82) * size
    n_seg = int(rng.integers(1, 4))
    pts = [(cx, cy)]
    for i in range(n_seg):
        step = length / n_seg
        angle += rng.uniform(-0.18, 0.18)
        cx += np.cos(angle) * step
        cy += np.sin(angle) * step
        pts.append((cx, cy))
    width = rng.uniform(1.0, 2.6)

    ss = 2  # supersample for anti-aliased sub-pixel width
    big = np.zeros((size * ss, size * ss), np.uint8)
    poly = np.array([[(int(round(x * ss)), int(round(y * ss))) for x, y in pts]], np.int32)
    thick = max(1, int(round(width * ss)))
    cv2.polylines(big, poly, False, 255, thickness=thick, lineType=cv2.LINE_AA)
    alpha = cv2.resize(big, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.45)

    delta = rng.uniform(16.0, 34.0)
    return alpha, float(delta), 0.0


def _draw_dent(rng: np.random.Generator, size: int) -> tuple[np.ndarray, np.ndarray, float]:
    """Radial bowl + specular rim. Returns (alpha mask, signed delta map, amplitude)."""
    a = rng.uniform(16.0, 40.0)
    b = a * rng.uniform(0.55, 1.0)
    cx = rng.uniform(0.22, 0.78) * size
    cy = rng.uniform(0.22, 0.78) * size
    ang = rng.uniform(0.0, np.pi)
    amp = rng.uniform(13.0, 30.0)

    ca, sa = np.cos(ang), np.sin(ang)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    xr = xx - cx
    yr = yy - cy
    u = (ca * xr + sa * yr) / a
    v = (-sa * xr + ca * yr) / b
    d2 = u * u + v * v
    inside = d2 < 1.0

    bowl = -amp * np.power(np.clip(1.0 - d2, 0.0, 1.0), 0.85)
    rim = 0.45 * amp * np.exp(-(((np.sqrt(d2) - 0.93) / 0.10) ** 2))
    delta = np.where(inside, bowl + rim, 0.0).astype(np.float32)
    alpha = (np.abs(delta) > 0.12 * amp).astype(np.float32)
    alpha = cv2.GaussianBlur(alpha, (0, 0), 0.8)
    return alpha, delta, float(amp)


def _draw_stain(rng: np.random.Generator, size: int) -> tuple[np.ndarray, float, float]:
    """Irregular low-contrast blotch (oil, dirt, coolant residue)."""
    cx = rng.uniform(0.2, 0.8) * size
    cy = rng.uniform(0.2, 0.8) * size
    radius = rng.uniform(14.0, 34.0)
    n = int(rng.integers(9, 15))
    angles = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False) + rng.uniform(-0.12, 0.12, n)
    radii = radius * rng.uniform(0.62, 1.18, n)
    poly = np.stack([cx + radii * np.cos(angles), cy + radii * np.sin(angles)], axis=1)
    mask = np.zeros((size, size), np.uint8)
    cv2.fillPoly(mask, [np.round(poly).astype(np.int32)], 255)
    alpha = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), rng.uniform(2.5, 4.5))
    delta = -rng.uniform(9.0, 16.0)
    return alpha, float(delta), 0.0


def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    return inter / float(aw * ah + bw * bh - inter)


def make_sample(seed: int, cfg: SynthConfig | None = None, n_defects: int | None = None) -> dict:
    """Build one deterministic sample.

    Returns {"image": BGR uint8 array, "gt": {...}, "config": {...}}.
    `n_defects` bypasses the random count (used by tests and by `synth` CLI).
    """
    cfg = cfg or SynthConfig()
    size = cfg.size
    rng = np.random.default_rng(seed)
    img = _background(rng, size)

    if n_defects is None:
        if rng.random() < cfg.clean_prob:
            n = 0
        else:
            n = int(rng.choice([1, 2, 3], p=[0.45, 0.35, 0.20]))
    else:
        n = int(n_defects)

    defects: list[dict] = []
    placed: list[tuple[int, int, int, int]] = []
    for idx in range(n):
        kind = (KIND_SCRATCH, KIND_DENT, KIND_STAIN)[int(rng.choice(3, p=[0.42, 0.33, 0.25]))]
        for _ in range(cfg.max_attempts):
            if kind == KIND_SCRATCH:
                alpha, delta, _ = _draw_scratch(rng, size)
                if rng.random() < 0.3:
                    delta = -delta  # bright gouge catching the light
                delta_map = None
            elif kind == KIND_DENT:
                alpha, delta_map, _ = _draw_dent(rng, size)
            else:
                alpha, delta, _ = _draw_stain(rng, size)
                delta_map = None
            bbox = _mask_bbox(alpha)
            if bbox is None:
                continue
            if any(_iou(bbox, other) > 0.02 for other in placed):
                continue
            x, y, w, h = bbox
            if w < 4 or h < 4:
                continue
            break
        else:
            continue

        if kind == KIND_DENT:
            delta_px = np.where(alpha > 0.02, delta_map, 0.0).astype(np.float32)
            img = img + delta_px
            contrast = float(np.abs(delta_px[alpha > 0.05]).mean())
        else:
            img = img + alpha * delta
            contrast = float(abs(delta) * alpha[alpha > 0.1].mean())
        placed.append(bbox)
        defects.append(
            {
                "id": len(defects),
                "type": kind,
                "bbox": [int(v) for v in bbox],
                "area_px": int((alpha > 0.25).sum()),
                "contrast": round(contrast, 2),
            }
        )

    noise_sigma = rng.uniform(1.2, 3.0)
    img = img + rng.normal(0.0, noise_sigma, img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    gt = {
        "seed": int(seed),
        "size": [int(size), int(size)],
        "noise_sigma": round(float(noise_sigma), 2),
        "defects": defects,
    }
    return {"image": bgr, "gt": gt, "config": asdict(cfg)}


def generate_dataset(
    out_dir: str | Path,
    n: int,
    seed_base: int = 7000,
    cfg: SynthConfig | None = None,
    clean_prob: float | None = None,
) -> dict:
    """Write `n` images + `ground_truth.json` into out_dir. Returns the manifest."""
    cfg = cfg or SynthConfig()
    if clean_prob is not None:
        cfg = SynthConfig(**{**asdict(cfg), "clean_prob": clean_prob})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    images_dir = out / "images"
    images_dir.mkdir(exist_ok=True)

    entries = []
    for i in range(n):
        seed = seed_base + i
        sample = make_sample(seed, cfg)
        name = f"plate_{i:04d}_seed{seed}.png"
        cv2.imwrite(str(images_dir / name), sample["image"])
        entry = {
            "file": f"images/{name}",
            "seed": seed,
            "defects": sample["gt"]["defects"],
            "noise_sigma": sample["gt"]["noise_sigma"],
        }
        entries.append(entry)

    manifest = {
        "version": 1,
        "generator": "fieldlens.synth",
        "config": asdict(cfg),
        "count": n,
        "entries": entries,
    }
    (out / "ground_truth.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load_dataset(path: str | Path) -> list[dict]:
    """Load images + ground truth from a directory produced by generate_dataset."""
    root = Path(path)
    manifest = json.loads((root / "ground_truth.json").read_text(encoding="utf-8"))
    samples = []
    for entry in manifest["entries"]:
        img = cv2.imread(str(root / entry["file"]), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"missing image for dataset entry: {entry['file']}")
        samples.append({"image": img, "gt": {"defects": entry["defects"], "seed": entry["seed"]}})
    return samples
