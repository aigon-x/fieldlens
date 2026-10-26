#!/usr/bin/env python3
"""fieldlens_mcp.py — MCP server (stdio, JSON-RPC 2.0) exposing FieldLens to an agent.

Zero external dependencies: implements the MCP stdio transport directly, so a judge
(or any MCP client) can run it without installing an SDK:

    {"command": "python3", "args": ["fieldlens_mcp.py"], "cwd": "<repo>"}

Tools
-----
inspect          one classical inspection (detections + thresholds used)
tune             scale one channel threshold (log|dog|disk|line), stateful
explain          why each detection fired, optional region filter [x,y,w,h]
request_rescan   structured "not decidable" verdict (never guess)
agent_inspect    full active-perception loop with a decision log
"""
from __future__ import annotations

import base64
import json
import sys
from dataclasses import replace

import cv2
import numpy as np

from fieldlens.agent import inspect_adaptive, summarize
from fieldlens.detect import DEFAULT_PARAMS, Params, inspect_array

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "fieldlens", "version": "1.0.0"}
_STATE: dict[str, Params] = {"params": DEFAULT_PARAMS}


def _p() -> Params:
    return _STATE["params"]


def _decode(image_b64: str) -> np.ndarray:
    raw = image_b64.split(",", 1)[-1]
    arr = cv2.imdecode(np.frombuffer(base64.b64decode(raw), np.uint8), cv2.IMREAD_COLOR)
    if arr is None:
        raise ValueError("image could not be decoded")
    return arr


def _thresholds(p: Params) -> dict:
    return {"log": list(p.log_thresholds), "dog": p.dog_threshold,
            "disk": p.disk_threshold, "line": p.line_threshold}


# ── tools ────────────────────────────────────────────────────────────────
def _inspect(args: dict) -> dict:
    img = _decode(args["image_b64"])
    p = _p()
    if args.get("max_dim"):
        p = replace(p, max_dim=int(args["max_dim"]))
    out = inspect_array(img, p).to_dict()
    out["thresholds"] = _thresholds(p)
    return out


def _tune(args: dict) -> dict:
    ch = str(args.get("channel", "")).lower()
    f = float(args.get("factor", 1.0))
    if not (0.5 <= f <= 2.0):
        return {"error": "factor out of range 0.5..2.0"}
    p = _p()
    if ch == "log":
        p = replace(p, log_thresholds=tuple(t * f for t in p.log_thresholds))
    elif ch == "dog":
        p = replace(p, dog_threshold=p.dog_threshold * f)
    elif ch == "disk":
        p = replace(p, disk_threshold=p.disk_threshold * f)
    elif ch == "line":
        p = replace(p, line_threshold=p.line_threshold * f)
    else:
        return {"error": f"unknown channel {ch!r}; use log|dog|disk|line"}
    _STATE["params"] = p
    return {"channel": ch, "factor": f, "thresholds": _thresholds(p)}


def _explain(args: dict) -> dict:
    img = _decode(args["image_b64"])
    region = args.get("region")
    res = inspect_array(img, _p())
    rows = []
    for d in res.defects:
        x, y, w, h = d.bbox
        if region:
            rx, ry, rw, rh = region
            if x + w < rx or x > rx + rw or y + h < ry or y > ry + rh:
                continue
        rows.append({"kind": d.kind, "bbox": [x, y, w, h], "area_px": d.area_px,
                     "contrast_sigma": round(d.contrast, 2), "evidence": round(d.score, 3),
                     "elongation": round(d.elongation, 3), "why": _why(d)})
    return {"region": region, "count": len(rows), "detections": rows}


def _why(d) -> str:
    if d.kind == "scratch":
        return f"elongated response {d.elongation:.1f}x; log/line channels above threshold"
    if d.kind == "dent":
        return "center-surround disk response with a rim; blob-like shape"
    return f"low-contrast plateau on disk channel ({d.contrast:.1f} noise units)"


def _request_rescan(args: dict) -> dict:
    return {"action": "request_rescan", "reason": args.get("reason", "unspecified"),
            "hint": "re-photograph with diffuse light or a different angle"}


def _agent_inspect(args: dict) -> dict:
    img = _decode(args["image_b64"])
    res, decisions, outcome = inspect_adaptive(img, _p())
    out = res.to_dict()
    out["thresholds"] = _thresholds(_p())
    out["agent"] = {"outcome": outcome, "decisions": decisions,
                    "summary": summarize(decisions, outcome)}
    return out


def _img_prop() -> dict:
    return {"type": "string", "description": "PNG/JPEG bytes as base64 (data: URI tolerated)"}


TOOLS = [
    {"name": "inspect", "description": "One classical inspection: detections, input thresholds.",
     "inputSchema": {"type": "object", "properties": {"image_b64": _img_prop(), "max_dim": {"type": "integer"}},
                     "required": ["image_b64"]}, "fn": _inspect},
    {"name": "tune", "description": "Scale one channel threshold. factor<1 = more sensitive, >1 = stricter.",
     "inputSchema": {"type": "object", "properties": {"channel": {"type": "string", "enum": ["log", "dog", "disk", "line"]},
                                                      "factor": {"type": "number"}}, "required": ["channel", "factor"]},
     "fn": _tune},
    {"name": "explain", "description": "Explain detections (why each fired), optional region [x,y,w,h].",
     "inputSchema": {"type": "object", "properties": {"image_b64": _img_prop(), "region": {"type": "array", "items": {"type": "integer"}}},
                     "required": ["image_b64"]}, "fn": _explain},
    {"name": "request_rescan", "description": "Report 'not decidable' with a reason instead of guessing.",
     "inputSchema": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]},
     "fn": _request_rescan},
    {"name": "agent_inspect", "description": "Active-perception loop: inspect -> decide -> tune -> re-inspect, with decision log.",
     "inputSchema": {"type": "object", "properties": {"image_b64": _img_prop()}, "required": ["image_b64"]},
     "fn": _agent_inspect},
]
_BY_NAME = {t["name"]: t for t in TOOLS}


# ── JSON-RPC ─────────────────────────────────────────────────────────────
def handle(req: dict) -> dict | None:
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}}
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS]}}
    if method == "tools/call":
        name = params.get("name")
        tool = _BY_NAME.get(name)
        if not tool:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown tool {name!r}"}}
        try:
            payload = tool["fn"](params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}}
        except Exception as exc:  # tool errors are results, not protocol errors
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": json.dumps({"error": str(exc)})}], "isError": True}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
