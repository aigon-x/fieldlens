# Judge review — FieldLens (OpenCV AI Competition 2026, powered by AWS)

Read-only review, 2026-10-20. Sources measured: README, DEVPOST_DRAFT, EVIDENCE, ARCHITECTURE,
working tree (`git log` 2c9a127, remote HEAD 2c9a127), live demo over HTTPS, public repo.
Rules read from /tmp/r_opencv26.html (rubric: tech 30 / innovation 20 / impact 20 / UX 10 /
docs 10 / cloud 10). The rules text fetched contains no separate "Stage One" definition, so
Stage One is assessed as the documented eligibility gate: real OpenCV 5 use + AWS + public artifacts.
UI assessed from served HTML and committed screenshots — not a fresh browser render (disclosed).

## 1. Stage One — TAK (technically), submission package NIE

| Gate | Result | Evidence (measured) |
|---|---|---|
| OpenCV 5 | PASS | `opencv-python-headless==5.0.0.93`, `cv2.__version__ == "5.0.0"` (EVIDENCE.md:17-39); filter2D/medianBlur/CLAHE/connectedComponentsWithStats in `fieldlens/` |
| AWS, live | PASS | `GET /` 200 (25 904 B); `POST /api/inspect` multipart 200, `count=2`, `elapsed_ms=66.37`, 247 KB annotated PNG returned; `GET /api/health` 200 |
| Public repo | PASS | `https://github.com/aigon-x/fieldlens` 200; raw README 200; MIT LICENSE present |
| Video | **FAIL** | `DEVPOST_DRAFT.md:170` — `Demo video: <VIDEO_URL> (not recorded yet)` |
| Docs match product | **FAIL** | README:131 "No AWS resource was created"; DEVPOST:156-157,171 "no cloud deployment… no public demo URL" — both false today |

Verdict: the technical gate is cleared with live evidence. If Stage One requires a complete
Devpost package (video + accurate links), this entry does not pass as submitted.

## 2. Scores (0–10, rubric weights; **bold** = the four requested criteria)

| Criterion | Weight | Score | Why |
|---|---|---|---|
| **Technical execution** | 30% | 6.5 | Real, deterministic, well-tested pipeline (62 committed tests); honest multi-matcher reporting. But all OpenCV calls are legacy API (no OpenCV 5-specific depth), and quality is capped by self-generated data. |
| **Innovation** | 20% | 5.0 | Textbook matched-filter bank (LoG/DoG/disk/steered lines) executed carefully, not a new idea; no learned component, no COOL, no agentic angle. |
| **Usefulness / real-world impact** | 20% | 5.5 | Real problem, plausible ICP. Zero real-plate validation, no customer, no cost/ROI evidence; demo mislabels arbitrary photos as defects, which erodes trust. |
| User experience | 10% | 6.5 | Clean dark inspector, one-click sample, keyboard + WCAG AA tests, mobile shot. No explanation of value on the landing page, no export/history, no domain warning live. |
| **Presentation / docs** | 10% | 5.0 | Exceptionally candid docs (rare and good) but internally contradictory, stale test counts (49/60/62), and no video. |
| Cloud / reproducibility / responsible | 10% | 5.0 | Live Lambda works; SAM template does not reproduce it; no CI, metrics, alarms, auth, or rate limit; open endpoint with `Access-Control-Allow-Origin: *`. |
| **Weighted** | 100% | **5.7** | 0.3·6.5 + 0.2·5.0 + 0.2·5.5 + 0.1·6.5 + 0.1·5.0 + 0.1·5.0 |

## 3. Five things a judge marks down — three visible in 60 seconds

1. **(60 s) The landing page explains nothing.** It shows "FieldLens / Surface inspection · classical CV /
   Inspector / Choose an image" and "No image inspected yet." No one-line value proposition, no repo
   link, no sample result on load, no video. A judge must guess what the product is.
2. **(60 s) Any photo becomes a defect report.** Uploading a UI screenshot returned HTTP 200 with
   `count=17` confident "scratch/dent/stain" labels in 214 ms. The domain guard (`fieldlens/quality.py`)
   exists only in the uncommitted working tree — the live demo has none.
3. **(60 s) Docs contradict the live product.** README/DEVPOST say no AWS deployment and no demo URL,
   yet `873vdlij6g.execute-api.eu-north-1.amazonaws.com` is live. Documented `POST /inspect` returns
   404; the working route is `/api/inspect`, multipart-only. Documented response schema
   (`defect_count`, `counts`, `kind`, `bbox`, `area_px`) differs from live (`count`, `type`, `score`, `box`).
4. **Evaluation is circular.** `fieldlens/synth.py` defines both the data and the detector's assumptions;
   F1 0.809 at IoU 0.25 and 0.662 at IoU 0.50 on synthetic plates is modest, and no real plate was ever
   measured. "Cannot be gamed" is asserted, not demonstrated.
5. **The deployable artifact does not match the deployment.** `template.yaml` targets
   `lambda_handler.handler` at `/inspect`, 30 s; the live function runs `lambda_http.handler` (Mangum)
   at `/api/*`, 60 s per EVIDENCE. A judge cannot rebuild the demo from the repo, and there is no
   observability, auth, quota, or cost control around an open public endpoint.

## 4. Three questions the submission does not answer

1. What is the false-positive rate per plate on a real inspection line, at the threshold you ship —
   and what happens to precision when lighting and material change?
2. What is the intended operating mode when input is out of domain (document, wood, fabric)? There is no
   deployed guard, no human-review step, and no stated liability model for a wrong "0 defects" verdict.
3. Which artifact is authoritative for reproduction — the SAM template or the Mangum container — and
   what is the cost and latency per 1 000 inspections at line rate, including cold starts?

## 5. One indefensible claim

README.md:131 — **"No AWS resource was created for this submission"** (repeated in DEVPOST_DRAFT:156-157
and scripts/deploy_aws.sh). It is false: API Gateway `873vdlij6g` and Lambda `fieldlens` in eu-north-1
serve the demo today, and EVIDENCE.md:481-484 records the ECR image and function. A judge who opens the
demo sees a live AWS deployment next to a document denying it exists; every other honesty claim in the
repo is then discounted, which is the opposite of what this unusually candid write-up deserves.
