---
name: Quality domain check
description: Bramka jakosci wejscia — kiedy obraz w ogole nie nadaje sie do inspekcji.
---

# Quality domain check

Przed inspekcja liczymy metryki jakosci (kontrast, ostrosc, ekspozycja).
Jesli obraz jest poza domena, silnik **nie zgaduje** — zwraca `rescan_needed`.

## Dlaczego przed, a nie po
Inspekcja na złym obrazie zuzywa `MAX_ITERS` i konczy sie rescanem i tak.
Sprawdzenie najpierw oszczedza iteracje i daje uczciwy powod.

## Wspolna liczba
`_mean_contrast()` — sredni kontrast w jednostkach szumu; prog `LOW_CONTRAST = 2.0`
jest wspolny z polityka agenta, zeby jedna liczba znaczyla jedno.
