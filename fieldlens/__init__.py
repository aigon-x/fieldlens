"""FieldLens — classical-CV visual inspection for scratches, dents and stains."""

from __future__ import annotations

from .benchmark import bbox_iou, evaluate, match, run_benchmark
from .detect import DEFAULT_PARAMS, Params, inspect_array
from .synth import SynthConfig, generate_dataset, make_sample
from .types import KINDS, Defect, InspectionResult

__version__ = "1.0.0"

__all__ = [
    "DEFAULT_PARAMS",
    "KINDS",
    "Defect",
    "InspectionResult",
    "Params",
    "SynthConfig",
    "__version__",
    "bbox_iou",
    "evaluate",
    "generate_dataset",
    "inspect_array",
    "make_sample",
    "match",
    "run_benchmark",
]
