# FieldLens — classical-CV surface inspection

FieldLens finds **scratches, dents and stains** on machined plates using OpenCV only —
no trained model, no GPU, no network. It runs as a CLI, as a FastAPI service, or as an
AWS Lambda handler.

The evaluation is a deterministic synthetic dataset with pixel-accurate ground truth, so
the numbers below can be reproduced from scratch on any machine:

```
precision 0.900   recall 0.955   F1 0.927   (IoU 0.25 + contained core, 40 plates, seed 7000)
precision 0.786   recall 0.833   F1 0.809   (same detections, IoU 0.25, no containment)
precision 0.643   recall 0.682   F1 0.662   (same detections, IoU 0.50, no containment)
F1 over 6 independent seeds: 0.836-0.930 / 0.736-0.860 / 0.574-0.678
                             (medians 0.878 / 0.793 / 0.647, same order as above)
clean-plate false positives: 3 on 36 clean plates across those seeds (not zero)
106-222 ms per 384x384 plate (wall clock on a shared host), Python 3.11/3.12 + OpenCV 5.0.0
```

Seed 7000 is a single dataset, not the headline: the seed range above is the honest
summary. The first row is an auxiliary lenient rule (a detection contained in the
ground-truth box also counts) because thin scratches have an unfavourable area/box
ratio. The two pure-IoU rows are the conventional detection numbers: **F1 0.809 at
IoU 0.25 and 0.662 at IoU 0.50** on seed 7000. All three are printed by every run.

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

Nothing else is required. The evidence run used `python3` 3.11.15 and `/usr/bin/python3`
3.12.3; both report `cv2.__version__ == 5.0.0` from the pinned wheel
`opencv-python-headless==5.0.0.93`. If your interpreter lacks OpenCV, install the
requirements or set `PYTHON=/path/to/python ./demo.sh`.

## Run

```bash
# one plate -> JSON + annotated PNG + mask PNG (written to ./out)
python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out

# machine-readable only
python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --json --no-write

# evaluation on 40 generated plates; exit code 1 if lenient F1 < 0.80
python3 -m fieldlens benchmark --n 40

# HTTP API + web inspector
python3 -m fieldlens serve --port 8099
# open http://127.0.0.1:8099/ and press "Inspect a sample plate" — no file needed
curl -X POST --data-binary @samples/images/plate_0003_seed7403.png \
     -H 'Content-Type: image/png' http://127.0.0.1:8099/api/inspect

# regenerate the synthetic dataset (images + ground_truth.json)
python3 -m fieldlens synth --out samples --n 8 --seed 7400

# tests (60, ~40 s)
python3 -m pytest tests -q
```

`./demo.sh` runs the whole loop in one command.

The inspector is keyboard-operable (dropzone, sample button, keyboard focus rings) and its
secondary text meets WCAG AA: faint labels measure 5.25:1 on the panel colour, the
white-on-accent buttons 5.13:1, and `tests/test_web.py` fails the build if either drops
below 4.5:1.

### API

`POST /api/inspect` accepts three encodings:

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

`lambda_handler.handler` handles API Gateway proxy events, direct invokes with
`{"image_base64": ...}`, and S3 `ObjectCreated` notifications. The S3 path reads the
object with `boto3` (bundled in the AWS Lambda Python runtime; a local interpreter
without it returns **501** with an explicit message, never a silent success).

`template.yaml` is an AWS SAM template with the function (`python3.12`, 2048 MB,
30 s timeout, `lambda_handler.handler`), an HTTP API `POST /inspect`, and an S3 trigger
for `.png` uploads to the generated bucket. `scripts/deploy_aws.sh` performs a real
`sam build` + `sam deploy` and stops with an explicit error when AWS credentials are
deployed. **Live deployment (2026-10-20):** Lambda `fieldlens` (container image, 2048 MB, 60 s, eu-north-1) behind API Gateway HTTP API `873vdlij6g`; public demo: https://873vdlij6g.execute-api.eu-north-1.amazonaws.com/

## The synthetic benchmark

`fieldlens.synth` renders plates deterministically from a seed: illumination gradient,
vignetting, brushed/speckled/cast texture, sensor noise, and 0-3 defects drawn with known
geometry. Ground truth is measured from the **drawn mask**, not from the drawing
parameters, so the benchmark cannot be gamed by geometry bookkeeping.

```
python3 -m fieldlens benchmark --n 40
TP=63  FP=7  FN=3
IoU 0.25 + containment (primary, lenient): precision=0.9000  recall=0.9545  f1=0.9265
IoU 0.25 (no containment):                 precision=0.7857  recall=0.8333  f1=0.8088  (TP=55 FP=15 FN=11)
IoU 0.50 (no containment):                 precision=0.6429  recall=0.6818  f1=0.6618  (TP=45 FP=25 FN=21)
```

Every run also sweeps six independent seed bases (40 plates each, ~48 s):

```
seed      f1@0.25+cont  f1@0.25pure  f1@0.50pure  clean_imgs  clean_fp
5000      0.8960        0.7360       0.6080       4           0
7000      0.9265        0.8088       0.6618       5           0
9000      0.8475        0.7797       0.6780       8           2
12000     0.8596        0.8070       0.6316       7           0
20000     0.9298        0.8596       0.6667       6           0
33333     0.8361        0.7541       0.5738       6           1
```

Summary: IoU 0.25 + containment F1 0.836-0.930 (median 0.878), pure IoU 0.25 F1
0.736-0.860 (median 0.793), pure IoU 0.50 F1 0.574-0.678 (median 0.647), and 3 false
positives on 36 clean plates. Per-class recall at seed 7000: scratch 0.93, dent 1.00,
stain 0.93.

Scoring is one-to-one greedy matching under three rules: **IoU 0.25 + containment**
(a detection contained in the ground-truth box also counts, containment >= 0.6 and at
most 3x its area), **IoU 0.25** (no containment) and **IoU 0.50** (no containment). The
containment rule favours thin scratches whose pixel area is small relative to their
bounding box. Quote the pure-IoU numbers unless the containment rule is stated.

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
* **Speed** is 106-262 ms per 384x384 plate in pure Python+OpenCV on a shared 24-core
  host (single image, no batching); the spread is host load, not a fixed constant.
  Larger inputs are downscaled to 768 px on the long side before analysis, so reported
  boxes are rescaled back but sub-pixel detail is lost.
* **The headline depends on the matcher.** At seed 7000, pure IoU 0.25 F1 is 0.809 and
  pure IoU 0.50 F1 is 0.662, not the 0.927 of the contained-core rule. The gap comes
  from thin scratches penalised by box IoU, but it is real and all three are reported.
* **No persistence, no auth, no tenant isolation** in the API — it is a stateless
  single-endpoint service.

## Repository layout

```
fieldlens/        library: io, preprocess, detect, synth, benchmark, annotate, api, cli
lambda_handler.py AWS Lambda entry point (HTTP API, direct invoke, S3 via boto3)
template.yaml     AWS SAM template: function, HTTP API, S3 trigger
scripts/          deploy_aws.sh (real deployment; stops without AWS credentials)
tests/            49 unit/integration tests, including negative cases and an ablation
samples/          8 generated plates + ground_truth.json (demo input)
Dockerfile        Lambda container image
ARCHITECTURE.md   data flow, decisions, verified OpenCV 5 behaviour
EVIDENCE.md       raw command output of the runs quoted above
```
