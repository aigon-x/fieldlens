---
name: IoU benchmark
description: Jak mierzymy jakosc detekcji i dlaczego dwa progi IoU.
---

# IoU benchmark

`agent_benchmark.py` -> `fieldlens/benchmark.py::match(..., iou_thr, allow_containment=False)`.

## Metryka
Dopasowanie kandydat<-> ground truth po IoU. Liczymy precision/recall/F1
przy `IoU 0.25` (luzne) i `IoU 0.50` (ostre). Dwa progi, bo luzne IoU maskuje
rozjazd ksztaltu, a ostre karze za przesuniecie.

## Zmierzony wynik (baseline, 20 probek)
| Tryb | F1 | P | R |
|---|---|---|---|
| baseline @.25 | 0.7937 | 0.781 | 0.806 |
| agent @.25 | 0.7812 | 0.758 | 0.806 |

Recall bez zmian, precision spadla -> podniesienie czulosci kupowalo falszywe
trafienia. To jest powod, dla ktorego istnieje `MIN_EVIDENCE_ACCEPT`.
