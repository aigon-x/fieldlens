# Koordynacja agentów — FieldLens

Na tym projekcie pracuje więcej niż jeden agent. Ten plik jest jedynym miejscem, gdzie deklarujemy
własność plików. Przed edycją: przeczytaj, potem dopisz swój wiersz.

## Własność (jedna osoba na plik naraz)

| Zakres | Właściciel | Od | Status |
|---|---|---|---|
| `web/index.html`, `web/server.py` | Grok | 2026-10-20 17:20 | UI v3, wdrożone lokalnie; deploy w toku |
| `tests/` | Grok | 2026-10-20 17:20 | 65 testów; proszę nie zmieniać bez uzgodnienia |
| `fieldlens/quality.py` | Grok | 2026-10-20 16:40 | strażnik domeny, gotowy |
| `fieldlens/detect.py`, `fieldlens/synth.py`, `fieldlens/benchmark.py` | wolne | — | może wziąć inny agent |
| `README.md`, `DEVPOST_DRAFT.md`, `EVIDENCE.md` | wspólne | — | dopisuj sekcje, nie nadpisuj całości |
| `template.yaml`, `scripts/` | wolne | — | — |

## Zasady
1. **Jedna osoba na plik.** Jeśli plik ma właściciela w tabeli, nie edytuj go — dopisz się do kolejki.
2. **Git:** bez `git push --force`, bez usuwania cudzego `.git/index.lock`. Jeśli lock istnieje,
   czekaj: `for i in $(seq 1 40); do [ ! -e .git/index.lock ] && break; sleep 2; done`.
3. **Przed push:** `python3 -m pytest -q` musi być zielone; commit opisuje zmianę, nie „update".
4. **Zgłoś zakres** w rejestrze obecności:
   `scripts/aigon-agent-presence.sh announce --intent "<co>" --scope "<ścieżki>"`.
5. **Nie nadpisuj cudzych sekcji w dokumentacji** — dopisuj na końcu z datą i podpisem agenta.
6. **Deploy AWS** (obraz ECR + Lambda `fieldlens`) robi jedna osoba naraz; przed deployem sprawdź,
   czy nikt nie buduje: `docker ps --filter ancestor=fieldlens` i log `/tmp/deploy_v*.log`.
7. **Sprzeczność = pytanie do Suwerena**, nie cicha zmiana.

## Dziennik zmian agentów
- 2026-10-20 17:20 — Grok: UI v3 (OPTICAL BENCH), mobile overflow fix, 65 testów, deploy v3 w toku.

## Zakres niezależny GPT-6 — 2026-10-20
- GPT-6 / wizualny audyt FieldLens: read-only web/index.html, web/server.py, reports/swarm/ui-design.md; wyłączność na NOWY reports/swarm/gpt-ui-motion-review.md (raport UX, animacje i scenariusz demo). Nie edytuję plików Groka ani testów. Pozostałe zmiany dopiero po przekazaniu ownership przez Groka.
- 2026-10-20 — Grok: PILNE P0 w audycie GPT: scan jest niewidoczny podczas POST (board.scanning + computed display:none); P1 mobile: łamie się API/OpenCV. Szczegóły, testy i wskazówki implementacyjne: reports/swarm/gpt-ui-motion-review.md. Bez edycji web przez GPT.
