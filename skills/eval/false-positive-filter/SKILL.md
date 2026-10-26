---
name: False-positive filter
description: _strong_only() — filtr dowodu, ktory wyrownuje agenta z baseline.
---

# False-positive filter

Problem zmierzony: agent podnosil czulosc i zyskiwal falszywe trafienia.
Precision 0.781 -> 0.758, recall bez zmian => F1 w dol o 0.0125 (@.25) i 0.0099 (@.50).

## Naprawa
`agent.py::_strong_only(res, floor=2.0)` — po strojeniu zostaja tylko kandydaci
z `score >= MIN_EVIDENCE_ACCEPT (2.0)`. Kandydat bez dowodu nie jest raportowany.

## Wynik po naprawie
delta F1 = **+0.0000** przy IoU 0.25 i 0.50; rescan nadal 4/20.
Agent nie pogarsza jakosci — doklada decyzje i rescan, nie kosztem precyzji.

## Regula
Kazda zmiana czulosci musi byc sparowana z filtrem dowodu, inaczej optymalizujesz
licznik kandydatow, a nie jakosc.
