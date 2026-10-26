---
name: Active perception loop
description: Petla decyzji agenta: kiedy podniesc czulosc, kiedy specyficznosc, kiedy zlecic rescan.
---

# Active perception loop

`fieldlens/agent.py::inspect_adaptive(bgr, base, max_iters, quality)`.

## Stale (zmierzone)
- `MAX_ITERS = 3`
- `SENSITIVITY_STEP = 0.85` (prog * 0.85 = czulosc w gore)
- `SPECIFICITY_STEP = 1.15` (prog * 1.15 = specyficznosc w gore)
- `MANY_HITS = 8`, `LOW_CONTRAST = 2.0`
- `MIN_EVIDENCE_ACCEPT = 2.0`

## Polityka
| Warunek | Decyzja |
|---|---|
| iter1, 0 wad | czulosc x0.85, powtorz |
| `n > 8` i `mean_contrast < 2.0` | specyficznosc x1.15, powtorz |
| inaczej | stop |
| po petli 0 wad | `request_rescan` + `rescan_needed` |
| `quality` poza domena | natychmiast rescan, bez inspekcji |

## Granica
Petla jest ograniczona `MAX_ITERS` — nie ma nieskonczonego zwiekszania czulosci.
Kazda decyzja zwraca `reason` i `thresholds`, wiec sedzia moze ja odtworzyc.
