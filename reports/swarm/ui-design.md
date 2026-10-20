# FieldLens — UI design spec · „OPTICAL BENCH”
`v1 · 2026-10-20 · zakres: warstwa wizualna web/index.html · API i logika bez zmian · stan: PROJEKT (nie wdrożono)`

## 1. Koncepcja
**OPTICAL BENCH (Ława Optyczna)** — interfejs nie udaje SaaS, tylko **instrument pomiarowy XXI wieku**: czarna anodowana płyta, grawerowane skale, jedna wiązka światła i liczby w monospace. Każdy element tłumaczy metodę (szum → próg → region), więc sędzia widzi nie „ładny front”, lecz **przyrząd, który mierzy i uzasadnia wynik**.

## 2. System wizualny
### 2.1 Paleta (hex)
| token | hex | rola |
|---|---|---|
| `--bg` | `#05070A` | tło przyrządu |
| `--panel` | `#0E1217` | korpus panelu |
| `--panel-2` | `#141A21` | wiersze, pola |
| `--hairline` | `#202833` | kreska 1 px, skala |
| `--ink` | `#E9ECF0` | tekst główny |
| `--muted` | `#A7B1BF` | tekst wspierający (8.4:1 na panelu) |
| `--faint` | `#8A95A3` | metadane (6.0:1) |
| `--beam` | `#5AA2FF` | wiązka/skan, focus, akcent (7.7:1 na bg) |
| `--beam-ink` | `#2F6BCC` | wypełnienie CTA (biały tekst 5.1:1) |
| `--scratch` | `#FF6B6B` | klasa scratch |
| `--dent` | `#FFB020` | klasa dent |
| `--stain` | `#D98AF0` | klasa stain |
| `--ok` | `#3ECF8E` | PASS / API ok |

Zakaz: gradientowe fiolety, glassmorphism, ilustracje, emoji. Kolor nigdy nie jest jedynym nośnikiem znaczenia — typ wady ma ikonę i podpis.
### 2.2 Typografia
Inter (UI) + JetBrains Mono (liczby, współrzędne, etykiety). Skala 1.25: `11` mono-mikro/eyebrow `.14em` · `12` mono-meta · `13` UI-small · `15` body · `18` h3 · `24` h2 · `34` licznik · `56` licznik hero (desktop). Wszystkie liczby `font-variant-numeric: tabular-nums`, waga 500–650, tracking ujemny tylko dla licznika (`-.02em`).
### 2.3 Siatka, promienie, cienie
12 kolumn, `max-width:1320px`, gutter 20, margines 28; workspace `minmax(0,1fr) 392px`; rytm pionowy 8 px (4/8/12/16/24/32/48). Promienie: `4` (kbd, swatch), `8` (przyciski, pola), `12` (panele), `999` wyłącznie status-chip. Cienie: `0 24px 60px -32px #000`, wewnętrzna krecha `inset 0 1px 0 rgba(255,255,255,.03)`, poświata tylko dla wiązki `0 0 24px rgba(90,162,255,.45)`. Zero rozmytych „kart”.

## 3. Układ (desktop → mobile)
1. **Rail** (60 px): znak celownika, „FieldLens / Surface inspection”, po prawej `status-chip` (API · v1.0.0) i numer seryjny przyrządu `FL-01`.
2. **Hero / Stage** (lewa, 1fr): viewport 4:3 z `object-fit:contain` na czerni `#020304`; narożne znaczniki kalibracyjne, skala px na krawędziach, `<img>` + nakładka SVG z ramkami (zamiast malowania w canvas — ostre na HiDPI i animowalne). Przed uploadem dropzone; po wyniku toolbar: `384×384 px · 967 ms` + „New image” + „Export PNG” (z `annotated_png_base64`).
3. **Findings** (prawa, 392 px): nagłówek + `elapsed`; wielki licznik `1 DEFECT`; legenda filtrów (klik = izolacja klasy); lista wierszy `[01] [ikona] stain · x151 y121 w59 h62 · ▮▮▮▮ z1.8`; hover/fokus wiersza podświetla ramkę na obrazie, `1–9` skacze do wady, `Esc` czyści.
4. **Metrics bar** (pod oboma, pełna szerokość): cztery komórki mono `TIME 967 ms` · `REGIONS 1` · `PEAK z 1.8` · `SIZE 384×384`, plus 8-slotowy sparkline czasów ostatnich inspekcji (czysta skala, nie wykres).
5. **Mobile ≤820 px**: stack Stage → Metrics (2×2) → Findings; rail zawija chip pod brand; listy bez `max-height`.

## 4. Animacje (ms, easing)
Tokeny: `--ease-out:cubic-bezier(.2,.7,.2,1)`, `--ease-snap:cubic-bezier(.16,1,.3,1)`, `--ease-scan:cubic-bezier(.4,0,.2,1)`, czasy `90/140/220/320/700/900`.

| # | element | wyzwalacz | ruch | czas | easing | delay |
|---|---|---|---|---|---|---|
| 1 | rail, stage, findings | load | `opacity 0→1`, `translateY(10px→0)` | 320 | out | 0 / 40 / 80 |
| 2 | scanline | upload OK | `translateY(-2px→100%)`, wiązka 2 px + poświata, 1 przebieg | 900 | scan | 0 |
| 3 | ramki wad | po skanie | `stroke-dashoffset L→0` (rysowanie obwodu), narożniki `scale .8→1` | 320 | out | 60×idx, max 6 |
| 4 | licznik wyniku | po skanie | `0→N`, `easeOutCubic`, tabular-nums | 420 | out | 120 |
| 5 | wiersze listy | po skanie | `opacity 0→1`, `translateX(-4px→0)` | 220 | out | 40×idx |
| 6 | hover/fokus wiersza | pointer/klawisz | ramka `stroke-width 2→3`, fill `.10`, wiersz `inset 2px beam` | 140 | out | 0 |
| 7 | filtr klasy | klik legendy | `opacity .15` pozostałych ramek | 160 | out | 0 |
| 8 | clean plate „PASS” | count=0 | pieczęć `scale 1.04→1`, `opacity 0→1` | 260 | snap | 120 |
| 9 | błąd | wyjątek | `opacity`, `translateY(4px)` | 180 | out | 0 |
| 10 | spinner | request | rotacja 360° | 720 | linear | — |

Reguły: tylko `transform`/`opacity`/`stroke-dashoffset`; `will-change` wyłącznie na scanline; brak animacji layoutu. Przy `prefers-reduced-motion: reduce` — wszystkie czasy `1ms`, bez transformacji, scanline ukryty (statyczna krecha), licznik natychmiastowy, ramki bez rysowania. Ten sam warunek w JS przez `matchMedia` (licznik i scan pomijane, nie „skracane”).

## 5. Dostępność
- Kontrast: tekst ≥4.5:1, obiekty graficzne ≥3:1; ramki na jasnym metalowym tle mają **halo**: ciemna obwódka 3 px + kolor 2 px, żeby nie znikły na `#9a9a9a`.
- `:focus-visible{outline:2px solid var(--beam); outline-offset:2px}` na każdym interaktywnym; nigdy `outline:none` bez zamiennika; target ≥44×44 px na dotyku.
- `aria-live="polite"` na podsumowaniu wyniku (jedno źródło — nie dublować z licznikiem), `role="status"` na skanie, `role="alert"` na błędzie, `aria-busy` na stage w czasie requestu.
- Klawiatura: dropzone `Enter/Space`, `Ctrl+V` wkleja obraz, `1–9` wybiera wadę, `Esc` reset, `Tab` przechodzi rail → stage → lista → metryki; skip-link istnieje i zostaje.
- Obraz: `<img alt>` + `aria-describedby` z listą „1 stain, x151 y121 w59 h62, z 1.8”; lista jest prawdziwym `<ul>` (czytnik ma treść niezależną od koloru).

## 6. Implementacja (czysty CSS/JS, bez frameworków)
Plik `web/index.html` pozostaje samowystarczalny; zero zależności, zero builda.
- **Klasy**: `.rail .brand .status-chip .workspace .panel .panel-head .stage .viewport .plate .calib .scanline .boxes .box .box-halo .bracket .findings .count .legend .defect-row .zbar .metrics .metric .spark .seal .dropzone .btn .btn-primary .state`.
- **Keyframes**: `@keyframes scan-sweep`, `box-draw` (z `--len`), `bracket-in`, `row-in`, `count-pop`, `seal-in`, `err-in`, `spin`.
- **JS (dopisać do istniejącego IIFE)**: `runScan()` (klasa `.is-scanning`, `animationend` → ramki), `buildOverlay(defects,w,h)` (SVG `viewBox="0 0 W H"`, `preserveAspectRatio="xMidYMid meet"`), `countUp(el,n,420)`, `bindRows()` (mapowanie wiersz↔ramka), `setFilter(type)`, `pushTime(ms)` (sparkline ring-buffer 8), `announce()`; `const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches`.
- **Wydajność**: obraz z `URL.createObjectURL`, brak re-layoutu w animacji, SVG generowany raz na wynik; budżet ≤ 18 KB CSS+JS, first paint < 150 ms lokalnie.
- **Zgodność z API**: `POST /api/inspect` bez zmian; używane pola `defects[]`, `count`, `elapsed_ms`, `image_size`, `annotated_png_base64`.

## 7. Trzy „wow” dla sędziego
1. **Skan, który kończy się pomiarem** — wiązka przechodzi płytę raz (900 ms), a ramki dosłownie się rysują; w trakcie kursor nad obrazem pokazuje celownik z odczytem `x,y` w pasku metryk, jak suwmiarka.
2. **Linijka progu szumu** — w panelu pionowa skala σ, na której każda wada ma pinezkę `z`; widać, *dlaczego* region przeszedł próg, a nie tylko że przeszedł — to rzadkość w demo CV.
3. **Pieczęć PASS dla czystej płyty** — `0 REGIONS` nie jest pustką: pojawia się grawerowana pieczęć `PASS · 0 regions · 195 ms` z numerem seryjnym przebiegu, więc wynik zerowy staje się dowodem, nie rozczarowaniem.
