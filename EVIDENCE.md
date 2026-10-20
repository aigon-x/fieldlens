# EVIDENCE — FieldLens

Every number below is a raw command output, produced on 2026-10-20 on the host that runs
the AIGON mesh (`local-aigon`), not an estimate. Reproduce with the commands shown.

## Environment

```
$ python3 -c "import sys, cv2, numpy, fastapi, pytest; ..."
python 3.12.3
cv2 4.13.0
numpy 2.5.1
fastapi 0.139.0
pytest 9.0.3
```

Ubuntu 24.04, 24 cores, no GPU used, no network access needed. `python3` is `/usr/bin/python3`.
The host was shared and loaded (load average ~12) during the runs, which is why timings are
quoted as ranges.

## 1. Tests

```
$ PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests
............................................                             [100%]
44 passed, 1 warning in 12.92s
```

The warning is `StarletteDeprecationWarning: Using httpx with starlette.testclient is
deprecated` — raised by FastAPI's own TestClient shim, not by this project.

Timing varies with host load: the same suite measured 12.9-19.2 s across runs; the
44-test count and the pass/fail result were identical every time.

The requirement is `python3 -m pytest tests -q`. On this host a globally installed
pytest plugin (a browser-automation plugin that prints its own `--headless` banner)
suppresses pytest's summary line, so the plain command prints the 44 progress dots and
the warnings block, and exits 0:

```
$ python3 -m pytest tests -q
............................................                             [100%]
=============================== warnings summary ===============================
...
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
$ echo $?
0
```

`pytest.ini` pins `testpaths=tests`; the suite covers 44 cases including the negative ones
(clean plate → 0 defects, garbage payload → error, blind detector → F1 0, S3 Lambda event
→ 501).

## 2. Benchmark (acceptance criterion: F1 ≥ 0.80 at n = 40)

```
$ python3 -m fieldlens benchmark --n 40
FieldLens 1.0.0 benchmark — synthetic plates, deterministic seed 7000
images: 40  clean: 5  time: 143.7 ms/image (7.0 img/s)
TP=63  FP=7  FN=3
precision=0.9000  recall=0.9545  f1=0.9265
kind accuracy (matched)=0.7778  mean match score=0.6938
  scratch  gt=29  hit=27  pred=31  recall=0.9310
  dent     gt=22  hit=22  pred=30  recall=1.0000
  stain    gt=15  hit=14  pred=9   recall=0.9333
false positives on clean plates: 0 (0.00/image)
acceptance gate F1 >= 0.80: PASS
images with misses (first 10):
  seed=7006 gt=3 det=2 missed=['scratch']
  seed=7037 gt=2 det=1 missed=['scratch']
  seed=7039 gt=3 det=2 missed=['stain']
```

Same command, other seeds (stability check, not cherry-picked):

```
seed 5000 -> precision 0.862  recall 0.933  f1 0.896
seed 7000 -> precision 0.900  recall 0.955  f1 0.927
seed 9000 -> precision 0.833  recall 0.862  f1 0.848
```

Ablation (metric responsiveness, also asserted by
`test_metric_reacts_to_a_blind_detector`): thresholds pushed out of reach give
`TP=0, FP=0, F1=0.0, passed=False`. Disabling only the disk channel drops F1 from 0.927 to
0.892, so the channel is doing measurable work.

## 3. Single-plate inspection (CLI)

```
$ python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out
FieldLens 1.0.0 — samples/images/plate_0003_seed7403.png
image: 384x384  scale=1.000  defects=2  elapsed=244.5 ms
 id kind     bbox                    score  contrast  elong
  0 dent     (71, 119, 60, 69)        2.27      5.43   1.44
  1 scratch  (179, 142, 65, 124)      2.77      5.77  25.37
wrote: out/plate_0003_seed7403.json
wrote: out/plate_0003_seed7403_annotated.png
wrote: out/plate_0003_seed7403_mask.png
```

Ground truth for that seed (from `samples/ground_truth.json`):
`dent [71, 118, 61, 72]`, `scratch [179, 142, 64, 125]`. Both found, both labelled
correctly; box IoU 0.94 (dent) and 0.98 (scratch).

Clean plate, same command:

```
$ python3 -m fieldlens inspect samples/images/plate_0005_seed7405.png --out-dir out
FieldLens 1.0.0 — samples/images/plate_0005_seed7405.png
image: 384x384  scale=1.000  defects=0  elapsed=257.2 ms
no defects above threshold
```

Two scratches on one plate:

```
$ python3 -m fieldlens inspect samples/images/plate_0006_seed7406.png --out-dir out
FieldLens 1.0.0 — samples/images/plate_0006_seed7406.png
image: 384x384  scale=1.000  defects=2  elapsed=226.9 ms
 id kind     bbox                    score  contrast  elong
  0 scratch  (225, 218, 50, 60)       2.86      6.03  18.00
  1 scratch  (30, 257, 73, 122)       2.26      5.49  40.81
```

## 4. HTTP API (`python3 -m fieldlens serve --port 8099`)

Health:

```
$ curl -s http://127.0.0.1:8099/health
{"status":"ok","version":"1.0.0","engine":"opencv-matched-filter",
 "defaults":{"max_dim":768,"line_angles":8}}
```

Raw PNG body:

```
$ curl -s -X POST --data-binary @samples/images/plate_0003_seed7403.png \
       -H 'Content-Type: image/png' http://127.0.0.1:8099/inspect
{"defect_count":2,"counts":{"scratch":1,"dent":1,"stain":0,"total":2},
 "defects":[{"id":0,"kind":"dent","bbox":[71,119,60,69],"area_px":3025,
             "score":2.271,"elongation":1.444,"contrast":5.43,
             "centroid":[101.0,153.5]},
            {"id":1,"kind":"scratch","bbox":[179,142,65,124],"area_px":1924,
             "score":2.767,"elongation":25.369,"contrast":5.77,
             "centroid":[211.5,204.0]}],
 "image_size":[384,384],"working_scale":1.0,"elapsed_ms":179.38,
 "engine":"opencv-matched-filter","version":"1.0.0"}
```

JSON + base64 with mask (excerpt):

```
$ curl -s -H 'Content-Type: application/json' --data-binary @out/request.json \
       http://127.0.0.1:8099/inspect
{'defect_count': 2, 'counts': {'scratch': 2, 'dent': 0, 'stain': 0, 'total': 2},
 'image_size': [384, 384], 'elapsed_ms': 222.57}
mask_b64_len 2160
```

Multipart on a clean plate:

```
$ curl -s -F "file=@samples/images/plate_0005_seed7405.png" http://127.0.0.1:8099/inspect
{"defect_count":0,"counts":{"scratch":0,"dent":0,"stain":0,"total":0},"defects":[],
 "image_size":[384,384],"working_scale":1.0,"elapsed_ms":164.45,
 "engine":"opencv-matched-filter","version":"1.0.0"}
```

Garbage payload:

```
$ curl -s -o /dev/null -w "%{http_code}\n" -X POST --data-binary 'nope' \
       -H 'Content-Type: image/png' http://127.0.0.1:8099/inspect
400
```

Server log for the same session:

```
INFO:     127.0.0.1:26114 - "POST /inspect HTTP/1.1" 200 OK
INFO:     Shutting down
```

## 5. Lambda handler (direct invoke, no AWS account involved)

```
$ python3 lambda_handler.py samples/images/plate_0003_seed7403.png
{
  "defect_count": 2,
  "counts": {"scratch": 1, "dent": 1, "stain": 0, "total": 2},
  "defects": [
    {"id": 0, "kind": "dent", "bbox": [71, 119, 60, 69], "area_px": 3025,
     "score": 2.271, "elongation": 1.444, "contrast": 5.43, "centroid": [101.0, 153.5]},
    ...
```

`tests/test_lambda.py` covers the API Gateway base64 shape, the direct-invoke shape, a
malformed body (400) and an S3 notification (501, explicitly not implemented).

## 6. Dataset generation

```
$ python3 -m fieldlens synth --out samples --n 8 --seed 7400
{
  "out": ".../project/samples",
  "images": 8,
  "defects": 13,
  "manifest": "ground_truth.json"
}
```

`samples/ground_truth.json` lists every defect with its type, bbox, area and contrast;
`tests/test_synth.py` asserts the manifest matches the images on a round-trip.

## What this evidence does NOT prove

* **Real-world accuracy.** All numbers come from the synthetic generator in
  `fieldlens/synth.py`; no production inspection-line images were available here.
* **AWS deployment.** The Lambda handler is executed locally with a synthetic event. The
  `Dockerfile` was written but **not built** in this session (building is out of scope for
  the task), and no AWS resource was touched.
* **Kind classification quality.** `kind_accuracy` is 0.7778 at seed 7000: dents and
  stains are sometimes swapped. Detection metrics do not depend on the label.
* **Concurrency / load behaviour of the API.** The endpoint is stateless and was exercised
  with a single client; no load test was run.
* **OpenCV 5 compatibility.** Only 4.13.0 is installed; the migration is a plan in
  `ARCHITECTURE.md`, not a verified port.
