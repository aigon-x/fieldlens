"""Input domain guard.

FieldLens is calibrated for flat, evenly lit industrial surfaces. Printed documents,
fabric or wood produce thousands of edges, and every edge looks like a defect to a
gradient detector. Rather than show a confident list of nonsense, the API reports that
the input is outside the domain.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import cv2
import numpy as np

# Measured on the bundled synthetic plates (edge density <= 0.0022, Laplacian <= 187)
# and on a photographed document (0.117 and 825). Thresholds sit well between them.
EDGE_DENSITY_LIMIT = 0.03
LAPLACIAN_VARIANCE_LIMIT = 400.0


@dataclass
class InputQuality:
    in_domain: bool
    code: str | None
    message: str | None
    edge_density: float
    laplacian_variance: float

    def as_dict(self) -> dict:
        return asdict(self)


def assess(image: np.ndarray) -> InputQuality:
    if image is None or image.size == 0:
        return InputQuality(False, "empty", "The image could not be read.", 0.0, 0.0)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, 50, 150)
    density = float((edges > 0).mean())
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if density > EDGE_DENSITY_LIMIT or variance > LAPLACIAN_VARIANCE_LIMIT:
        return InputQuality(
            False, "outside_domain",
            "This does not look like a flat, evenly lit surface: the image is too textured. "
            "Defect counts on printed documents, fabric or wood are not meaningful.",
            round(density, 4), round(variance, 1))
    return InputQuality(True, None, None, round(density, 4), round(variance, 1))
