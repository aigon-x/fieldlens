# FieldLens — architecture

One page: data flow, modules, the decisions that matter, and what changes under OpenCV 5.

## Data flow

```
                       ┌──────────────────────────────────────────────┐
 raw bytes / base64 ──►│ imageio: imdecode → BGR/gray, PNG encode      │
                       └───────────────┬──────────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────────┐
                       │ preprocess: resize ≤768 → median(3) →        │
                       │ bilateral → CLAHE (visual/contrast normal.)  │
                       └───────────────┬──────────────────────────────┘
                                       ▼
                       ┌──────────────────────────────────────────────┐
                       │ flat_field: Gaussian(0.7) − background,      │
                       │ background = median(7) on a 1/8-scale copy   │
                       └───────────────┬──────────────────────────────┘
                                       ▼
        ┌──────────────────────────────┴───────────────────────────────┐
        │ matched-filter bank (filter2D, 5 channels)                   │
        │  LoG σ3 · LoG σ6 · DoG 6/14 · disk 16/40 · line × 8 angles   │
        └──────────────────────────────┬───────────────────────────────┘
                                       ▼
        ┌──────────────────────────────┴───────────────────────────────┐
        │ per-channel RMS normalisation → z maps                       │
        │ threshold per channel (3.6–4.8 σ) → hot mask                 │
        │ morphology: close(7) → open(3)                               │
        └──────────────────────────────┬───────────────────────────────┘
                                       ▼
        ┌──────────────────────────────┴───────────────────────────────┐
        │ blob branch  (LoG/DoG/disk)      line branch (oriented)      │
        │ area ≥ 170 px, extent/shape      length ≥ 14, thickness ≤ 12 │
        │ → dent / stain                   → scratch                   │
        └──────────────────────────────┬───────────────────────────────┘
                                       ▼
        ┌──────────────────────────────┴───────────────────────────────┐
        │ merge same-kind neighbours → suppress overlaps (NMS)         │
        │ → Defect list (bbox in ORIGINAL pixels) + accepted mask      │
        └──────────────────────────────┬───────────────────────────────┘
                                       ▼
              CLI JSON/PNG · FastAPI JSON (+mask, annotated) · Lambda JSON
```

## Modules

| module | responsibility | notes |
|---|---|---|
| `imageio.py` | decode path/bytes/base64, encode PNG | raises `ImageDecodeError`, never returns `None` |
| `preprocess.py` | resize cap, denoise, CLAHE | pure functions, no state |
| `detect.py` | flat field, filter bank, z-gating, components, classification, NMS | the whole algorithm |
| `synth.py` | deterministic plates + ground truth; dataset writer/loader | ground truth measured from the drawn mask |
| `benchmark.py` | IoU/containment matching, P/R/F1, timing, gate | one-to-one greedy matching |
| `annotate.py` | boxes + labels, red mask overlay | BGR output only |
| `cli.py` | `inspect` / `benchmark` / `serve` / `synth` | exit code 1 when the F1 gate fails |
| `api.py` | FastAPI app, three input encodings | stateless |
| `lambda_handler.py` | API Gateway, direct invoke, S3 via boto3 | 501 only when boto3 is unavailable |
| `template.yaml` | SAM: function, HTTP API, S3 trigger | not deployed; YAML structure parsed locally (no SAM CLI on this host) |
| `scripts/deploy_aws.sh` | real `sam build` + `sam deploy` | exits 1 without AWS credentials |

## Decisions and alternatives

**Matched filters instead of plain morphology.** The brief suggested Sobel/Laplacian +
adaptive threshold + morphology. Measured on this data, a black-hat/top-hat pair with
per-pixel adaptive gating responded to brushed texture as strongly as to defects: with a
local-statistics threshold the mask covered 132k of 147k pixels on a noisy plate, and the
first working version produced 1219 false positives on 20 plates. Morphology responds to
*any* local extremum; a defect is a *shape*. An orientation-steered line kernel plus
LoG/DoG/disk kernels changed the measured separation to: clean-plate background z p99.9 =
2.2-3.7 per channel, scratch peaks 14-63, dent and stain peaks 4-10. Sobel-like edge
energy is still present implicitly — LoG is the Laplacian of a Gaussian and `filter2D` is
the same primitive Sobel uses — but the gate is a statistical z-score (a data-adaptive
threshold on a normalised response) rather than `cv2.adaptiveThreshold`, which normalises
locally and re-amplifies texture in flat areas.

**Background on a downscaled copy.** A full-resolution median `k=31` is *narrower than a
60 px stain*: at the stain centre the window lies entirely inside the defect, the median
follows the defect, and the residual collapses to zero — the defect disappears. `k=81`
would fix it at a large cost. Downscale ×8 → `median(7)` → upscale reconstructs only the
low-frequency illumination/cast surface and costs 2.4 ms. Measured effect on 40 plates
(seed 7000, identical channels and thresholds): stain recall 0.27 → 0.87, F1 0.80 →
0.89. Adding the disk channel on top of that gives stain recall 0.93 and F1 0.927
on the primary matcher (ablation: disabling only the disk channel drops F1 back to
0.892).

**Per-channel RMS normalisation, not theoretical noise gain.** Standardising by
`σ_residual · ‖k‖₂` assumes white noise. The plate texture is coloured (brushed streaks,
cast waviness), and that model under-estimated the denominator by 10-30x, leaving
background z of 20-48. Normalising each channel by the RMS of its own response map on
the same image is data-driven and exposure-independent.

**Half-resolution disk channel.** The disk kernel targets 28-80 px structures, so it is
convolved at half resolution and upsampled: measured identical P/R/F1 on seeds 5000,
7000 and 9000, with 40-plate wall time 8.4-10.8 s instead of 11.0 s.

**Blob and line branches are separated.** Hysteresis growth of blob seeds was tried and
rejected: at a permissive grow threshold the blob branch swallowed scratches into large
texture-connected regions and scratch recall fell from 1.00 to 0.29. The final design
grows nothing; it gates per branch and then suppresses line boxes that live inside a
blob box (a dent rim is a line response).

**Border rejection instead of padding.** Reflect-padding the whole frame removed one
false positive on a clean plate but cost 40% more time and slightly lowered precision.
Rejecting components that touch the frame edge (`reject_border`) keeps the runtime and
gives the same clean-plate result; edge defects are explicitly out of scope.

**Containment matching for thin objects — reported next to the strict rule.** A 2 px
scratch has a bbox 30x wider than its pixels; strict IoU-0.5 matching calls such a
correct detection a miss. The primary matcher therefore accepts a detection whose box is
contained in the ground-truth box (≥0.6, ≤3x area). It is *lenient*, so every report also
contains `iou25_no_containment` and `strict_iou50`, both without containment. At seed
7000 that is F1 0.809 (IoU 0.25) and 0.662 (IoU 0.50) against the primary 0.927; all
three numbers are printed by the CLI and stored in the JSON.

**Rejected: deep learning.** The competition requires real OpenCV use; a CNN would also
need training data that does not exist here, and the point of the entry is a
zero-dependency, CPU-only baseline that runs in a Lambda cold start.

## Failure modes and guards

| failure | guard | test |
|---|---|---|
| texture producing "defects" | per-channel RMS z gate + area/shape filters | `test_clean_plates_report_nothing` |
| metric that always looks good | ablation: blind detector must score F1 = 0 | `test_metric_reacts_to_a_blind_detector` |
| broken decode silently succeeding | `ImageDecodeError` → HTTP 400 / CLI exit 2 | `test_garbage_payload_raises`, `test_inspect_rejects_garbage` |
| Lambda "success" without work | S3 path returns 501 without boto3, 502 on read failure | `test_s3_event_without_boto3_returns_501`, `test_s3_event_without_key_returns_400` |
| double-counting one defect | one-to-one greedy matching | `test_matching_is_one_to_one` |
| coordinate drift on downscale | boxes mapped back to original pixels | `test_large_image_coordinates_are_original_scale` |

## OpenCV 5 (verified, not planned)

`requirements.txt` pins `opencv-python-headless==5.0.0.93`; `cv2.__version__` is `5.0.0`
and the whole suite plus the benchmark was re-run on it.

| check | measured result |
|---|---|
| import | `cv2.__version__ == "5.0.0"` from wheel 5.0.0.93 |
| tests | 49 passed, 0 failed |
| benchmark, seed 7000 | TP=63 FP=7 FN=3; F1 0.9265 primary / 0.8088 at IoU 0.25 / 0.6618 at IoU 0.50 — identical counts to the documented 4.x run |
| source changes needed for 5.x | none |

The API surface is the same one the tests already exercised: `imdecode`/`imencode`,
`GaussianBlur`/`medianBlur`/`bilateralFilter`, `filter2D`, `morphologyEx` +
`getStructuringElement`, `connectedComponentsWithStats`, `minAreaRect`, `moments(...,
binaryImage=True)`, `createCLAHE`, `getRotationMatrix2D`/`warpAffine`. OpenCV 5 accepted
the explicit `float32` kernels and the `uint8`/`float32` boundaries unchanged, so the
migration was a regression test rather than a port. The wheel is `cp37-abi3`, which is
why the same 5.0.0.93 install serves the Python 3.11 and 3.12 interpreters on this host.

## AWS deployment surface

`template.yaml` (AWS SAM) defines:

* `AWS::Serverless::Function` — `Handler: lambda_handler.handler`, Python 3.12, x86_64,
  2048 MB, 30 s timeout, inline `s3:GetObject` on the plates bucket ARN;
* `AWS::Serverless::HttpApi` — `POST /inspect`;
* an S3 event on the function — `s3:ObjectCreated:*` for `.png` objects in
  `fieldlens-plates-<account-id>-<region>`.

When run with credentials, `scripts/deploy_aws.sh` validates the template, runs
`sam build` and a real `sam deploy` change set. Without usable credentials it exits 1 and states that nothing
was built or deployed; it never fakes a deployment.

**Not done for this submission:** no `sam build`, no `sam deploy`, no AWS account was
touched. The S3 branch is covered by unit tests with a stubbed client, and by an explicit
501 when boto3 is unavailable in the local interpreter.

## Performance

At 384x384 the filter bank dominates (measured 163 ms of a 379 ms `inspect` call on a
host with load average ~12 on 24 cores: five convolution families, eight angles for the
line channel). The rest is components, per-component descriptors (`minAreaRect`) and two
`connectedComponentsWithStats` calls. The benchmark reports 106-262 ms/plate depending on
host load (106-222 ms in the OpenCV 5 runs); these are wall-clock numbers on a shared
machine, not isolated microbenchmarks.
Batching for throughput would mean running channels in a thread pool or stacking images
into one `filter2D` call — not done, because Lambda and the demo process one image at a
time.
