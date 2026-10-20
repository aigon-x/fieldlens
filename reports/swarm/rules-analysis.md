# Analiza regulaminu — OpenCV AI Competition 2026 (AWS)
Data: 2026-10-20 · Źródła: `curl -sSL https://opencv26.devpost.com/rules` i `/` (tekst w /tmp/opencv26_rules.txt, /tmp/opencv26_main.txt) · Projekt: ten katalog.
Deadline: **26.10.2026 23:45 PDT** = 27.10.2026 08:45 CEST (overview podaje 23:59 PT — przyjmij 23:45 PDT jako wiążące).

## 1. Kryteria oceny (nazwy dokładnie z regulaminu, wagi)
Rubryka Overall (100 pkt, min. 2 niezależnych sędziów, ranking = średnia):
| Kryterium (dosłownie) | Waga |
|---|---|
| Technical execution — correctness and depth of the OpenCV 5 implementation, architecture, reliability, and evaluation | **30%** |
| Innovation — originality and thoughtful use of computer vision or AI | **20%** |
| Real-world impact — importance of the problem, usefulness, and evidence of potential benefit | **20%** |
| User experience — usability, accessibility, and quality of interaction | **10%** |
| Documentation and presentation — clarity of the report, code, architecture, instructions, and video | **10%** |
| Cloud delivery, reproducibility, and responsible operation — AWS deployment quality, repeatability, observability, security, responsible-use | **10%** |

Remisy: najpierw Technical Execution, potem Real-World Impact, potem dodatkowy sędzia.
Nagrody specjalne (osobne rubryki, max. jedna Overall + jedna lub obie specjalne):
- Best Use of COOL: COOL na Graviton/Arm 30% · architektura 25% · zmierzona wartość 20% · innowacja 15% · reprodukcja 10%.
- Agentic Vision: integracja OpenCV 5 + agent 30% · orkiestracja/autonomia 25% · skuteczność i ewaluacja 20% · obsługa błędów/obserwowalność/kontrola człowieka 15% · UX+dokumentacja+demo 10%.

## 2. Wymogi twarde (dyskwalifikujące / warunkujące ważność)
| Wymóg | Stan dziś | Dowód / luka |
|---|---|---|
| OpenCV 5 do istotnej analizy obrazu/wideo | **PASS** | `cv2.__version__ 5.0.0`, pin `opencv-python-headless==5.0.0.93`, benchmark + 65 testów |
| Znaczący komponent działa na AWS | **PASS** | Lambda `fieldlens` (ECR eu-north-1) + API Gateway: `GET /` 200 (0,17 s), `POST /api/inspect` 200 (0,47 s) |
| Repo dostępne dla sędziego | **PASS** | `github.com/aigon-x/fieldlens` → HTTP 200 |
| Przypięte zależności + instrukcje build/deploy/test | **PARTIAL** | pin tylko OpenCV; `numpy>=2,<3`, `fastapi>=0.110`, `uvicorn>=0.29`, `mangum>=0.17`; brak lockfile; `template.yaml` (SAM) ≠ realny stack (ręczne ECR + API Gateway) |
| Diagram architektury z OpenCV 5 **i** AWS | **PARTIAL** | ARCHITECTURE.md ma ASCII pipeline; AWS tylko lista prozą |
| Działający web endpoint **lub** screen-share | **PASS** | `https://873vdlij6g.execute-api.eu-north-1.amazonaws.com/`; strona = `web/index.html` (sha256 identyczny) |
| Wideo ≤5 min, public/unlisted: zespół, działanie, architektura, wyniki | **FAIL** | brak; draft ma `<VIDEO_URL>` |
| Raport techniczny: problem, użytkownicy, architektura, OpenCV 5, AWS, ewaluacja, ograniczenia, responsible use | **PARTIAL** | DEVPOST_DRAFT mówi „No cloud deployment was made” i „Public demo URL: none” przy żywym demo; brak sekcji responsible-use |
| Dowody ewaluacji z przypadkami porażek | **PASS** | EVIDENCE.md §8 + 3 FP na 36 czystych płyt |
| Legalność/etyka/„nie zmyślać możliwości” | **RYZYKO** | sprzeczność draft↔EVIDENCE = możliwy zarzut misrepresentation; dane syntetyczne własne (OK) |
| Zgłoszenie na Devpost przed deadline, rejestracja zespołu | **NIEZWERYFIKOWANE** | brak dostępu do konta; sprawdzić „Join hackathon” + reprezentanta |

## 3. Siedem ulepszeń — ranking po wpływie na ocenę (każde ≤4 h)
1. **Wideo 4:30 (twardy gate + 10%).** Co: nagranie 1280×720, CH: problem 0:00, live demo 0:40, architektura 2:00, wyniki 3:00, ograniczenia 4:00. Dlaczego: bez wideo zgłoszenie jest niekompletne; dodatkowo buduje Real-world impact (20%) i Documentation (10%). Czas 2,5 h. Dowód: unlisted YouTube + link w draftcie, 0 błędów konsoli w nagraniu.
2. **„Prawda w zgłoszeniu”.** Co: przepisać sekcje Deployment/Links w DEVPOST_DRAFT na żywy URL + ARN/region; jeden kanoniczny licznik testów; dodać sekcję responsible-use. Dlaczego: Documentation 10% i Cloud 10%, usuwa zarzut misrepresentation. Czas 1,5 h. Dowód: tabela „twierdzenie → komenda → wynik” wykonana na żywym URL.
3. **Baseline + krzywa P/R.** Co: `benchmark --baselines`: black-hat+`adaptiveThreshold` (znane 1219 FP), Canny+contours, FieldLens — te same seedy i matcher; plus sweep progu w 3 punktach pracy. Dlaczego: Technical execution 30% wymaga „evaluation”, a porównanie z naiwnym OpenCV jest mocniejsze niż samo F1. Czas 3 h. Dowód: tabela drukowana jedną komendą, wklejona do EVIDENCE.
4. **Dowód OpenCV 5 + głębia AWS.** Co: `/api/health` zwraca `cv2.__version__` i digest obrazu; jeden realny invoke z triggera S3 z logiem CloudWatch i request-id; `template.yaml` zgodny z wdrożonym stackiem (Image + API Gateway) + `sam validate`. Dlaczego: Cloud 10% (observability, repeatability) i Technical 30% (dowód, że 5.0 działa w chmurze). Czas 3 h. Dowód: curl health z Lambdy pokazujący `5.0.0`, wyciąg logu, `get-function` output.
5. **Unit economics z pomiaru.** Co: CloudWatch Duration p50/p95, cold vs warm, koszt/1000 obrazów przy 2048 MB i cenie eu-north-1; obok baseline czasu ręcznej inspekcji z jawnymi założeniami. Dlaczego: Real-world impact 20% = „evidence of potential benefit”, Cloud 10%. Czas 1,5 h. Dowód: tabela + jawny wzór i data cennika.
6. **Oddać input-domain guard.** Co: commit `fieldlens/quality.py` + 3 testy (już istnieją, niecommitowane) i pokazać w demo zdjęcie dokumentu → `outside_domain` zamiast listy rzekomych wad. Dlaczego: responsible operation (10%), zaufanie do wyniku (20%), UX 10% (uczciwy komunikat zamiast pewnej bzdury). Czas 2 h. Dowód: test + screenshot + JSON odpowiedzi.
7. **Dwubiegowa re-inspekcja (aktywne postrzeganie).** Co: kandydat słaby/przy krawędzi → drugi przebieg na powiększonym wycinku 2×, merge, zmierzony ΔF1 na 6 seedach. Dlaczego: Innovation 20% + Technical 30% (wynik percepcji zmienia następne działanie), bez ryzykownego „agenta”. Czas 3,5 h. Dowód: tabela przed/po + ablacja (wyłącz 2. przebieg → F1 wraca).

## 4. Czego NIE robić
**Nie ścigaj Best Use of COOL / Graviton.** Wymaga subskrypcji COOL z AWS Marketplace, realnego wdrożenia na Graviton i porównania z baseline — 3–4 dni, których nie ma, a bez twardego dowodu „COOL executes the core workload” nagroda i tak nie zostanie przyznana. Zjada czas z Technical execution (30%) i nic nie dodaje do Overall.

## 5. Jak podawać metryki, żeby były wiarygodne
- Zawsze: matcher + n + seedy, np. „F1 0.809 (IoU 0.25, bez containment; 40 płyt × 6 seedów)”.
- Nagłówek = czysty IoU 0.25; wariant „containment” tylko jako pomocniczy, jawnie oznaczony „lenient”.
- Podawaj medianę i zakres min–max, nigdy najlepszy seed (7000 jest najlepszy — to pułapka).
- Rozdzielaj detekcję (P/R/F1) od klasyfikacji (`kind_accuracy 0.778`) — nie mieszaj w jedno „accuracy”.
- Opóźnienie: p50/p95, cold vs warm, host i load; nie „real-time”, tylko „106–262 ms/płytę na współdzielonym 24-rdzeniowym hoście”.
- Koszt: wzór + założenia (pamięć, region, data cennika), nie jedna liczba z sufitu.
- Zawsze obok wyniku: przypadek porażki i ablacja (`blind detector → F1 0`), która dowodzi, że metryka reaguje.
- Jedna komenda reprodukcji przy każdym twierdzeniu; jedno źródło prawdy dla liczby testów (dziś 49/54/60/62 w różnych plikach — zmierzone 65).
