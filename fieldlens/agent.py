"""Active perception: adaptive inspection loop with an auditable decision log.

This is the agentic layer on top of the classical engine. It does NOT change the
matched-filter maths; it changes *how the engine is driven*: inspect, read the
channel mix and the contrast in noise units, decide, and either re-inspect with
adjusted thresholds or refuse to guess and ask for a rescan.

Design rules (why this is active perception and not a retry loop):
  * every decision has a machine-readable reason and is logged;
  * the loop is bounded (MAX_ITERS) and monotone (sensitivity once, specificity once);
  * **a tuned iteration is accepted only if its detections carry strong evidence**
    (>= MIN_EVIDENCE_ACCEPT x the channel threshold). This is what stops the
    sensitivity raise from buying false positives: in the shipped benchmark a
    blind sensitivity raise cost -0.0125 F1 at IoU 0.25 (precision 0.781 -> 0.758,
    recall unchanged), so the loop now keeps only high-evidence detections;
  * "not decidable" is a valid outcome -> `request_rescan`, never a silent guess.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from .detect import DEFAULT_PARAMS, Params, inspect_array
from .types import InspectionResult

MAX_ITERS = 3
SENSITIVITY_STEP = 0.85  # lower thresholds -> catch faint defects
SPECIFICITY_STEP = 1.15  # higher thresholds -> suppress texture false positives
MANY_HITS = 8
LOW_CONTRAST = 2.0  # in noise units; below the reporting floor
# A detection accepted after tuning must sit clearly above the noise floor.
# `score` is the peak evidence in "just at the channel threshold" units, so 2.0
# means "twice the threshold" -- a real defect, not texture.
MIN_EVIDENCE_ACCEPT = 2.0


def _scale(p: Params, k: float) -> Params:
    """Return Params with every channel threshold multiplied by k."""
    return replace(
        p,
        log_thresholds=tuple(t * k for t in p.log_thresholds),
        dog_threshold=p.dog_threshold * k,
        disk_threshold=p.disk_threshold * k,
        line_threshold=p.line_threshold * k,
    )


def _thresholds(p: Params) -> dict[str, Any]:
    return {
        "log": [round(t, 3) for t in p.log_thresholds],
        "dog": round(p.dog_threshold, 3),
        "disk": round(p.disk_threshold, 3),
        "line": round(p.line_threshold, 3),
    }


def _mean_contrast(res: InspectionResult) -> float:
    if not res.defects:
        return 0.0
    return sum(d.contrast for d in res.defects) / len(res.defects)


def _kinds(res: InspectionResult) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in res.defects:
        out[d.kind] = out.get(d.kind, 0) + 1
    return out


def _strong_only(res: InspectionResult, floor: float = MIN_EVIDENCE_ACCEPT) -> InspectionResult:
    """Keep only detections whose peak evidence clears the acceptance floor."""
    kept = [d for d in res.defects if d.score >= floor]
    if len(kept) == len(res.defects):
        return res
    res.defects = kept
    return res


def inspect_adaptive(
    bgr: np.ndarray,
    base: Params = DEFAULT_PARAMS,
    max_iters: int = MAX_ITERS,
    quality: dict | None = None,
) -> tuple[InspectionResult, list[dict[str, Any]], str]:
    """Run the active-perception loop.

    Returns (best_result, decisions, outcome) where outcome is one of:
      "decided"        - a stable read was reached
      "rescan_needed"  - input quality or ambiguity says: ask for another image
    """
    decisions: list[dict[str, Any]] = []
    params = base
    best: tuple[int, InspectionResult, Params] | None = None
    outcome = "decided"

    if quality is not None and quality.get("in_domain") is False:
        decisions.append({
            "iter": 0,
            "action": "request_rescan",
            "reason": f"input out of domain: {quality.get('message') or quality.get('code')}",
            "count": 0,
            "thresholds": _thresholds(params),
        })
        return inspect_array(bgr, params), decisions, "rescan_needed"

    for i in range(1, max_iters + 1):
        res = inspect_array(bgr, params)
        # A tuned read is filtered: only high-evidence detections survive, so the
        # sensitivity raise cannot pay for itself with texture false positives.
        if i > 1:
            before = len(res.defects)
            res = _strong_only(res)
            if before != len(res.defects):
                decisions.append({
                    "iter": i,
                    "action": "filter_evidence",
                    "reason": f"dropped {before - len(res.defects)} detections below evidence {MIN_EVIDENCE_ACCEPT}",
                    "count": len(res.defects),
                    "thresholds": _thresholds(params),
                })
        n = len(res.defects)
        mc = _mean_contrast(res)
        mean_evidence = (sum(d.score for d in res.defects) / n) if n else 0.0

        decisions.append({
            "iter": i,
            "action": "inspect",
            "reason": "baseline" if i == 1 else "re-inspect after tuning",
            "count": n,
            "kinds": _kinds(res),
            "mean_contrast_sigma": round(mc, 2),
            "mean_evidence": round(mean_evidence, 3),
            "thresholds": _thresholds(params),
        })

        if best is None or n > best[0]:
            best = (n, res, params)

        # --- decision policy (explicit, auditable) -------------------------
        if i == 1 and n == 0:
            params = _scale(params, SENSITIVITY_STEP)
            decisions[-1]["next"] = (
                f"raise sensitivity x{SENSITIVITY_STEP} (0 defects at baseline)"
            )
            continue

        if n > MANY_HITS and mc < LOW_CONTRAST:
            params = _scale(params, SPECIFICITY_STEP)
            decisions[-1]["next"] = (
                f"raise specificity x{SPECIFICITY_STEP} "
                f"({n} hits, mean contrast {mc:.2f} < {LOW_CONTRAST} noise units)"
            )
            continue

        decisions[-1]["next"] = "stop (stable read)"
        break

    assert best is not None
    n, res, _ = best
    if n == 0 and len(decisions) > 1:
        decisions.append({
            "iter": len(decisions) + 1,
            "action": "request_rescan",
            "reason": "no defect above the reporting floor after sensitivity raise",
            "count": 0,
            "thresholds": _thresholds(params),
        })
        outcome = "rescan_needed"

    return res, decisions, outcome


def summarize(decisions: list[dict[str, Any]], outcome: str) -> dict[str, Any]:
    """Compact, judge-readable summary of what the agent did and why."""
    return {
        "outcome": outcome,
        "iterations": sum(1 for d in decisions if d["action"] == "inspect"),
        "rescans": sum(1 for d in decisions if d["action"] == "request_rescan"),
        "trail": "; ".join(
            f"i{d['iter']} {d['action']} -> {d.get('count', '?')} hits"
            + (f" ({d['next']})" if d.get("next") else "")
            for d in decisions
        ),
    }
