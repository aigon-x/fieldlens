# FieldLens

**Classical-CV visual inspection for scratches, dents and stains — no trained model, no GPU, no network.**

## Elevator pitch

FieldLens turns a single photo of a machined plate into a defect report in under a second,
using nothing but OpenCV. Five matched-filter channels (two Laplacian-of-Gaussian scales,
a difference-of-Gaussians blob detector, a center-surround disk for faint stains, and eight
orientation-steered line kernels for scratches) are standardised against each image's own
noise floor, so the same thresholds work on a bright and a dull plate. It runs as a CLI,
as an HTTP service, and as an AWS Lambda handler, and it ships with a deterministic
synthetic benchmark with pixel-accurate ground truth. At seed 7000 it measures
**F1 0.809 at IoU 0.25 and F1 0.662 at IoU 0.50** (no containment rule), plus 0.927
when a detection contained in the ground-truth box is also accepted. Over six
independent seed bases the pure-IoU F1 ranges are 0.736-0.860 at IoU 0.25 and
0.574-0.678 at IoU 0.50. Clean plates are not guaranteed false-positive free: 3 false
positives were measured on 36 clean plates across those seeds. All three matchers and
the whole seed range are printed by every benchmark run.

## Inspiration

Visual inspection is the part of manufacturing that still eats human attention: someone
stands at the end of a line and looks for a 1 mm scratch in brushed metal under changing
light. The commercial answers are either expensive turnkey machines or a deep-learning
stack that needs thousands of labelled defects per part number — data a small shop never
has. We wanted the opposite: a model-free baseline that works on day one, runs on the CPU
already sitting next to the conveyor, and fails in ways you can explain to an operator
("the contrast is below 6 gray levels, so it is below the reporting floor").

The OpenCV AI Competition's requirement of real OpenCV use pushed us toward the classical
toolbox we would otherwise skip in 2026 — and it turned out that careful matched filtering
plus disciplined statistics goes a long way.

## What it does

Given an image (path, bytes, base64 or multipart), FieldLens:

1. **Normalises** — converts to grayscale, caps the working resolution at 768 px, removes
   sensor noise (median + edge-preserving bilateral) and applies CLAHE.
2. **Flattens illumination** — subtracts an illumination surface estimated as a small
   median on a 1/8-scale copy of the image. That detail matters: a full-resolution median
   narrower than the defect follows the defect itself and erases it.
3. **Applies a matched-filter bank** — Laplacian-of-Gaussian at sigma 3 and 6, a
   difference-of-Gaussians for mid-size blobs, a center-surround disk filter (r 16/40) for
   low-contrast stains and dents, and eight rotated anisotropic Gaussians for scratches.
4. **Gates statistically** — every channel is divided by its own RMS on that image, then
   thresholded in sigma units; morphology closes gaps and removes specks.
5. **Describes and filters** — each component is measured (area, elongation, extent,
   channel mix) before acceptance, so brushed-metal texture cannot masquerade as a defect.
6. **Labels and reports** — scratch / dent / stain, bounding boxes in original pixel
   coordinates, contrast in noise units, a binary mask, and an annotated PNG.

Outputs: JSON, annotated image, mask. Same engine behind `POST /inspect` and behind
`lambda_handler.handler`.

## How we built it

* **Pure Python + OpenCV 5 + numpy.** No model weights, no GPU, no network calls. The
  pinned engine is `opencv-python-headless==5.0.0.93` (`cv2.__version__ == "5.0.0"`); the
  Lambda image is `public.ecr.aws/lambda/python:3.12` plus that requirement.
* **The benchmark came first.** `fieldlens/synth.py` renders deterministic plates from a
  seed — illumination gradient, vignetting, brushed/speckled/cast texture, sensor noise,
  and 0-3 defects with known geometry. Ground truth is measured from the *drawn mask*, not
  from the drawing parameters, so the benchmark cannot be gamed.
* **Every design decision was measured, and several were reverted.** Details and numbers
  are in `ARCHITECTURE.md`; the short version:
  * plain black-hat/top-hat + local adaptive threshold → 1219 false positives on 20 plates;
  * hysteresis region growing → scratch recall collapsed from 1.00 to 0.29 (texture
    bridges), removed;
  * full-resolution median background → stains erased, stain recall 0.27;
  * downscaled background → stain recall 0.87, F1 0.89 (same channels);
  * adding the disk channel → stain recall 0.93, F1 0.927 on the primary matcher, and
    disabling just that channel drops F1 back to 0.892.
* **Failure modes are tested, not assumed.** Clean plate must report zero; a blind detector
  must score F1 = 0 (so the metric provably reacts); garbage bytes must be a 400, not a
  silent success; an unimplemented S3 input must be a 501.
* **49 tests** run in ~21 s with no network and no fixtures on disk.

## Challenges we ran into

* **Texture that looks like defects.** On brushed metal, a single-scale morphology response
  to texture was as strong as to a real scratch (defect peak z 2.8-3.9 vs texture p99.9
  3.2). Orientation-steered kernels and per-channel standardisation changed that to
  background 2.2-3.7 vs scratch peaks 14-63.
* **The background subtraction eating the defect.** A median whose kernel is narrower than
  a 60 px stain samples only stain pixels at the stain's center: the "background" becomes
  the defect and the residual vanishes. Estimating the surface on a downscaled copy fixed
  it and made the whole stain class detectable.
* **Normalising for texture, not for white noise.** Standardising by the theoretical
  white-noise gain left background z-scores of 20-48, because brushed texture is coloured
  and passes low-frequency kernels efficiently. Per-channel RMS on the actual image was the
  honest scale.
* **Thin-object evaluation.** A 2 px scratch has a bounding box 30x wider than its pixels;
  strict IoU-0.5 matching calls a correct detection a miss. We report three rules side by
  side — IoU 0.25, IoU 0.50 and the contained-core variant — instead of quoting only the
  flattering one.
* **A false positive at x = 0** from convolution borders, found only because the clean-plate
  test was strict. Fixed by rejecting components that touch the frame edge, with the cost
  (no edge defects) written down.

## Accomplishments that we're proud of

* A detector with **no learned parameters** that reaches **F1 0.809 at IoU 0.25 and
  0.662 at IoU 0.50** at seed 7000, reported together with the six-seed ranges
  (0.736-0.860 and 0.574-0.678) instead of the best seed alone.
* A benchmark that counts what hurts: **3 false positives on 36 clean plates** across
  the seed sweep, disclosed rather than claimed away.
* A benchmark that is **reproducible byte-for-byte** from a seed, with ground truth that
  cannot be reverse-engineered from the code that draws the defects.
* **Three deployment surfaces** (CLI, FastAPI, Lambda) over one engine, with all three
  exercised in `EVIDENCE.md`.
* An **ablation test** (`test_metric_reacts_to_a_blind_detector`) that fails the build if
  the benchmark ever stops reacting to a detector that does nothing.
* An architecture document that records the **rejected** designs and their measured costs,
  not only the winning one.

## What we learned

* In classical CV, the **background model is the algorithm**. Two lines of background
  estimation moved stain recall from 0.27 to 0.87.
* **Shape priors beat thresholds.** A threshold on a scalar response detects texture; a
  matched filter detects defects.
* **A metric must be able to fail.** We deliberately disabled the detector inside a test to
  prove the benchmark is not a facade.
* **Over-claiming is easy.** We downgraded several statements in this repository after
  re-measuring them (e.g. "5x better separation" → the actual per-channel z numbers).

## What's next

1. **Validate on real plates.** The synthetic domain is the biggest weakness; the next step
   is 200-500 labelled photos from an actual line, with the same benchmark harness.
2. **Per-part calibration.** Learn the reporting floor (contrast in noise units) from a few
   known-good plates per part number, instead of a global constant.
3. **Colour stains.** Inspect chroma channels (Lab a/b) for oil and coolant residues that
   are invisible in grayscale.
4. **Deploy the SAM stack.** `template.yaml` defines the function, the HTTP API and an
   S3 trigger, and the handler now reads S3 objects with boto3. It has not been deployed;
   `scripts/deploy_aws.sh` is the real path and requires AWS credentials.
5. **Metric improvements.** Raise IoU 0.50 F1 (currently 0.662 at seed 7000) and pure
   IoU 0.25 F1 (0.809) by fitting boxes to the scratch core instead of its response
   envelope.
6. **Throughput.** Batch the filter bank across images and move the eight line angles into
   one `filter2D` call with a stacked kernel for line-rate inspection.

## Built with

Python 3.12 · OpenCV 5.0.0 (`opencv-python-headless==5.0.0.93`) · NumPy 2.4/2.5 · FastAPI ·
Uvicorn · pytest · AWS SAM (`template.yaml`) · AWS Lambda container base image
(`Dockerfile` builds and runs locally on `public.ecr.aws/lambda/python:3.12`; no AWS account)

## Deployment status

`template.yaml` is an AWS SAM template with the Lambda function (`lambda_handler.handler`,
python3.12, 2048 MB, 30 s), an HTTP API `POST /inspect`, and an S3 `.png` upload trigger.
**No cloud deployment was made.** No AWS credentials were available, so no bucket,
function, API Gateway or CloudFormation stack exists, and there is no public demo URL.
`scripts/deploy_aws.sh` refuses to run without credentials instead of pretending to
deploy.

What did run is the function artifact: `scripts/live_lambda.sh` builds the image from the
official `public.ecr.aws/lambda/python:3.12` base and invokes the handler over the Lambda
Runtime API. Both input shapes return 200 with the same two defects, a malformed body
returns 400, and the S3 branch reaches a real `boto3` client and fails closed with 502
when no credentials exist. The recorded trace is `evidence/lambda-live-trace.json`.

## Links

* Repository: `https://github.com/aigon-x/fieldlens`
* Demo video: `<VIDEO_URL>` (not recorded yet)
* Public demo URL: none — the AWS deployment has not been performed
* Benchmark report: `EVIDENCE.md` in the repository

## Try it

```bash
python3 -m pip install -r requirements.txt

# single plate -> JSON + annotated PNG + mask
python3 -m fieldlens inspect samples/images/plate_0003_seed7403.png --out-dir out

# evaluation, exit code 1 below F1 0.80
python3 -m fieldlens benchmark --n 40

# service + web inspector (the page offers "Inspect a sample plate" — no file needed)
python3 -m fieldlens serve --port 8099
curl -X POST --data-binary @samples/images/plate_0003_seed7403.png \
     -H 'Content-Type: image/png' http://127.0.0.1:8099/inspect

# tests
python3 -m pytest tests -q
```
