---
name: API contract
description: Kontrakt HTTP FieldLens: /inspect, /agent/inspect, /health.
---

# API contract

`fieldlens/api.py` (FastAPI).

| Trasa | Wejscie | Wyjscie |
|---|---|---|
| `GET /health` | — | `{status, engine}` |
| `POST /inspect` | obraz (multipart lub base64) | `InspectionResult` |
| `POST /agent/inspect` | obraz + opcjonalny `quality` | `payload + agent{outcome,decisions,summary}` |

`/agent/inspect` zwraca `engine: "opencv-matched-filter + active-perception"` —
jawnie odroznia tryb klasyczny od agentowego.

## Zasada
Agent nie jest osobnym serwisem: to ta sama trasa z dodatkowa warstwa decyzji,
wiec sedzia widzi jeden produkt, nie dwa.
