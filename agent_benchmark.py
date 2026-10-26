#!/usr/bin/env python3
"""agent_benchmark.py — does the active-perception loop actually improve F1?

Compares, on the same deterministic plates:
  baseline : inspect_array(DEFAULT_PARAMS)      (what the classical engine does)
  agent    : inspect_adaptive(...)              (the shipped loop)

Scored with the repository's own matcher (`fieldlens.benchmark.match`), at
IoU 0.25 and 0.50, no containment — the honest numbers, not the lenient rule.

Writes /tmp/agent-bench.json and prints a table.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fieldlens.agent import inspect_adaptive
from fieldlens.benchmark import match
from fieldlens.detect import DEFAULT_PARAMS, inspect_array
from fieldlens.synth import SynthConfig, make_sample


def score(samples, use_agent: bool, iou: float) -> dict:
    tp = fp = fn = 0
    clean = clean_fp = 0
    iters: list[int] = []
    rescans = 0
    for s in samples:
        if use_agent:
            res, decisions, outcome = inspect_adaptive(s["image"])
            iters.append(sum(1 for d in decisions if d["action"] == "inspect"))
            rescans += 1 if outcome == "rescan_needed" else 0
        else:
            res = inspect_array(s["image"], DEFAULT_PARAMS)
        dets = [d.to_dict() for d in res.defects]
        truths = s["gt"]["defects"]
        if not truths:
            clean += 1
            clean_fp += len(dets)
        pairs = match(dets, truths, iou_thr=iou, allow_containment=False)
        mdet = {di for di, _, _ in pairs}
        mgt = {gi for _, gi, _ in pairs}
        tp += len(pairs)
        fp += len(dets) - len(mdet)
        fn += len(truths) - len(mgt)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn,
        "clean_plates": clean, "clean_fp": clean_fp,
        "mean_iterations": round(statistics.mean(iters), 2) if iters else None,
        "rescans": rescans if use_agent else None,
    }


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7000
    cfg = SynthConfig()
    samples = [make_sample(seed + i, cfg) for i in range(n)]

    out = {"n": n, "seed": seed, "engine": "fieldlens/agent + detect"}
    for iou in (0.25, 0.50):
        out[f"baseline_iou{int(iou*100)}"] = score(samples, False, iou)
        out[f"agent_iou{int(iou*100)}"] = score(samples, True, iou)

    for iou in (0.25, 0.50):
        b = out[f"baseline_iou{int(iou*100)}"]
        a = out[f"agent_iou{int(iou*100)}"]
        delta = round(a["f1"] - b["f1"], 4)
        out[f"delta_f1_iou{int(iou*100)}"] = delta
        print(f"IoU {iou:.2f}  baseline F1={b['f1']:.4f} (P={b['precision']:.3f} R={b['recall']:.3f})"
              f"  agent F1={a['f1']:.4f} (P={a['precision']:.3f} R={a['recall']:.3f})"
              f"  delta={delta:+.4f}  iters={a['mean_iterations']} rescans={a['rescans']}")

    same = out["baseline_iou25"]["f1"] == out["agent_iou25"]["f1"]
    out["verdict"] = (
        "agent == baseline on this sample set (loop stops at iteration 1: the read is already stable)"
        if same else
        "agent differs from baseline (loop tuned thresholds)"
    )
    Path("/tmp/agent-bench.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print("VERDICT:", out["verdict"])
    print("saved /tmp/agent-bench.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
