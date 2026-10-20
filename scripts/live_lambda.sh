#!/usr/bin/env bash
# Execute the handler inside the official AWS Lambda Python runtime image and record a trace.
#
# public.ecr.aws/lambda/python:3.12 ships the Lambda Runtime Interface Emulator, so the
# handler is invoked over the real Lambda Runtime API (port 8080 inside the container)
# without an AWS account. Nothing here creates an AWS resource; deployment stays in
# scripts/deploy_aws.sh and needs credentials.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE="${IMAGE:-fieldlens-lambda:live}"
CONTAINER="${CONTAINER:-fieldlens-live}"
HOST_PORT="${HOST_PORT:-}"   # empty = let Docker pick a free host port
TRACE="${TRACE:-evidence/lambda-live-trace.json}"
SAMPLE="${SAMPLE:-samples/images/plate_0003_seed7403.png}"

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

mkdir -p "$(dirname "$TRACE")"
docker build -q -t "$IMAGE" . >/dev/null
cleanup
docker run -d --name "$CONTAINER" -p "127.0.0.1:${HOST_PORT}:8080" "$IMAGE" >/dev/null

URL="http://127.0.0.1:$(docker port "$CONTAINER" 8080/tcp | head -1 | sed 's/.*://')"
URL="${URL}/2015-03-31/functions/function/invocations"

ready=0
for _ in $(seq 1 60); do
  if curl -s -o /dev/null --max-time 2 -d '{}' "$URL"; then ready=1; break; fi
  sleep 0.5
done
[ "$ready" = 1 ] || { echo "container did not answer on ${URL}" >&2; exit 1; }

IMAGE_REF="$IMAGE" TRACE="$TRACE" URL="$URL" SAMPLE="$SAMPLE" /usr/bin/python3 - <<'PY'
import base64, json, os, time, urllib.request
from pathlib import Path

url, b64 = os.environ["URL"], base64.b64encode(Path(os.environ["SAMPLE"]).read_bytes()).decode()
cases = [
    ("api_gateway_base64", {"body": b64, "isBase64Encoded": True,
                            "queryStringParameters": {"include_mask": "true"}}, 200),
    ("direct_invoke", {"image_base64": b64}, 200),
    ("malformed_body", {"body": "nope", "isBase64Encoded": False}, 400),
    ("s3_event_without_credentials",
     {"Records": [{"s3": {"bucket": {"name": "fieldlens-plates-live"},
                          "object": {"key": "plates/plate.png"}}}]}, 502),
]
rows = []
for name, event, expected in cases:
    req = urllib.request.Request(url, data=json.dumps(event).encode(),
                                 headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status, raw = resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        status, raw = exc.code, exc.read().decode()
    outer = json.loads(raw)
    inner = json.loads(outer["body"]) if isinstance(outer.get("body"), str) else {}
    answer = outer.get("statusCode", status)
    rows.append({"case": name, "lambda_status": answer,
                 "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                 "defect_count": inner.get("defect_count"), "error": inner.get("error")})
    if answer != expected:
        raise SystemExit(f"{name}: expected {expected}, got {answer}: {raw[:300]}")

body = ",\n  ".join(json.dumps(r, separators=(",", ":")) for r in rows)
Path(os.environ["TRACE"]).write_text(
    '{\n "runtime_image": "%s",\n "runtime_api": "2015-03-31/functions/function/invocations",'
    '\n "aws_account": null,\n "invocations": [\n  %s\n ]\n}\n'
    % (os.environ["IMAGE_REF"], body), encoding="utf-8")
for r in rows:
    print(f"{r['case']:28s} status={r['lambda_status']:3d} defects={r['defect_count']} {r['elapsed_ms']} ms")
PY
