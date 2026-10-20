"""Benchmark: synthetic data -> detections -> matched precision/recall/F1.

Three matchers are reported for the same detections:

* **primary (lenient)** — IoU >= 0.25, or a detection *contained* in the ground-truth
  box (containment >= 0.6, detection at most 3x GT area). Thin scratches have an
  unfavourable area/bbox ratio, so this rule is deliberately generous.
* **iou25_no_containment** — IoU >= 0.25, no containment.
* **strict** — IoU >= 0.5, no containment, the usual detection convention.

Matching is one-to-one (greedy by score) in all cases because a single physical
defect must not inflate both precision and recall.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Sequence
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


STRICT_IOU = 0.5


def match(
    detections: list[dict],
    truths: list[dict],
    iou_thr: float = 0.25,
    allow_containment: bool = True,
) -> list[tuple[int, int, float]]:
    """One-to-one greedy matching. Returns [(det_idx, gt_idx, score)]."""
    candidates: list[tuple[float, int, int]] = []
    for di, det in enumerate(detections):
        for gi, gt in enumerate(truths):
            iou = bbox_iou(det["bbox"], gt["bbox"])
            cont = _containment(det["bbox"], gt["bbox"])
            det_area = det["bbox"][2] * det["bbox"][3]
            gt_area = gt["bbox"][2] * gt["bbox"][3]
            contained_ok = allow_containment and cont >= 0.6 and det_area <= 3.0 * gt_area
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
    s_tp = s_fp = s_fn = 0
    q_tp = q_fp = q_fn = 0
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

        strict_pairs = match(dets, truths, iou_thr=STRICT_IOU, allow_containment=False)
        strict_dets = {di for di, _, _ in strict_pairs}
        strict_gts = {gi for _, gi, _ in strict_pairs}
        s_tp += len(strict_pairs)
        s_fp += len(dets) - len(strict_dets)
        s_fn += len(truths) - len(strict_gts)

        q_pairs = match(dets, truths, iou_thr=0.25, allow_containment=False)
        q_dets = {di for di, _, _ in q_pairs}
        q_gts = {gi for _, gi, _ in q_pairs}
        q_tp += len(q_pairs)
        q_fp += len(dets) - len(q_dets)
        q_fn += len(truths) - len(q_gts)

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
    s_precision = s_tp / (s_tp + s_fp) if s_tp + s_fp else 0.0
    s_recall = s_tp / (s_tp + s_fn) if s_tp + s_fn else 0.0
    s_f1 = 2 * s_precision * s_recall / (s_precision + s_recall) if s_precision + s_recall else 0.0
    q_precision = q_tp / (q_tp + q_fp) if q_tp + q_fp else 0.0
    q_recall = q_tp / (q_tp + q_fn) if q_tp + q_fn else 0.0
    q_f1 = 2 * q_precision * q_recall / (q_precision + q_recall) if q_precision + q_recall else 0.0
    n = len(samples)
    return {
        "images": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "matching": {
            "primary": {"iou_threshold": 0.25, "containment": True},
            "iou25_no_containment": {"iou_threshold": 0.25, "containment": False},
            "strict": {"iou_threshold": STRICT_IOU, "containment": False},
        },
        "iou25_no_containment": {
            "tp": q_tp,
            "fp": q_fp,
            "fn": q_fn,
            "precision": round(q_precision, 4),
            "recall": round(q_recall, 4),
            "f1": round(q_f1, 4),
        },
        "strict_iou50": {
            "tp": s_tp,
            "fp": s_fp,
            "fn": s_fn,
            "precision": round(s_precision, 4),
            "recall": round(s_recall, 4),
            "f1": round(s_f1, 4),
        },
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
    seeds: Sequence[int] | None = None,
) -> dict:
    """Generate n deterministic plates, evaluate, and apply the acceptance gate.

    `seeds` adds a seed sweep (min/median/max F1 on independent datasets) so a
    single lucky seed cannot be quoted as the headline.
    """
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
    if seeds:
        report["seed_sweep"] = run_seed_sweep(n=n, seeds=seeds, cfg=cfg, params=params)
    return report


def _stats(values: list[float]) -> dict:
    return {
        "values": [round(v, 4) for v in values],
        "min": round(min(values), 4),
        "median": round(statistics.median(values), 4),
        "max": round(max(values), 4),
    }


def run_seed_sweep(
    n: int = 40,
    seeds: Sequence[int] = (5000, 7000, 9000, 12000, 20000, 33333),
    cfg: SynthConfig | None = None,
    params: Params = DEFAULT_PARAMS,
) -> dict:
    """Evaluate independent seed bases and summarise F1 by min/median/max."""
    per_seed = []
    for seed in seeds:
        report = run_benchmark(n=n, seed=int(seed), cfg=cfg, params=params)
        per_seed.append(
            {
                "seed": int(seed),
                "f1_iou25_containment": report["f1"],
                "f1_iou25_no_containment": report["iou25_no_containment"]["f1"],
                "f1_iou50_strict": report["strict_iou50"]["f1"],
                "precision_iou25_containment": report["precision"],
                "recall_iou25_containment": report["recall"],
                "precision_iou50_strict": report["strict_iou50"]["precision"],
                "recall_iou50_strict": report["strict_iou50"]["recall"],
                "clean_images": report["clean_images"],
                "false_positives_on_clean": report["false_positives_on_clean"],
            }
        )
    return {
        "n_per_seed": n,
        "seeds": [int(s) for s in seeds],
        "f1_iou25_containment": _stats([row["f1_iou25_containment"] for row in per_seed]),
        "f1_iou25_no_containment": _stats([row["f1_iou25_no_containment"] for row in per_seed]),
        "f1_iou50_strict": _stats([row["f1_iou50_strict"] for row in per_seed]),
        "clean_images_total": sum(row["clean_images"] for row in per_seed),
        "false_positives_on_clean_total": sum(row["false_positives_on_clean"] for row in per_seed),
        "per_seed": per_seed,
    }
