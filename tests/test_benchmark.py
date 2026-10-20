"""Benchmark: matching semantics, acceptance gate and metric responsiveness (ablation)."""

from __future__ import annotations

import pytest

from fieldlens.benchmark import bbox_iou, match, run_benchmark, run_seed_sweep
from fieldlens.detect import Params


def test_iou_basics() -> None:
    assert bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert bbox_iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0
    assert bbox_iou((0, 0, 10, 10), (5, 0, 10, 10)) == pytest.approx(50 / 150)


def test_matching_is_one_to_one() -> None:
    dets = [{"bbox": [0, 0, 10, 10], "kind": "scratch"}, {"bbox": [1, 1, 10, 10], "kind": "scratch"}]
    truths = [{"bbox": [0, 0, 10, 10], "type": "scratch"}]
    pairs = match(dets, truths)
    assert len(pairs) == 1, "one ground-truth defect must not absorb two detections"
    assert pairs[0][1] == 0


def test_matching_rejects_unrelated_boxes() -> None:
    dets = [{"bbox": [0, 0, 8, 8], "kind": "stain"}]
    truths = [{"bbox": [200, 200, 20, 20], "type": "stain"}]
    assert match(dets, truths) == []


def test_matching_accepts_contained_core() -> None:
    """A thin scratch often yields a core inside its true box; containment must count."""
    dets = [{"bbox": [20, 20, 60, 8], "kind": "scratch"}]
    truths = [{"bbox": [16, 18, 80, 14], "type": "scratch"}]
    assert len(match(dets, truths)) == 1


def test_strict_iou_50_rejects_the_lenient_contained_core() -> None:
    """IoU 0.5 without containment must disagree with the generous primary rule."""
    dets = [{"bbox": [20, 20, 60, 8], "kind": "scratch"}]
    truths = [{"bbox": [16, 18, 80, 14], "type": "scratch"}]
    assert len(match(dets, truths)) == 1, "containment accepts the thin core"
    assert match(dets, truths, iou_thr=0.5, allow_containment=False) == []


def test_benchmark_passes_acceptance_gate() -> None:
    report = run_benchmark(n=20, seed=7000, min_f1=0.80)
    assert report["images"] == 20
    assert report["f1"] >= 0.80, f"F1 {report['f1']} below the 0.80 gate"
    assert report["precision"] > 0.0 and report["recall"] > 0.0
    assert report["tp"] + report["fn"] > 0
    assert report["passed"] is True
    # bookkeeping must add up: every prediction is TP or FP
    assert report["tp"] + report["fp"] == sum(k["pred"] for k in report["per_kind"].values())
    assert report["tp"] + report["fn"] == sum(k["gt"] for k in report["per_kind"].values())


def test_benchmark_reports_all_matchers() -> None:
    report = run_benchmark(n=6, seed=7000)
    assert report["matching"]["primary"]["iou_threshold"] == 0.25
    assert report["matching"]["iou25_no_containment"]["containment"] is False
    assert report["matching"]["strict"]["iou_threshold"] == 0.5
    iou25 = report["iou25_no_containment"]
    strict = report["strict_iou50"]
    assert iou25["f1"] <= report["f1"], "dropping containment cannot improve F1"
    assert strict["f1"] <= iou25["f1"]
    assert strict["tp"] + strict["fn"] == sum(k["gt"] for k in report["per_kind"].values())


def test_seed_sweep_reports_min_median_max() -> None:
    sweep = run_seed_sweep(n=4, seeds=[7000, 7001, 7002, 7003, 7004])
    assert len(sweep["per_seed"]) == 5
    for key in ("f1_iou25_containment", "f1_iou25_no_containment", "f1_iou50_strict"):
        stats = sweep[key]
        assert len(stats["values"]) == 5
        assert stats["min"] <= stats["median"] <= stats["max"]
    assert sweep["clean_images_total"] >= 0


def test_metric_reacts_to_a_blind_detector() -> None:
    """Ablation: a detector that cannot fire must score F1 = 0.

    Without this, a benchmark that always reports good numbers would be a facade.
    """
    blind = Params(log_thresholds=(1e6, 1e6), dog_threshold=1e6, disk_threshold=1e6, line_threshold=1e6)
    report = run_benchmark(n=6, seed=7000, params=blind)
    assert report["tp"] == 0
    assert report["fp"] == 0
    assert report["recall"] == 0.0
    assert report["f1"] == 0.0
    assert report["passed"] is False
