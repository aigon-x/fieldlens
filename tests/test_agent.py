"""Tests for the active-perception layer (agent.py + /agent/inspect).

These assert the *decision policy*, not the detector: the detector is covered by
the existing benchmark suite. A green run here means the agent really decides.
"""

from __future__ import annotations

import numpy as np
import pytest

from fieldlens.agent import inspect_adaptive, summarize
from fieldlens.detect import DEFAULT_PARAMS


def _clean_plate(size: int = 384) -> np.ndarray:
    """Uniform grey plate: no gradient, no texture, no defects."""
    return np.full((size, size, 3), 128, dtype=np.uint8)


def test_clean_plate_raises_sensitivity_then_requests_rescan():
    """0 defects at baseline must trigger a sensitivity raise, then a rescan — never a silent 0."""
    res, decisions, outcome = inspect_adaptive(_clean_plate())
    actions = [d["action"] for d in decisions]
    assert actions[0] == "inspect"
    assert "request_rescan" in actions, "agent must refuse to guess on an undecidable plate"
    assert outcome == "rescan_needed"
    assert len(res.defects) == 0
    # the sensitivity raise is explicit and logged
    assert any("raise sensitivity" in (d.get("next") or "") for d in decisions)


def test_sensitivity_raise_lowers_every_channel_threshold():
    """The tuning step must actually change Params, not just claim to."""
    from fieldlens.agent import _scale

    p = _scale(DEFAULT_PARAMS, 0.85)
    assert all(a < b for a, b in zip(p.log_thresholds, DEFAULT_PARAMS.log_thresholds))
    assert p.dog_threshold < DEFAULT_PARAMS.dog_threshold
    assert p.disk_threshold < DEFAULT_PARAMS.disk_threshold
    assert p.line_threshold < DEFAULT_PARAMS.line_threshold


def test_out_of_domain_input_is_rejected_without_inspecting():
    """Quality gate comes first: a bad image must not be 'inspected' into a guess."""
    quality = {"in_domain": False, "code": "too_blurry", "message": "laplacian variance 3"}
    res, decisions, outcome = inspect_adaptive(_clean_plate(), quality=quality)
    assert outcome == "rescan_needed"
    assert decisions[0]["action"] == "request_rescan"
    assert "too_blurry" in decisions[0]["reason"] or "laplacian" in decisions[0]["reason"]
    assert not any(d["action"] == "inspect" for d in decisions)


def test_loop_is_bounded():
    """The agent must never exceed MAX_ITERS inspections (no runaway loop)."""
    from fieldlens.agent import MAX_ITERS

    _, decisions, _ = inspect_adaptive(_clean_plate())
    inspections = [d for d in decisions if d["action"] == "inspect"]
    assert len(inspections) <= MAX_ITERS


def test_every_decision_carries_a_reason_and_thresholds():
    """An auditable trail: each step has reason + thresholds (that is the judge demo)."""
    _, decisions, _ = inspect_adaptive(_clean_plate())
    for d in decisions:
        assert d.get("reason"), f"decision without reason: {d}"
        assert d.get("thresholds"), f"decision without thresholds: {d}"


def test_summary_is_machine_readable():
    _, decisions, outcome = inspect_adaptive(_clean_plate())
    s = summarize(decisions, outcome)
    assert s["outcome"] == outcome
    assert isinstance(s["iterations"], int)
    assert isinstance(s["rescans"], int)
    assert s["trail"]


def test_agent_endpoint_registered_and_returns_decision_log():
    """The HTTP surface exists and returns the agent block, not just detections."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    client = fastapi_testclient.TestClient(_app())
    routes = {r.path for r in client.app.routes if hasattr(r, "path")}
    assert "/agent/inspect" in routes

    import io

    import cv2

    img = _clean_plate()
    ok, buf = cv2.imencode(".png", img)
    assert ok
    r = client.post("/agent/inspect", files={"file": ("p.png", io.BytesIO(buf.tobytes()), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"].endswith("active-perception")
    assert body["agent"]["outcome"] in ("decided", "rescan_needed")
    assert body["agent"]["decisions"]


def _app():
    from fieldlens.api import create_app

    return create_app()
