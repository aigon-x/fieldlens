"""Benchmark: synthetic data -> detections -> matched precision/recall/F1.

Matching is one-to-one (greedy by score) because a single physical defect must not
inflate both precision and recall. A thin scratch has an unfavourable area/bbox
ratio, so besides IoU the matcher accepts a detection that is *contained* in the
ground-truth box (containment >= 0.6, detection at most 3x GT area). This is stated
explicitly in the report so the numbers are not over-claimed.
"""

from __future__ import annotations

import time
from dataclasses import asdict

import numpy as np

from .detect import DEFAULT_PARAMS, Params, inspect_array
from .synth import SynthConfig, make_sample


def bbox_iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = float((x1 - x0) * (y1 - y0))
    return inter / float(aw * ah + bw * bh - inter)


def _containment(det, gt) -> float:
    dx, dy, dw, dh = det
    gx, gy, gw, gh = gt
    x0, y0 = max(dx, gx), max(dy, gy)
    x1, y1 = min(dx + dw, gx + gw), min(dy + dh, gy + gh)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float((x1 - x0) * (y1 - y0)) / float(max(1, dw * dh))


def match(detections: list[dict], truths: list[dict], iou_thr: float = 0.25) -> list[tuple[int, int, float]]:
    """One-to-one greedy matching. Returns [(det_idx, gt_idx, score)]."""
    candidates: list[tuple[float, int, int]] = []
    for di, det in enumerate(detections):
        for gi, gt in enumerate(truths):
            iou = bbox_iou(det["bbox"], gt["bbox"])
            cont = _containment(det["bbox"], gt["bbox"])
            det_area = det["bbox"][2] * det["bbox"][3]
            gt_area = gt["bbox"][2] * gt["bbox"][3]
            contained_ok = cont >= 0.6 and det_area <= 3.0 * gt_area
            if iou >= iou_thr or contained_ok:
                score = max(iou, 0.5 * cont)
                candidates.append((score, di, gi))

    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    used_det: set[int] = set()
    used_gt: set[int] = set()
    pairs: list[tuple[int, int, float]] = []
    for score, di, gi in candidates:
        if di in used_det or gi in used_gt:
            continue
        used_det.add(di)
        used_gt.add(gi)
        pairs.append((di, gi, score))
    return pairs


def evaluate(samples: list[dict], params: Params = DEFAULT_PARAMS) -> dict:
    """Run the detector over samples (each with 'image' and 'gt') and score it."""
    tp = fp = fn = 0
    clean_images = 0
    clean_fp = 0
    matched_iou: list[float] = []
    per_kind_gt = {"scratch": 0, "dent": 0, "stain": 0}
    per_kind_hit = {"scratch": 0, "dent": 0, "stain": 0}
    per_kind_pred = {"scratch": 0, "dent": 0, "stain": 0}
    kind_correct = 0
    total_ms = 0.0
    image_failures: list[dict] = []

    for sample in samples:
        result = inspect_array(sample["image"], params)
        total_ms += result.elapsed_ms
        truths = sample["gt"]["defects"]
        dets = [d.to_dict() for d in result.defects]
        if not truths:
            clean_images += 1
            clean_fp += len(dets)
        pairs = match(dets, truths)
        matched_dets = {di for di, _, _ in pairs}
        matched_gts = {gi for _, gi, _ in pairs}

        tp += len(pairs)
        fp += len(dets) - len(matched_dets)
        fn += len(truths) - len(matched_gts)
        for det_idx, gt_idx, score in pairs:
            matched_iou.append(score)
            gkind = truths[gt_idx]["type"]
            per_kind_gt[gkind] += 1
            per_kind_hit[gkind] += 1
            if dets[det_idx]["kind"] == gkind:
                kind_correct += 1
        for gi, gt in enumerate(truths):
            if gi not in matched_gts:
                per_kind_gt[gt["type"]] += 1
        for det in dets:
            per_kind_pred[det["kind"]] = per_kind_pred.get(det["kind"], 0) + 1

        if len(pairs) != len(truths):
            image_failures.append(
                {
                    "seed": sample["gt"].get("seed"),
                    "gt": len(truths),
                    "det": len(dets),
                    "missed": [truths[gi]["type"] for gi in range(len(truths)) if gi not in matched_gts],
                }
            )

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    n = len(samples)
    return {
        "images": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "mean_match_score": round(float(np.mean(matched_iou)), 4) if matched_iou else 0.0,
        "kind_accuracy": round(kind_correct / tp, 4) if tp else 0.0,
        "per_kind": {
            k: {
                "gt": per_kind_gt[k],
                "hit": per_kind_hit[k],
                "pred": per_kind_pred.get(k, 0),
                "recall": round(per_kind_hit[k] / per_kind_gt[k], 4) if per_kind_gt[k] else None,
            }
            for k in ("scratch", "dent", "stain")
        },
        "clean_images": clean_images,
        "false_positives_on_clean": clean_fp,
        "fp_per_clean_image": round(clean_fp / clean_images, 3) if clean_images else 0.0,
        "ms_per_image": round(total_ms / n, 2) if n else 0.0,
        "images_per_s": round(1000.0 * n / total_ms, 2) if total_ms else 0.0,
        "failed_images": image_failures[:10],
        "params": asdict(params),
    }


def run_benchmark(
    n: int = 40,
    seed: int = 7000,
    cfg: SynthConfig | None = None,
    params: Params = DEFAULT_PARAMS,
    min_f1: float = 0.80,
) -> dict:
    """Generate n deterministic plates, evaluate, and apply the acceptance gate."""
    cfg = cfg or SynthConfig()
    t0 = time.perf_counter()
    samples = [make_sample(seed + i, cfg) for i in range(n)]
    gen_ms = (time.perf_counter() - t0) * 1000.0
    report = evaluate(samples, params)
    report["seed_base"] = seed
    report["generator_ms_total"] = round(gen_ms, 1)
    report["wall_ms_total"] = round(gen_ms + report["ms_per_image"] * n, 1)
    report["min_f1"] = min_f1
    report["passed"] = report["f1"] >= min_f1
    return report
