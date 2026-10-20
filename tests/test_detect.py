"""Detector behaviour: true positives with real IoU, plus the negative case."""

from __future__ import annotations

import cv2
import numpy as np

from fieldlens.annotate import annotate, mask_overlay
from fieldlens.benchmark import bbox_iou
from fieldlens.detect import inspect_array


def _best_match(result, gt_defect) -> tuple[float, str]:
    best_iou, best_kind = 0.0, ""
    for det in result.defects:
        iou = bbox_iou(det.bbox, gt_defect["bbox"])
        if iou > best_iou:
            best_iou, best_kind = iou, det.kind
    return best_iou, best_kind


def test_detects_scratch_with_real_overlap(scratch_sample) -> None:
    result = inspect_array(scratch_sample["image"])
    gt = scratch_sample["gt"]["defects"][0]
    iou, kind = _best_match(result, gt)
    assert result.defects, "no defect reported for a plate with one scratch"
    assert iou >= 0.40, f"IoU {iou:.3f} too low for the single scratch"
    assert kind == "scratch"


def test_detects_dent(dent_sample) -> None:
    result = inspect_array(dent_sample["image"])
    gt = dent_sample["gt"]["defects"][0]
    iou, kind = _best_match(result, gt)
    assert iou >= 0.40
    assert kind == "dent"


def test_detects_low_contrast_stain(stain_sample) -> None:
    result = inspect_array(stain_sample["image"])
    gt = stain_sample["gt"]["defects"][0]
    iou, kind = _best_match(result, gt)
    assert iou >= 0.30, f"IoU {iou:.3f} too low for the stain"
    assert kind == "stain"


def test_clean_plates_report_nothing(clean_samples) -> None:
    """Negative test: a plate with texture and sensor noise but no defect must stay empty."""
    for sample in clean_samples:
        result = inspect_array(sample["image"])
        assert result.defects == [], f"false positives on clean plate {sample['gt']['seed']}: {result.defects}"


def test_gray_input_matches_bgr(scratch_sample) -> None:
    bgr = scratch_sample["image"]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    assert len(inspect_array(gray).defects) == len(inspect_array(bgr).defects)


def test_large_image_coordinates_are_original_scale(scratch_sample) -> None:
    """2x upscale must be analysed at working resolution but reported in original pixels."""
    bgr = scratch_sample["image"]
    big = cv2.resize(bgr, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    small_res = inspect_array(bgr)
    big_res = inspect_array(big)
    assert big_res.image_size == (bgr.shape[1] * 2, bgr.shape[0] * 2)
    assert big_res.scale <= 1.0
    # the same defect must land in the same place after undoing the 2x factor
    gt = scratch_sample["gt"]["defects"][0]["bbox"]
    iou_small, _ = _best_match(small_res, {"bbox": gt})
    iou_big, _ = _best_match(big_res, {"bbox": [v * 2 for v in gt]})
    assert iou_small >= 0.4 and iou_big >= 0.4


def test_mask_and_annotation_shapes(scratch_sample) -> None:
    result = inspect_array(scratch_sample["image"])
    h, w = scratch_sample["image"].shape[:2]
    assert result.mask is not None and result.mask.shape == (h, w)
    assert result.mask.dtype == np.uint8
    annotated = annotate(scratch_sample["image"], result)
    overlay = mask_overlay(scratch_sample["image"], result.mask)
    assert annotated.shape == overlay.shape == (h, w, 3)
    assert not np.array_equal(annotated, scratch_sample["image"]), "annotation drew nothing"
    assert not np.array_equal(overlay, scratch_sample["image"]), "mask overlay drew nothing"


def test_flat_image_has_no_defects() -> None:
    flat = np.full((256, 256, 3), 127, dtype=np.uint8)
    assert inspect_array(flat).defects == []
