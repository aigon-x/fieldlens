---
name: Matched-filter inspection engine
description: Jak dziala detekcja wad w FieldLens: pasma Log/DoG, progowanie, kontrast w jednostkach szumu.
---

# Matched-filter inspection

Silnik: `fieldlens/engine.py` (OpenCV). Wejscie BGR -> wyjscie `InspectionResult`.

## Etapy
1. `max_dim=768` — downscale, zeby koszt byl przewidywalny.
2. `denoise_sigma=0.7` — wygasza szum sensora bez zjadania cienkich rys.
3. Pasma Log `(3.0, 6.0)` + pasma DoG `(6.0, 14.0)` — skala plamy.
4. Progi bazowe: `log (3.8, 3.8)`, `disk 3.6`, `line 4.8`.
5. Morfologia: `close 7`, `open 3`; filtry `min_area 30`, `min_blob_area 170`, `min_extent 0.05`.

## Dlaczego progi, a nie jedna liczba
Kazdy typ wady ma inna geometrie (plama/disk/linia), wiec jedna globalna czulosc
albo gubi rysy, albo produkuje falszywe plamy. Cztery progi = cztery niezalezne decyzje.

## Dowod
`tests/test_engine.py` + `agent_benchmark.py` (baseline F1 0.7937 @IoU .25).
