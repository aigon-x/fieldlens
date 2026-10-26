---
name: Lambda container via SAM
description: Wdrozenie FieldLens jako obraz kontenera w AWS Lambda przez SAM.
---

# Lambda container via SAM

Pliki: `template.yaml`, `Dockerfile`, `lambda_handler.py`, `lambda_http.py`.

## Przebieg
1. Zbudowanie obrazu kontenera z `Dockerfile` (FastAPI + adapter `lambda_http.py`).
2. `sam build` / `sam deploy` z `template.yaml` (`PackageType: Image`).
3. API Gateway HTTP API -> Lambda -> `handler(event, context)`.

## Zmierzone
Publiczny endpoint: `https://873vdlij6g.execute-api.eu-north-1.amazonaws.com/`
Trace: `evidence/lambda-live-trace.json`.

## Pulapki
- Obraz musi byc `linux/amd64` — inaczej Lambda odrzuca manifest.
- Zimny start: pierwszy request po wdrozeniu jest wolniejszy; mierzyc drugi.
- `requirements-lambda.txt` osobno od `requirements.txt` (mniejszy obraz).
