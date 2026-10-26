---
name: Rescan policy
description: Kiedy silnik odmawia werdyktu zamiast zgadywac — i jak to raportuje.
---

# Rescan policy

Zasada: **lepszy brak werdyktu niz falszywy werdykt.**

## Kiedy rescan
1. Po `MAX_ITERS` nadal `0` wad przy scenie, ktora nie jest czysta.
2. `quality` poza domena (rozmycie, brak kontrastu, zla ekspozycja) — sprawdzane
   PRZED inspekcja, zeby nie tracic iteracji.
3. Wewnetrzna sprzecznosc: duzo kandydatow, bardzo niski kontrast.

## Co zwraca
`outcome = "rescan_needed"`, `decisions[]` z powodami, `summary` maszynowo czytelne.
Konsument (API/MCP) widzi jawne "nie wiem", nie pusta liste wad.

## Dowod
`tests/test_agent.py::test_clean_plate_raises_sensitivity_then_rescan` —
czysta plyta musi skonczyc sie rescanem, nie pustym werdyktem "OK".
