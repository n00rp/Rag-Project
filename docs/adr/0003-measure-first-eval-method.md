# ADR 0003: Mät först – frågeset med dev/test, intervall och flera domare

- **Status:** Accepterad
- **Datum:** 2026-10-19

## Kontext
Det första frågesetet (51 + 16 frågor, v1) gav siffror som såg bra ut (93 % korrekta svar), men en skillnad på en fråga var 2,3 procentenheter, justeringar valdes på samma frågor de mättes på, och domaren var samma modell som en av de bedömda. Varje förändring av sökning eller prompt behövde kunna avgöras utan att lura oss själva.

## Beslut
- **Frågeset v2** (`eval/evalset.jsonl`): 143 räknade besvarbara frågor och 44 som saknar svar, genererade av `build_evalset.py` ur protokollen. Bygget misslyckas om en förväntad § saknas, om ett påstått faktum inte står i källtexten eller om ett ord i en nej-fråga ändå finns i dokumenten.
- **dev/test-delning.** Inställningar väljs på dev; test tittar vi på först när ett beslut ska fattas.
- **Intervall.** Alla huvudsiffror redovisas med 95 % bootstrap-intervall. Med 56–87 frågor per del är 0,02 oftast brus.
- **Flera domare.** qwen3:14b och llama3.1:8b bedömer korrekthet och förankring; en modell dömer aldrig sig själv (gemma3 genererar). "Korrekt (strikt)" kräver att alla domare håller med, "minst en domare" är den övre gränsen. Domarnas överensstämmelse (75–94 %) redovisas.
- **Beslutsregel:** ett förslag antas om det ger minst +0,02 på dev, inte försämrar något på test och inte kostar mer än 2 s i median.
- **Retrieval mäts separat från svar** (`retrieval.py`, utan LLM, ca en minut) så att en sökförändring kan bedömas utan att brusiga domare är med.
- Alla frågor är märkta `reviewed: false` tills en människa gått igenom dem; `make_review.py` → `apply_review.py` → `build_evalset.py` bygger in besluten.

## Konsekvenser
- (+) Fyra idéer har förkastats eller stängts av med siffror i stället för magkänsla (se `eval/README.md`).
- (+) Siffrorna går att reproducera: rådata ligger i `eval/results/`.
- (−) Frågorna är skrivna av utvecklaren utifrån protokollens struktur, vilket gör sökningen lättare än för riktiga användare. Siffrorna är optimistiska tills någon annan granskat dem.
- (−) LLM-domare är brusiga (qwen3 underkänner ibland praktiskt taget oförändrade svar) och är inte kalibrerade mot en människa. `calibrate.py` är förberedd men inte körd. Därför går små skillnader inte att avgöra med domarna ensamma.
- (−) Utvärderingen körs lokalt (kräver Ollama) och ingår inte i CI.
