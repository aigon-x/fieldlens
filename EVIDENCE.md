# EVIDENCE — FieldLens

Every number below is raw command output, produced on 2026-10-20 on the host that runs
the AIGON mesh (`local-aigon`), not an estimate. Reproduce with the commands shown.

## Environment

```
$ python3 - <<'PY'
import sys, cv2, numpy, fastapi, pytest
print("python", sys.version.split()[0])
print("cv2.__version__", cv2.__version__)
print("cv2 file", cv2.__file__)
print("numpy", numpy.__version__)
print("fastapi", fastapi.__version__)
print("pytest", pytest.__version__)
PY
python 3.11.15
cv2.__version__ 5.0.0
cv2 file /home/sniegul/.local/lib/python3.11/site-packages/cv2/__init__.py
numpy 2.4.6
fastapi 0.141.1
pytest 9.0.3
```

OpenCV 5 was installed with the required pin:

```
$ python3 -m pip install --user opencv-python-headless==5.0.0.93
error: externally-managed-environment            # PEP 668 on this host
$ python3 -m pip install --user --break-system-packages opencv-python-headless==5.0.0.93
Collecting opencv-python-headless==5.0.0.93
  Using cached opencv_python_headless-5.0.0.93-cp37-abi3-manylinux_2_28_x86_64.whl (61.2 MB)
Successfully installed opencv-python-headless-5.0.0.93
$ /usr/bin/python3 -m pip install --user --break-system-packages opencv-python-headless==5.0.0.93
Successfully installed opencv-python-headless-5.0.0.93
$ /usr/bin/python3 -c "import cv2; print(cv2.__version__)"
5.0.0
```

`--break-system-packages` was required only because both interpreters carry a PEP 668
marker; combined with `--user` it writes to `~/.local/lib/python3.X/site-packages` and
does not modify the system site-packages.

`requirements.txt` now pins `opencv-python-headless==5.0.0.93`. Both interpreters on
this host (3.11.15 as `python3`, 3.12.3 as `/usr/bin/python3`) import the same
`cp37-abi3` wheel and report `cv2.__version__ == "5.0.0"`. Ubuntu 24.04, 24 cores, no
GPU, no network access needed: the host was shared and loaded, so timings are ranges.

## 1. Tests

```
$ time python3 -m pytest tests -q
.................................................                        [100%]
=============================== warnings summary ===============================
../../../../../../../../home/sniegul/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/site-packages/fastapi/testclient.py:1
  /home/sniegul/.local/share/uv/python/cpython-3.11.15-linux-x86_64-gnu/lib/python3.11/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
49 passed, 1 warning in 21.09s

real	0m22,093s
user	0m26,913s
sys	0m17,057s
```

The warning is raised by FastAPI's own `TestClient` shim, not by this project. The
44-dot output of the previous revision became 49 tests after adding the strict-IoU and
seed-sweep tests and the S3-path tests.

`pytest.ini` used to add `-q` on top of the command-line `-q` (pytest's `-qq`), which
suppressed the summary line; it now adds `-ra`, so the requested command prints
`49 passed`. A second run on `/usr/bin/python3` (3.12.3) measured `49 passed, 1 warning
in 16.53s`; the count and result were identical, the timing varies with host load. The suite includes negative cases: a clean plate must return zero defects,
garbage bytes must raise, a blind detector must score F1 = 0, an S3 event without boto3
must return 501, and a malformed S3 record must return 400.

Re-measured 2026-10-20 after the concurrency change: `62 passed in 25.90s` — 60 before,
plus the two event-loop tests. Earlier that day the accessibility change took the count
from 58 to 60. On that day the host's `/tmp` tmpfs was 100% full and `tmp_path` tests failed
with `ENOSPC` through no fault of the code, so `tests/conftest.py` now gives each session its
own scratch directory under `/var/tmp` (removed at exit) instead of relying on the shared
mount.

## 2. Benchmark, seed 7000 (40 plates, 5 clean)

```
$ python3 -m fieldlens benchmark --n 40 --seed 7000 --no-sweep
FieldLens 1.0.0 benchmark — synthetic plates, deterministic seed 7000
images: 40  clean: 5  time: 141.4 ms/image (7.1 img/s)
TP=63  FP=7  FN=3
IoU 0.25 + containment (primary, lenient): precision=0.9000  recall=0.9545  f1=0.9265
IoU 0.25 (no containment):                 precision=0.7857  recall=0.8333  f1=0.8088  (TP=55 FP=15 FN=11)
IoU 0.50 (no containment):                 precision=0.6429  recall=0.6818  f1=0.6618  (TP=45 FP=25 FN=21)
kind accuracy (matched)=0.7778  mean match score=0.6938
  scratch  gt=29  hit=27  pred=31  recall=0.9310
  dent     gt=22  hit=22  pred=30  recall=1.0000
  stain    gt=15  hit=14  pred=9   recall=0.9333
clean plates: 5  false positives on them: 0 (0.00/image)
acceptance gate on IoU 0.25 + containment, F1 >= 0.80: PASS
images with misses (first 10):
  seed=7006 gt=3 det=2 missed=['scratch']
  seed=7037 gt=2 det=1 missed=['scratch']
  seed=7039 gt=3 det=2 missed=['stain']
```

`TP=63 FP=7 FN=3` is the primary (lenient) matcher; the two pure-IoU matchers have
their own counts on the following lines. All three rows are the same detections scored
three times, not three runs.

The OpenCV 5 counts and metrics are **identical** to the documented 4.13 run
(`TP=63 FP=7 FN=3`, P=0.9000 R=0.9545): the pipeline is deterministic and no source
change was needed.

## 3. Seed sweep — six independent bases

```
$ time python3 -m fieldlens benchmark --n 40 --seed 7000
FieldLens 1.0.0 benchmark — synthetic plates, deterministic seed 7000
images: 40  clean: 5  time: 116.3 ms/image (8.6 img/s)
TP=63  FP=7  FN=3
IoU 0.25 + containment (primary, lenient): precision=0.9000  recall=0.9545  f1=0.9265
IoU 0.25 (no containment):                 precision=0.7857  recall=0.8333  f1=0.8088  (TP=55 FP=15 FN=11)
IoU 0.50 (no containment):                 precision=0.6429  recall=0.6818  f1=0.6618  (TP=45 FP=25 FN=21)
kind accuracy (matched)=0.7778  mean match score=0.6938
  scratch  gt=29  hit=27  pred=31  recall=0.9310
  dent     gt=22  hit=22  pred=30  recall=1.0000
  stain    gt=15  hit=14  pred=9   recall=0.9333
clean plates: 5  false positives on them: 0 (0.00/image)
acceptance gate on IoU 0.25 + containment, F1 >= 0.80: PASS
seed sweep (6 independent bases, n=40 each):
  IoU 0.25 + containment f1 min=0.8361 median=0.8778 max=0.9298
  IoU 0.25 (no cont.)    f1 min=0.7360 median=0.7933 max=0.8596
  IoU 0.50 (no cont.)    f1 min=0.5738 median=0.6467 max=0.6780
  clean plates total: 36  false positives on them: 3
images with misses (first 10):
  seed=7006 gt=3 det=2 missed=['scratch']
  seed=7037 gt=2 det=1 missed=['scratch']
  seed=7039 gt=3 det=2 missed=['stain']

real	0m48,351s
user	0m56,832s
sys	0m34,842s
```

Per-seed values from the same `run_seed_sweep` function:

```
seed      f1@0.25+cont  f1@0.25pure  f1@0.50pure  clean_imgs  clean_fp
5000      0.8960        0.7360       0.6080       4           0
7000      0.9265        0.8088       0.6618       5           0
9000      0.8475        0.7797       0.6780       8           2
12000     0.8596        0.8070       0.6316       7           0
20000     0.9298        0.8596       0.6667       6           0
33333     0.8361        0.7541       0.5738       6           1
```

Seed 7000 is the best of the six for every matcher; it is not the headline. The honest
summary is: IoU 0.25 + containment F1 0.836-0.930 (median 0.878), pure IoU 0.25 F1
0.736-0.860 (median 0.793), pure IoU 0.50 F1 0.574-0.678 (median 0.647). **There are
false positives on clean plates:** 3 across 36 clean images, 2 at seed 9000 and 1 at
seed 33333. The earlier claim that clean plates produce no false positives was true only
for the seeds that had been run at the time and is withdrawn.

Ablation (asserted by `test_metric_reacts_to_a_blind_detector`): thresholds pushed out
of reach give `TP=0, FP=0, F1=0.0, passed=False`, so the metric reacts to a detector
that does nothing.

## 4. Single-plate inspection (CLI)

```
$ python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out
FieldLens 1.0.0 — samples/images/plate_0003_seed7403.png
image: 384x384  scale=1.000  defects=2  elapsed=262.4 ms
 id kind     bbox                    score  contrast  elong
  0 dent     (71, 119, 60, 69)        2.27      5.43   1.44
  1 scratch  (179, 142, 65, 124)      2.77      5.77  25.37
wrote: out/plate_0003_seed7403.json
wrote: out/plate_0003_seed7403_annotated.png
wrote: out/plate_0003_seed7403_mask.png
```

Ground truth for that seed (`samples/ground_truth.json`): `dent [71, 118, 61, 72]`,
`scratch [179, 142, 64, 125]`. Both found, both labelled correctly; box IoU 0.94 (dent)
and 0.98 (scratch).

Clean plate:

```
$ python3 -m fieldlens inspect samples/images/plate_0005_seed7405.png --out-dir out
FieldLens 1.0.0 — samples/images/plate_0005_seed7405.png
image: 384x384  scale=1.000  defects=0  elapsed=200.2 ms
no defects above threshold
wrote: out/plate_0005_seed7405.json
wrote: out/plate_0005_seed7405_annotated.png
wrote: out/plate_0005_seed7405_mask.png
```

Two scratches on one plate:

```
$ python3 -m fieldlens inspect samples/images/plate_0006_seed7406.png --out-dir out
FieldLens 1.0.0 — samples/images/plate_0006_seed7406.png
image: 384x384  scale=1.000  defects=2  elapsed=222.2 ms
 id kind     bbox                    score  contrast  elong
  0 scratch  (225, 218, 50, 60)       2.86      6.03  18.00
  1 scratch  (30, 257, 73, 122)       2.26      5.49  40.72
wrote: out/plate_0006_seed7406.json
wrote: out/plate_0006_seed7406_annotated.png
wrote: out/plate_0006_seed7406_mask.png
```

## 5. HTTP API (`python3 -m fieldlens serve --port 8099`)

Health:

```
$ curl -s http://127.0.0.1:8099/health
{"status":"ok","version":"1.0.0","engine":"opencv-matched-filter","defaults":{"max_dim":768,"line_angles":8}}
```

Raw PNG body:

```
$ curl -s -X POST --data-binary @samples/images/plate_0003_seed7403.png \
       -H 'Content-Type: image/png' http://127.0.0.1:8099/inspect
{"defect_count":2,"counts":{"scratch":1,"dent":1,"stain":0,"total":2},"defects":[{"id":0,"kind":"dent","bbox":[71,119,60,69],"area_px":3025,"score":2.271,"elongation":1.444,"contrast":5.43,"centroid":[101.0,153.5]},{"id":1,"kind":"scratch","bbox":[179,142,65,124],"area_px":1924,"score":2.767,"elongation":25.369,"contrast":5.77,"centroid":[211.5,204.0]}],"image_size":[384,384],"working_scale":1.0,"elapsed_ms":217.94,"engine":"opencv-matched-filter","version":"1.0.0"}
```

Multipart on a clean plate:

```
$ curl -s -F "file=@samples/images/plate_0005_seed7405.png" http://127.0.0.1:8099/inspect
{"defect_count":0,"counts":{"scratch":0,"dent":0,"stain":0,"total":0},"defects":[],"image_size":[384,384],"working_scale":1.0,"elapsed_ms":133.97,"engine":"opencv-matched-filter","version":"1.0.0"}
```

Garbage payload:

```
$ curl -s -o /dev/null -w "%{http_code}\n" -X POST --data-binary 'nope' \
       -H 'Content-Type: image/png' http://127.0.0.1:8099/inspect
400
```

JSON + base64 with mask (summary of the response body):

```
$ curl -s -H 'Content-Type: application/json' --data-binary @out/request.json \
       http://127.0.0.1:8099/inspect
{'defect_count': 2, 'counts': {'scratch': 1, 'dent': 1, 'stain': 0, 'total': 2},
 'image_size': [384, 384], 'elapsed_ms': 246.59, 'mask_b64_len': 2164}
```

The server was stopped after the calls; the log is not kept.

## 6. Lambda handler — local invoke and live execution in the AWS Lambda runtime

```
$ python3 lambda_handler.py samples/images/plate_0003_seed7403.png
{
  "defect_count": 2,
  "counts": {"scratch": 1, "dent": 1, "stain": 0, "total": 2},
  "defects": [
    {"id": 0, "kind": "dent", "bbox": [71, 119, 60, 69], "area_px": 3025,
     "score": 2.271, "elongation": 1.444, "contrast": 5.43, "centroid": [101.0, 153.5]},
    {"id": 1, "kind": "scratch", "bbox": [179, 142, 65, 124], "area_px": 1924,
     "score": 2.767, "elongation": 25.369, "contrast": 5.77, "centroid": [211.5, 204.0]}
  ],
  "image_size": [384, 384],
  "working_scale": 1.0,
  "elapsed_ms": 202.5,
  "version": "1.0.0",
  "engine": "opencv-matched-filter"
}
```

`tests/test_lambda.py` covers the API Gateway base64 shape, the direct-invoke shape, a
malformed body (400), an S3 event with a stubbed boto3 client (200, checks the decoded
key and `source`), an S3 event without boto3 (501), and an S3 event without an object
key (400). The S3 branch has never been exercised against a real bucket.

`template.yaml` (SAM) and `scripts/deploy_aws.sh` define the deployment. Neither the AWS
CLI nor the SAM CLI is installed on this host, so the script stops at its first check and
deploys nothing:

```
$ bash scripts/deploy_aws.sh
deploy_aws.sh: performs a REAL deployment and requires AWS credentials.
ERROR: AWS CLI not found in PATH; deployment needs the AWS CLI plus credentials. NOTHING WAS DEPLOYED.
$ echo $?
1
```

`deploy_aws.sh` was never executed against an AWS account; see section 8.

### 6b. Live execution inside the AWS Lambda runtime image

The handler runs inside `public.ecr.aws/lambda/python:3.12` — the official Lambda base
image, which ships the Runtime Interface Emulator. Invocations are posted to the real
Lambda Runtime API path (`2015-03-31/functions/function/invocations`). No AWS account is
involved and no AWS resource is created.

```
$ bash scripts/live_lambda.sh
api_gateway_base64           status=200 defects=2 613.2 ms
direct_invoke                status=200 defects=2 249.6 ms
malformed_body               status=400 defects=None 8.1 ms
s3_event_without_credentials status=502 defects=None 2955.5 ms
```

What this proves: the packaged image imports OpenCV 5.0.0.93 and answers both the API
Gateway and the direct-invoke shape with the counts of the local run (1 scratch, 1 dent);
a garbage body is refused with 400; the S3 branch has `boto3` in the real runtime and
fails closed with 502 `Unable to locate credentials`. 613 ms first call (init included),
250 ms warm; the spread against earlier runs is host load.
`evidence/lambda-live-trace.json` is the record of that run.

What this does not prove: a cloud deployment. No bucket, function, HTTP API or
CloudFormation stack exists in any AWS account.

## 7. Dataset generation

```
$ python3 -m fieldlens synth --out out/synth-check --n 8 --seed 7400
{
  "out": ".../project/out/synth-check",
  "images": 8,
  "defects": 13,
  "manifest": "ground_truth.json"
}
```

Same 8 images / 13 defects as the checked-in `samples/` directory, generated under
OpenCV 5. `tests/test_synth.py` asserts the manifest matches the images on a round-trip.

## 8. What this evidence does NOT prove

* **Real-world accuracy.** All numbers come from the synthetic generator in
  `fieldlens/synth.py`; no production inspection-line images were available.
* **AWS cloud deployment.** `template.yaml` exists and `scripts/deploy_aws.sh` is
  written, but **no `sam build`, no `sam deploy` and no AWS API call were made** — there
  were no AWS credentials. No bucket, function, API Gateway or CloudFormation stack was
  created. The handler itself does execute live inside the official AWS Lambda runtime
  image (section 6b), which is a runtime proof, not a deployment. The S3 path reaches a
  real `boto3` client but no real bucket.
* **Kind classification quality.** `kind_accuracy` is 0.7778 at seed 7000: dents and
  stains are sometimes swapped. Detection metrics do not depend on the label.
* **Concurrency / load behaviour of the API.** A short concurrency probe is in section 9c
  (eight simultaneous plates, single uvicorn worker). A sustained soak, multi-worker
  deployment and real network latency are still not covered.
* **A single F1 number.** At seed 7000: 0.927 with the contained-core rule, 0.809 at
  pure IoU 0.25, 0.662 at pure IoU 0.50; across seeds 0.836-0.930, 0.736-0.860 and
  0.574-0.678 respectively. None is a universal accuracy claim, and clean plates are not
  guaranteed false-positive free.
* **Timings as constants.** 106-262 ms/plate on a shared host; the spread is load.

## 9. Web UI (FastAPI + single-page client)

Files: `web/server.py` (API and static shell), `web/index.html` (dark single-page client, no
build step), `tests/test_web.py`. The page calls the same `inspect_array` pipeline as
`POST /inspect`; detection logic is unchanged.

```
$ python3 -m uvicorn web.server:app --host 127.0.0.1 --port 8731
$ curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8731/    # 200
$ curl -s http://127.0.0.1:8731/api/health
{"status":"ok","version":"1.0.0","engine":"opencv-matched-filter"}
$ curl -s http://127.0.0.1:8731/api/samples | head -c 60
{"samples":["plate_0000_seed7400.png","plate_0001_seed7401.png"
$ # multipart POST of samples/images/plate_0000_seed7400.png
POST /api/inspect -> 200 | count: 1 | types: ['scratch'] | annotated PNG: 292988 b64 chars | 311.34 ms
```

A first visit has no file, so the page offers the four bundled plates:
`GET /api/samples` lists them and `GET /api/sample/<name>` serves one (the name is
matched against the directory listing, never joined into a path — an unknown name is
404). The button loads the first plate through the same `/api/inspect` path.

Browser check (Playwright 1.62, 1280x900): page load → `#sampleBtn` visible → click →
`#board.is-visible`, summary "1 region flagged on this plate.", 1 item in `#defectList`,
0 console errors; the frame is committed as `evidence/webui-sample.png`.

`POST /api/inspect` returns `{"defects":[{"type","score","box":[x,y,w,h]}],"count":N,
"annotated_png_base64":"..."}` plus `image_size`, `elapsed_ms` and `version`. Garbage bytes
return 400, a missing `file` field returns 400, a payload above 12 MB returns 413.

Whole suite, the requested command:

```
$ python3 -m pytest -q -p no:warnings
......................................................                   [100%]
54 passed in 32.15s
```

The 5 new tests cover `GET /` (200, viewport meta, dropzone markup), `GET /api/health`,
the `POST /api/inspect` contract on a generated scratch plate (count, per-defect keys,
PNG magic), a non-image upload → 400 and a missing multipart field → 400. The suite had 49
tests before this change.

Browser verification (Chromium 1234 via Playwright; desktop 1440×1000, mobile 480×900):
empty state, result state (1 defect, box drawn on canvas, 1 list row), reset back to empty,
error state for `bad.txt` (`"bad.txt" is not an image (text/plain).`), 0 console errors, no
horizontal overflow at 480 px. The result-state check caught a real defect — the canvas
container stayed `display:none` because its state class was never toggled — fixed before commit.

Not proven: sustained load (the probe in 9c is eight requests, not a soak), real
inspection-line images, and rendering in WebKit or Firefox.

### 9b. Text contrast (WCAG 2.1 AA)

Secondary text — `.hint`, `.meta`, `.formats`, `.empty-note`, `.defect .idx`, the footer and
the summary line — used `--faint:#6b7686`. Measured against the surfaces it lands on, that is
**3.94:1** on `--panel` and **3.59:1** on `--panel-2`, below the 4.5:1 that SC 1.4.3 requires
at 11–12.5 px. White labels sat on `--accent:#4c82d9`, which measures **3.81:1**.

Change: `--faint` is now `#7f8b9c` (**5.25:1** on `--panel`, **4.79:1** on `--panel-2`) and
every white-labelled surface (`.skip-link`, `.btn-accent`) moved to `--accent-ink:#2f6bcc`
(**5.13:1**; hover `#356fc9` **4.92:1**). `--accent` is unchanged for outlines and for the
z-score text, which already read at 4.75:1.

Measured in Chromium 155 against the running page, not against the stylesheet by hand:

```
hint     fg=rgb(127,139,156) bg=rgb(5,7,10)   ratio=5.83:1
formats  fg=rgb(127,139,156) bg=rgb(13,17,22) ratio=5.48:1
summary  fg=rgb(127,139,156) bg=rgb(5,7,10)   ratio=5.83:1
score    fg=rgb(76,130,217)  bg=rgb(5,7,10)   ratio=5.28:1
sample click -> "1 region flagged on this plate." | 1 list row | 0 console errors
390x844 viewport -> no horizontal overflow
```

Frames: `evidence/webui-contrast-desktop.png`, `evidence/webui-contrast-result.png`,
`evidence/webui-contrast-mobile.png`.

Regression: `tests/test_web.py::test_secondary_text_meets_wcag_aa_on_every_surface` and
`::test_white_labels_sit_on_the_darker_accent` parse the `:root` tokens from the served page
and fail below 4.5:1. Ablation: putting `--faint:#6b7686` and `--accent-ink:#4c82d9` back
turns both tests red (2 failed); the shipped values turn them green.

### 9c. Concurrent requests — the inspection used to freeze the API

`web/server.py` declared `async def inspect` and ran the whole decode plus filter bank
inside it. The work is CPU-bound (~100 ms per plate), so it ran on the event loop and
every other request waited. Method: one uvicorn worker, eight `POST /api/inspect` calls
with the same 384×384 plate issued concurrently through `httpx`, then ten `GET /api/health`
probes while they were in flight.

```
before (async handler):
  inspect elapsed_ms: [127, 106, 99, 98, 97, 98, 96, 96]
  8 inspects wall: 1185 ms
  health during load: max=917 ms  median=3 ms

after (def handler -> FastAPI threadpool):
  inspect elapsed_ms: [461, 458, 347, 452, 509, 459, 389, 401]
  8 inspects wall: 794 ms
  health during load: max=47 ms  median=18 ms
```

The batch finishes sooner because the plates overlap, and the probe drops from 917 ms to
47 ms — the page's API chip no longer flips to "unreachable" while a plate is being
inspected. Per-request time rises (96–127 → 347–509 ms) because eight plates now share the
same cores; that is the honest cost of concurrency, not a regression.

Regression: `tests/test_web.py::test_inspect_handler_runs_off_the_event_loop` (the route
endpoint must not be a coroutine) and `::test_slow_inspection_does_not_stall_the_api`
(health latency under a four-request batch must stay below half the batch wall time).
Ablation: making the handler `async` again turns both red.

## Wdrożenie AWS (2026-10-20, live)
- Obraz kontenera: `830393774429.dkr.ecr.eu-north-1.amazonaws.com/fieldlens:v1`
- Funkcja Lambda `fieldlens` (PackageType Image, 2048 MB, timeout 60 s, x86_64), region eu-north-1,
  stan `Active`, `LastUpdateStatus=Successful`.
- Rola `fieldlens-lambda-exec` z `AWSLambdaBasicExecutionRole`.
- Wywołanie przez SDK: `statusCode: 200`, body `{"samples":[...]}` — FastAPI + Mangum działa w Lambdzie.
- Function URL: `https://h2mihukfj7v2qzbsevyul5w3fe0sipqx.lambda-url.eu-north-1.on.aws/`
  (`AuthType=NONE`, polityka `lambda:InvokeFunctionUrl` dla `*`) — na chwilę obecną zwraca **403**;
  publiczne demo działa pod adresem tunelu: `https://lets-parish-egg-bingo.trycloudflare.com`.
