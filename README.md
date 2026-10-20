# FieldLens — classical-CV surface inspection

FieldLens finds **scratches, dents and stains** on machined plates using OpenCV only —
no trained model, no GPU, no network. It runs as a CLI, as a FastAPI service, or as an
AWS Lambda handler.

The evaluation is a deterministic synthetic dataset with pixel-accurate ground truth, so
the numbers below can be reproduced from scratch on any machine:

```
precision 0.900   recall 0.955   F1 0.927      (40 plates, seed 7000)
0 false positives on 5 clean plates
168 ms per 384x384 plate on a loaded 24-core host, Python 3.12 + OpenCV 4.13
```

## What it does

```
image -> flat field (illumination removed) -> matched-filter bank
      -> robust z-gating -> connected components -> shape/contrast filtering
      -> JSON + annotated PNG + binary mask
```

The filter bank is the interesting part:

| channel | kernel | catches |
|---|---|---|
| `log3`, `log6` | Laplacian of Gaussian, sigma 3 / 6 | thin edges, scratch flanks, dent rims |
| `dog` | difference of Gaussians 6/14 | mid-size blobs |
| `disk` | center-surround disk, r 16 / 40 | low-contrast stains and dents (plateau matched filter) |
| `line` | 8 orientation-steered anisotropic Gaussians | scratches in any direction |

Each channel is divided by its own RMS on that image, so the thresholds are in
"just at the noise floor" units and do not depend on exposure. Regions above threshold
are described (area, elongation, extent, channel mix) and only then accepted and
labelled, which is what keeps brushed-metal texture from producing defects.

## Install

```bash
python3 -m pip install -r requirements.txt     # numpy, opencv-python-headless, fastapi, uvicorn
```

Nothing else is required. Python 3.12 and OpenCV 4.13 were used for the evidence run.

> On the machine used for the evidence run, `python3` in `PATH` is a user-local shim
> without numpy; the interpreter that has OpenCV/numpy is `/usr/bin/python3`. If your
> `python3` lacks numpy, run the commands below with `/usr/bin/python3` or set
> `PYTHON=/usr/bin/python3 ./demo.sh`.

## Run

```bash
# one plate -> JSON + annotated PNG + mask PNG (written to ./out)
python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out

# machine-readable only
python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --json --no-write

# evaluation on 40 generated plates; exit code 1 if F1 < 0.80
python3 -m fieldlens benchmark --n 40

# HTTP API
python3 -m fieldlens serve --port 8099
curl -X POST --data-binary @samples/images/plate_0003_seed7403.png \
     -H 'Content-Type: image/png' http://127.0.0.1:8099/inspect

# regenerate the synthetic dataset (images + ground_truth.json)
python3 -m fieldlens synth --out samples --n 8 --seed 7400

# tests (44, ~30 s)
python3 -m pytest tests -q
```

`./demo.sh` runs the whole loop in one command.

### API

`POST /inspect` accepts three encodings:

| input | example |
|---|---|
| raw bytes | `Content-Type: image/png`, body = file |
| JSON | `{"image_base64": "...", "include_mask": true}` |
| multipart | `-F file=@plate.png` |

Response:

```json
{
  "defect_count": 2,
  "counts": {"scratch": 1, "dent": 1, "stain": 0, "total": 2},
  "defects": [
    {"id": 0, "kind": "dent", "bbox": [71, 119, 60, 69], "area_px": 3025,
     "score": 2.271, "elongation": 1.444, "contrast": 5.43, "centroid": [101.0, 153.5]}
  ],
  "image_size": [384, 384],
  "elapsed_ms": 179.4,
  "engine": "opencv-matched-filter",
  "version": "1.0.0"
}
```

`include_mask` adds `mask_png_b64`, `include_annotated` adds `annotated_png_b64`.

### Lambda

`lambda_handler.handler` handles API Gateway proxy events and direct invokes with
`{"image_base64": ...}`. S3 notifications return **501** on purpose: fetching from S3
would need `boto3`, which is not a dependency of this package. The `Dockerfile` builds
the Lambda container image (`CMD ["lambda_handler.handler"]`); the image was **not**
built in this session.

## The synthetic benchmark

`fieldlens.synth` renders plates deterministically from a seed: illumination gradient,
vignetting, brushed/speckled/cast texture, sensor noise, and 0-3 defects drawn with known
geometry. Ground truth is measured from the **drawn mask**, not from the drawing
parameters, so the benchmark cannot be gamed by geometry bookkeeping.

```
python3 -m fieldlens benchmark --n 40
TP=63  FP=7  FN=3
precision=0.9000  recall=0.9545  f1=0.9265
```

Across seeds 5000 / 7000 / 9000: F1 0.896 / 0.927 / 0.848 (all above the 0.80 gate).
Per-class recall at seed 7000: scratch 0.93, dent 1.00, stain 0.93.

Scoring is one-to-one greedy matching. A detection counts as a hit when IoU >= 0.25, or
when it is *contained* in the ground-truth box (containment >= 0.6 and at most 3x its
area) — thin scratches have an unfavourable area/box ratio and a strict IoU-0.5 rule
would punish correct detections. The containment rule is deliberately generous; it is
stated here so the numbers are not over-read.

## Limitations (measured, not guessed)

* **Synthetic domain only.** The benchmark is generated by the same code that defines
  the task. No real inspection-line images were available in this environment; the
  detector has not been validated against a customer dataset.
* **Kind labels are heuristic.** `kind_accuracy` is ~0.78: dents and stains are often
  confused when a stain is compact. Detection metrics (P/R/F1) do not depend on labels.
* **Faint, short scratches are missed.** A 1 px-wide, low-contrast scratch that only
  produces a few above-threshold pixels falls under the minimum length and is dropped
  (3 misses out of 40 plates at seed 7000).
* **Defects touching the frame edge are ignored** (`reject_border`), because convolution
  borders otherwise invent structures — one 171 px false stain was measured at `x=0`
  before this rule. An edge defect is therefore out of scope.
* **Contrast only.** The pipeline converts to grayscale; a stain that differs from the
  plate only in hue is invisible.
* **No rotation/orientation prior beyond the 8 line angles** (22.5 deg steps). Curved
  scratches longer than ~150 px fragment into several boxes.
* **Speed** is ~170-250 ms per 384x384 plate in pure Python+OpenCV on a loaded 24-core
  host (single image, no batching). Larger inputs are downscaled to 768 px on the long
  side before analysis, so reported boxes are rescaled back but sub-pixel detail is lost.
* **No persistence, no auth, no tenant isolation** in the API — it is a stateless
  single-endpoint service.

## Repository layout

```
fieldlens/        library: io, preprocess, detect, synth, benchmark, annotate, api, cli
lambda_handler.py AWS Lambda entry point
tests/            44 unit/integration tests, including negative cases and an ablation
samples/          8 generated plates + ground_truth.json (demo input)
Dockerfile        Lambda container image
ARCHITECTURE.md   data flow, decisions, OpenCV 5 migration plan
EVIDENCE.md       raw command output of the runs quoted above
```
