# Förbättringsplan: premium-UI, bättre svar, lokal drift

Utgångspunkt: fas 1 och 3 är gjorda, fas 4 är påbörjad (källvisare med markering, "Ny konversation", verifierade exempelfrågor). Inloggning och kvoter (fas 2) väntar, och allt körs lokalt tills vidare. Den här planen styr nästa arbetsperiod. Den utökar [projektplanen](projektplan.md) (fas 4–5) och ersätter inte den; ändrad ordning eller nytt scope noteras här.

Storlekar nedan är grova uppskattningar av arbetsinsats: **S** = ett kort arbetspass, **M** = några pass, **L** = en längre sammanhängande insats. De är inte mätta.

## Status
**Etapp 1 (grund): gjord 2026-10-19, med tre undantag.**
- **B0 evalset v2:** 143 räknade besvarbara + 7 följda svaga frågetyper + 40 utan svar, dev/test-delat, byggt av `eval/build_evalset.py` med automatiska kontroller mot källtexten. Mätning med 95 %-intervall, två domare som aldrig dömer sig själva, `calibrate.py`, `run_all.py`. Baslinjen står i `eval/README.md`.
- **Granskningsverktyg** (`make_review.py`, `apply_review.py`) är klara och testade. **Ingen fråga är granskad av en människa än** (du gör det sist). Domarna är heller inte kalibrerade mot en människa; `answers.py --review-sample` har skrivit `eval/review/answer-samples.md` för det.
- **C:** `scripts/start.ps1` (WSL vaken, stack, modell, uppvärmning av hela kedjan: första frågan 1,7 s i stället för 17 s), `stop.ps1`, `backup.ps1`, `restore.ps1` (återställning testad mot en separat databas). **CI-lint** (ESLint, ruff över ai-service och eval, dotnet format) är tillagd.
- **Medvetet inte gjort:** (1) `OLLAMA_KEEP_ALIVE` och `.wslconfig` (kräver ditt ok; startskriptet värmer upp modellen utan att ändra inställningar); (2) ett **andra dokumentset** för generalisering (nya filer att hämta, väntar på ditt svar om vilka); (3) **eval i CI** (kräver att CI kan hämta PDF:erna och installera torch, och kan inte provas lokalt: körs tills vidare lokalt med `run_all.py`).

**Etapp 2 (LLM-känsla): gjord 2026-10-19/20, med avvikelser.**
- **A2 streaming:** `POST /query/stream` (ai-service) och `POST /api/chat/stream` (.NET), som NDJSON (en JSON-händelse per rad) i stället för SSE: webbläsaren skickar en POST med `fetch`, där NDJSON är enklare att läsa, och nginx kör redan utan buffring. Stopp (Esc), "Svara igen" och kopiera finns. Ett stoppat eller avbrutet svar **sparas** som det var (ny kolumn `Interrupted` + migration), så det finns kvar efter omladdning. Tid till första ord med varm modell: 0,2 s; källor syns efter 0,3 s genom nginx.
- **A3:** Markdown i svaren (utan rå HTML, bara http(s)- och egna `cite:`-länkar), `[1]` och `[1, 3]` som citat-chips med hovringskort, källor som en lugn chip-rad med utdrag ett klick bort, förlopp (söker, läser, skriver). **Inte gjort:** märkena "Delvis stöd" och "Listan kan vara ofullständig" (kräver B5/B6) och **följdfrågor** (jag bedömde dem som lågt värde utan ett LLM-anrop; kan läggas till senare).
- **A1:** förfinade tokens (kall blåsvart/ljus yta, blå-violett accent), rörelse- och skuggtokens, svarstypografi, blinkande markör, gradientlogo, svävande inmatningsruta, förslagskort. Ett formellt komponentbibliotek (shadcn/Radix) valdes bort: de nya byggstenarna är få och egna, och tokens ligger på ett ställe.
- **Mätt:** Lighthouse tillgänglighet 100 och bästa praxis 100 (mobil och skrivbord); **mobil prestanda 81** (89 innan Markdown-biblioteken; Markdown och PDF-visaren laddas nu lazy). Målet ≥ 90 hör till A8.
- **Tester:** ai-service 52, backend 29, frontend 38, alla gröna.

**Etapp 3 (sökning): delvis gjord 2026-10-19/20.**
- **B4 införd** i en bättre form än planerad: hybridsökning för frågor med ärendenummer eller § (inte som en separat router i frontend), **datumfilter** (nytt) och **direkt nekande av okända nummer** (nytt). Sökning på identifierarfrågor: MRR 0,21 → 0,96 (dev), 0,12 → 0,91 (test); korrekta svar på dem 21 % → 68 %. Se `eval/README.md`, "Förbättring 1".
- **B1 grannchunkar** (en enklare variant av §-chunkning: modellen får även chunkarna bredvid varje träff) är byggt bakom `CONTEXT_NEIGHBORS` (av) och mätt på svar och förkastat (netto +1 korrekt svar, detaljfrågorna blev inte bättre; se `eval/README.md`, experiment 6).
- **B2 omrankare och B3 större embeddingmodell: skjutna upp.** På evalset v2 är sökningen redan nära taket för alla frågetyper utom identifierare (MRR 0,98 dev, 0,96–0,98 test), så de kan inte visa en vinst som går att skilja från brus; de är heller dyra (modellnedladdning, latens, omindexering och ny `min_score`). De tas när evalsetet innehåller svårare frågor skrivna av dig, eftersom det är då det syns om sökningen räcker.

**Etapp 4 (layout och återkoppling): gjord 2026-10-20.**
- **A4:** på skärmar ≥ 1280 px öppnas källvisaren **bredvid** chatten (på smalare skärmar är den kvar som sidopanel), med **zoom** (75–200 %) och **automatisk rullning till det markerade utdraget**. Inte gjort: "nästa/föregående träff på samma sida" och en filtrering av frågan till ett valt dokument i dokumentpanelen (API:et stöder `documentIds`).
- **A7:** tumme upp/ned på varje svar, en frivillig kommentar vid ned, sparat i databasen (`Rating`, `FeedbackComment`, migration, endpoint `PUT /api/chat/{id}/feedback`) och kvar efter omladdning. `eval/export_feedback.py` exporterar bedömda svar (git-ignorerade) som råmaterial till nya evalfrågor.
- **A6:** `/` fokuserar frågefältet, **Ctrl/Cmd+K** öppnar en kommandopalett (ny konversation, byt tema, visa dokument, stäng källvisaren), `↑` i ett tomt fält hämtar förra frågan, `Esc` stoppar ett svar eller stänger källvisaren, Enter/Shift+Enter som förut. Inte gjort: "dra och släpp var som helst i fönstret" (dropzonen i dokumentpanelen finns).
- **Tester:** ai-service 69, backend 32, frontend 47, alla gröna.

**Etapp 5 (smartare svar): delvis gjord 2026-10-20.**
- **B6 strukturerat svar:** byggt och mätt, **inte infört** (`STRUCTURED_ANSWER`, av). Det löste beloppsfrågan och rättade flera falska antaganden men gav två nya felaktiga nekanden, och på test föll strikt korrekthet 0,84 → 0,79 (inom bruset; domarna är överens i bara 75–84 %). Beslutsregeln uppfylls inte. Hela kedjan finns ändå på plats och testad (stödnivå i strömmen, API, databas, märket "Delvis stöd i dokumenten"), så det går att slå på när domarna är kalibrerade. Se `eval/README.md`, experiment 7.
- **B5 översiktsfrågor, i en lättviktsform:** de känns igen med ett snävt mönster, får 12 utdrag och en instruktion att säga att svaret kan vara ofullständigt, och gränssnittet visar ett märke. **Inte gjort:** förberäknade sammanfattningar per ärende vid indexering (kräver ett LLM-anrop per ärende och gör uppladdningen långsam) och riktig frågeklassificering med LLM. Räkning och "lista alla" bygger därför fortfarande på ett urval, men säger det.
- **Tester:** ai-service 93, backend 34, frontend 51.

**Vad baslinjen sa (se `eval/README.md`):** utan ärendenummer är sökningen i princip perfekt men svaren är korrekta i ca 80 %; **ärendenummer/§-frågor är bara 21 % korrekta** (retrieval), **falska antaganden rättas inte** (0 av 4), och alla 40 frågor utan svar nekas. Etapp 3 (B4) och B6 pekas därför ut som de mest värdefulla.

## 0. Principer
1. **Mät före och efter.** Inget som påverkar svaren införs utan en siffra från evalet (spår B). Ett experiment som inte hjälper dokumenteras som ett resultat, inte raderas.
2. **Känslan kommer av detaljerna.** "Premium" och "LLM-känsla" är summan av strömmande text, ren typografi, rörelse som aldrig stör, tydliga tillstånd och noll hackighet. Det är inte en ny färg.
3. **Ärlighet i gränssnittet.** Systemet ska visa när det är osäkert eller bara svarar delvis, i stället för att se fullständigt ut (kända problem: sammanfattning, räkning, "lista alla").
4. **Lokalt först.** Inget i planen kräver moln, konto eller löpande kostnad. Hostat läge är ett senare beslut.
5. **Ett spår i taget i koden, tre spår i planen.** Spår A (UI), B (svarskvalitet) och C (lokal drift) överlappar bara i ett ställe: strömmande svar (A2) ändrar API-kontraktet och görs därför före B6.

## 1. Nuläge i siffror (att jämföra mot)
| Mått | Nu | Källa |
|---|---|---|
| Rätt sida bland topp 3 (45 vanliga frågor) | 100 % (MRR 0,97) | `eval/README.md` |
| Rätt sida för ärendenummer/§-frågor (6 st) | MRR 0,25 (R@3 0,33) | experiment 4 |
| Korrekta svar, gemma3:12b | 91–93 % | `answers.py` |
| Obesvarbara frågor som nekas | 100 % (16 av 16) | `answers.py` |
| Felaktigt nekade besvarbara | 5–7 % | `answers.py` |
| Svarstid (median / kallstart) | 1,2 s / 28 s | mätt |
| Lighthouse tillgänglighet / bästa praxis | 100 / 100 | mätt |
| Frågeset | 51 + 16, **mitt utkast, ej granskat** | `eval/evalset.jsonl` |

**Viktig begränsning:** alla mått vilar på ett frågeset som jag skrev ur protokollens rubriker. Det är optimistiskt och sex av sju dokument-typer är protokoll. Därför kommer **B0 först**.

---

## Spår B: Svarskvalitet (börja här, eftersom allt annat mäts mot det)

### B0. Ett evalset man kan lita på (M, görs först)
**Mål:** minst 150 besvarbara och 40 obesvarbara frågor, uppdelade i *dev* (för att tuna) och *test* (rörs aldrig vid tuning), så att vi inte överanpassar.
- **Typer att täcka** (idag saknas flera): faktafråga, person, beslut/utfall, ärendenummer och §, tabell/belopp, jämförelse över dokument, aggregering ("hur många"), sammanfattning, flerstegs, frågor med felaktigt antagande ("totalsumman" som inte finns), vaga frågor, andra dokumenttyper.
- **Källor till frågor:** (1) du skriver 40–60 egna på det sätt du själv skulle fråga (viktigast, för att få riktiga formuleringar); (2) jag genererar kandidater ur dokumenten och du **granskar och rättar** dem; (3) senare riktiga frågor från testare med tummen upp/ner (A7).
- **Ett andra dokumentset** (t.ex. en årsredovisning, en detaljplan och en policy) för att se om förbättringar generaliserar utanför protokoll.
- **Bättre mätning:** konfidensintervall (bootstrap) på alla huvudtal; en annan domare än den som svarar (gemma dömer qwen och tvärtom) och **30 stickprov som du bedömer för hand** för att kalibrera domaren; mät även *delvis svar* och *citerar rätt sida*.
- **Beslutsregel:** ett förslag antas om det förbättrar MRR eller korrekthet med minst 0,02 på dev, inte försämrar något på test och inte kostar mer än 2 s i median.
- **Klart när:** `eval/README.md` har resultat med intervall på dev och test, och ett kommando (`eval/run_all.py`) kör allt.

### Experimentkö (efter B0, i ungefär den här ordningen)
Varje rad är en hypotes som ska bekräftas eller förkastas av siffrorna.

| # | Experiment | Hypotes | Storlek | Risk |
|---|---|---|---|---|
| B1 | **§-medveten chunkning**: dela protokoll vid `§ N Ärendenummer …`, varje ärende är en enhet med ärendetiteln som rubrik; ärenden över ~900 tecken delas på stycken. Hämta bästa chunk och ge modellen hela ärendet ("förälder") | Ett ärende är den naturliga svarsenheten. Ger bättre träff på §-/ärendenummerfrågor, rena markeringar och mindre avklippta resonemang | M | Fungerar bara för protokoll; behöver reservväg (nuvarande chunkning) för andra dokument |
| B2 | **Omrankare** (cross-encoder, t.ex. `bge-reranker-v2-m3`): hämta 30, ranka om, ta 5 | Rätt chunk finns oftast redan i topp 10 men ligger på plats 2–6; omrankning flyttar upp den. Störst effekt på R@1 | M | +0,3–1 s latens; extra VRAM (≈1–2 GB) |
| B3 | **Större embeddingmodell** (`multilingual-e5-base`/`-large` eller `bge-m3`) | e5-small är den minsta varianten; poängen är hoptryckta (0,81–0,88) och det gör tröskeln skör | M | Ny dimension → ny kolumn, omindexering och ny `min_score`; trögare indexering |
| B4 | **Identifierar-router**: ärendenummer eller `§ N` i frågan → nyckelordssökning, annars vektor | Simulerat MRR 0,947 mot 0,889 på 51 frågor (n=6 för identifierare, så osäkert) | S | Bygger på handvald delmängd; måste mätas på fler frågor (B0) |
| B5 | **Frågeklassificering och routing** (se nedan) | Fel strategi för fel frågetyp är största kvarvarande felet | L | Klassificeraren kan ha fel; ska kunna falla tillbaka på standardflödet |
| B6 | **Strukturerat svar i stället för strängjakt** (se nedan) | Löser "Jag hittar inget stöd" när ämnet finns men det efterfrågade saknas | M | Modellen måste hålla JSON-format; mät felfrekvens |
| B7 | **Bättre PDF-tolkning**: kolumner och tabeller (PyMuPDF/pdfplumber), OCR för skannade PDF:er (Tesseract `swe`) | Belopp i tabeller och skannade dokument är idag opålitliga eller omöjliga | L | Tung beroendekedja; OCR-kvalitet varierar |
| B8 | **Modelljämförelse igen** när något nytt finns (och Qwen3 med tänkandet avstängt) | Qwen3:s 4,8 s kan bero på tänkande-läget, ej undersökt | S | – |

**B5 Frågeklassificering och routing.** Idag behandlas alla frågor lika. Förslag på fem typer och vad som ska hända:
- *Uppslag* (fakta, beslut, person): dagens flöde, med B1/B2.
- *Ärendenummer/§*: B4.
- *Sammanfattning* ("sammanfatta protokollet", "vad hände på mötet"): **sammanfatta per ärende vid indexering** och spara sammanfattningarna som egna sökbara chunks; svaret byggs av dem. Aldrig av fem slumpade utdrag.
- *Aggregering/räkning/lista alla* ("hur många yrkanden avslogs"): hämta betydligt fler utdrag (15–30), låt modellen gå igenom dem i omgångar (map-reduce) och **säg uttryckligen att listan kan vara ofullständig** när träfflistan är avkortad.
- *Jämförelse*: en hämtning per sak som jämförs, sedan ett svar.
Klassificeringen görs först med enkla regler och ett litet LLM-anrop; mät hur ofta den har rätt innan den får styra något.

**B6 Strukturerat svar.** Modellen returnerar JSON: `{"stod": "fullt"|"delvis"|"inget", "svar": "...", "citat": [1,3]}`. Konsekvenser: (1) nekandet avgörs av `stod`, inte av att en mening finns i texten, vilket löser frågan om "totalsumman"; (2) "delvis" visas i gränssnittet som ett tydligt märke ("Delvis stöd i dokumenten"); (3) citaten valideras (finns `[n]`, ligger den på rätt sida) innan svaret visas. Kräver att strömmande svar (A2) hanterar JSON eller att strömmen bara gäller `svar`-fältet.

### Mål för spår B (efter B0 satt som riktvärden, justeras när vi sett riktiga intervall)
- Rätt sida i topp 1 ≥ 0,92 på dev-frågor och ≥ 0,70 på identifierarfrågor.
- Korrekta svar ≥ 95 %, felaktigt nekade ≤ 3 %, obesvarbara nekade ≥ 95 %.
- Inga frågetyper som *ser* fullständiga ut men inte är det: aggregering och sammanfattning ska antingen svara bra eller tydligt säga att de är ofullständiga.

---

## Spår A: Premium-UI med "LLM-känsla"

### Designriktning
Referensen är den ro och snabbhet man känner i moderna AI-chattar: en smal, lugn läskolumn, svaret som **växer fram ord för ord**, få men välgjorda kontroller och inga onödiga ramar. Vi kopierar inget varumärke, vi bygger ett eget uttryck.
- **Typografi:** nuvarande Inter, men med tydlig skala (svarstext 16–17 px, radavstånd ca 1,65), `font-feature-settings` för tabelltal, och svensk citat-/tankstreckstypografi. Kod/§-nummer i monospace där det hjälper.
- **Färg:** ett diskret, mättat accentspektrum, neutrala ytor med tre nivåer av djup, och riktiga kontrastkrav (AA) i både ljust och mörkt. Mörkt läge är standard-känslan men ljust ska vara lika välgjort.
- **Rörelse:** bara tre standardkurvor och tider (snabb 120 ms, normal 200 ms, lugn 320 ms). Allt respekterar `prefers-reduced-motion`.
- **Designtokens** i en fil (`src/styles/tokens.css`) så att hela uttrycket kan justeras på ett ställe. Befintliga Tailwind-klasser flyttas till tokens.
- **Varumärke:** namn, logotyp och favicon finns men är enkla. Ett kort pass för en ordentlig logotyp och en egen "empty state"-illustration (SVG) ingår i A8.

### A1. Designsystem och grunder (M)
- Tokens (färg, avstånd, radier, skuggor, rörelse), komponentbibliotek med få, genomtänkta byggstenar: knapp, ikonknapp, chip, kort, dialog/sheet, tooltip, skelett, toast, menyer. (Projektplanen nämner shadcn/ui; om vi använder den ska det vara för tillgängliga primitiver (Radix), inte för utseendet.)
- Global tangentbordsfokus-stil, skip-länk, `aria-live` för strömmande text.
- **Klart när:** alla befintliga skärmar använder komponenterna, ingen hårdkodad färg finns kvar, Lighthouse ≥ 95 behålls.

### A2. Strömmande svar (SSE) end to end (L, **kärnan i LLM-känslan**)
- **Ollama** strömmar redan (`stream: true`). **ai-service:** ny endpoint som strömmar händelser: `sources` först (så att källorna syns direkt), därefter `token`-delar, sist `done`. **.NET:** vidarebefordrar som Server-Sent Events (`IAsyncEnumerable<SseItem>`), sparar det färdiga svaret i historiken först när strömmen är klar (och vid avbrott: sparar det som hunnit komma, märkt som avbrutet). **Frontend:** läser strömmen, visar text allt eftersom, behåller `POST /api/chat` som reserv.
- **Avbryt/stopp** (knapp som byter plats med skicka), **återgenerera** och **kopiera**.
- Tid-till-första-ord ska mätas och visas i loggen (mål: < 1,5 s när modellen är varm).
- **Klart när:** ett svar börjar synas inom 1,5 s och avbrott städar korrekt hos alla tre lagren (med tester för avbrutet svar och nätverksfel mitt i strömmen).

### A3. Rikt svarsinnehåll (M)
- **Markdown i svar** (listor, fetstil, tabeller, citat) med en säker renderare utan rå HTML; modellen instrueras skriva Markdown.
- **Inline-citat som chips** `[1]` som visar ett **hovringskort**: dokumentnamn, sida och de första raderna av utdraget; klick öppnar visaren. Tangentbordsnåbart.
- **Laddningsrad med steg** i stället för tre prickar: "Söker i 6 dokument → hittade 5 utdrag i 3 dokument → skriver svaret". Det är stegen från strömmen (A2) och ger den "tänker på riktigt"-känslan utan att visa interna detaljer.
- **Märken** för osäkerhet: "Delvis stöd i dokumenten", "Listan kan vara ofullständig" (från B5/B6).
- **Följdfrågor** (2–3 förslag efter svaret). Börja regelbaserat från källorna, inte med ett extra LLM-anrop.

### A4. Layout: chatt och dokument sida vid sida (M)
- På bred skärm öppnas källvisaren som en **delad vy** bredvid chatten i stället för en overlay, så man kan läsa svaret och beviset samtidigt. På smal skärm är det kvar som helskärmsark.
- Källvisaren: zoom, föregående/nästa träff (om flera utdrag på samma sida), mjuk rullning till markeringen, och en liten "var på sidan"-indikator. (Markeringen finns redan.)
- Dokumentpanelen: sökning/filter, tydlig status, framsteg vid indexering och "filtrera frågan till valt dokument" (API:et stöder redan `documentIds`).

### A5. Konversationer (M)
- Flera sparade konversationer med automatiskt genererad rubrik, en smal sidokolumn som kan fällas ihop, och **Ny konversation** (finns) som skapar en ny i stället för att radera.
- Det kräver en `Conversation`-tabell i backend (migration) och att historik-API:et grupperas på konversation. Eftersom roller/delning är utanför scope gäller konversationerna fortfarande en enda ägare.
- *Nytt scope jämfört med projektplanen;* tas bara om du vill ha det.

### A6. Kontroller, genvägar och inmatning (S–M)
- Inmatningsfältet: växande, `Enter` skickar, `Shift+Enter` radbryter (finns), `↑` hämtar senaste frågan, `Esc` stoppar strömmen, `/` fokuserar fältet, `Ctrl/Cmd+K` öppnar en kommandopalett (ny konversation, byt tema, öppna dokument, hoppa till konversation).
- Dra-och-släpp var som helst i fönstret för uppladdning, med framsteg per fil.

### A7. Återkoppling (S–M)
- Tumme upp/ned på varje svar och valfri kommentar vid ned. Sparas i databasen (migration) och blir indata till evalsetet (B0). Visa aldrig mer än en liten, snygg animation.

### A8. Polering och helhet (M)
- **Skelett** i stället för tomma ytor, genomtänkta **tomma lägen och felmeddelanden** (offline, kallstart, inget indexerat), första-gången-välkomst som förklarar vad systemet kan och inte kan (ärligt: ingen sammanfattning av hela dokument än), mjuk skiftning ljust/mörkt.
- Mobil: samma kvalitet, inte "det fungerar". Gester och tumvänliga ytor.
- Logotyp, favicon, öppen-graf-bild, titel. **Skärmbilder och en 60–90 s demovideo** till README.
- **Klart när:** en genomgång på laptop och mobil visar inga ojämna kanter; Lighthouse tillgänglighet ≥ 95 och prestanda ≥ 90 på mobil; manuellt test med tangentbord och en skärmläsare.

### Ordning inom spår A
A1 → A2 → A3 → A4 → A7 → A6 → A5 → A8. A2 är det som mest förändrar upplevelsen, och A3 bygger på strömmen.

---

## Spår C: Lokal drift (löpande, litet men viktigt)
Allt körs på din dator. Det som gör det *pålitligt* att visa upp och testa:
- **Ett kommando för att starta allt** (`scripts/start.ps1`): håller WSL vaken, startar Docker-stacken, kontrollerar att Ollama svarar på rätt adress, värmer upp modellen (så att första frågan inte tar 28 s) och skriver ut länken. Plus `stop.ps1`.
- **`OLLAMA_KEEP_ALIVE`** satt så att modellen inte lämnar minnet mellan frågor (kräver ett ok från dig, det är en inställning på din dator).
- **Hälsosida** (`/status`) som visar databas, AI-tjänst, modell laddad/inte, och version. Gränssnittet visar redan "AI online/offline".
- **`.wslconfig`** med minnesgräns så att `VmmemWSL` inte äter allt (kräver ditt ok).
- **Säkerhetskopia** av databas och uppladdade filer med ett kommando (`scripts/backup.ps1`) och återställning som är testad.
- **Observability** (fas 5): strukturerade loggar med ett id som följer varje fråga genom alla tre tjänster, och latens per steg (hämtning, omrankning, generering).
- **Reservläge** när modellen är av: gränssnittet visar redan offline-läge; lägg till en *inspelad exempelsession* så att någon utan din dator ändå kan se hur det fungerar (fas 5-krav).
- **CI:** lint (ESLint, ruff, `dotnet format`) och ett Playwright-flöde (ladda upp → fråga → klicka källa → markering syns). **Eval i CI:** retrievalmätningen (`retrieval.py`) behöver bara embeddingmodellen och databasen, så den kan köras på en vanlig CPU-runner (ca 30 s plus installation av torch) och falla om recall eller MRR sjunker under en gräns. Svarsmätningen (`answers.py`) behöver Ollama och körs bara lokalt.

---

## Tidsordning (förslag)
| Etapp | Innehåll | Resultat |
|---|---|---|
| **1. Grund** | B0 (evalset v2 + mätning), C: startskript och keep-alive, CI-lint | Siffror vi kan lita på och en pålitlig lokal miljö |
| **2. LLM-känsla** | A1 (designsystem), A2 (streaming), A3 (markdown, citat-chips, steg) | Gränssnittet *känns* som en modern AI-chatt |
| **3. Sökning** | B1 (§-chunkning), B2 (omrankare), B3 (embeddingmodell), B4 (router) | Mätbart bättre träff, särskilt på ärendenummer |
| **4. Layout och återkoppling** | A4 (delad vy), A7 (tummar), A6 (genvägar) | Läsa svar och bevis samtidigt, första riktiga data |
| **5. Smartare svar** | B5 (routing, sammanfattning per ärende), B6 (strukturerat svar), A3-märken | Ärliga och bättre svar på svåra frågetyper |
| **6. Helhet** | A5 (konversationer, om önskat), A8, B7 (tabeller/OCR), C: backup, observability, demovideo, README, ADR:er | Något man kan visa upp och lämna ifrån sig |

Etapp 1 måste komma först. Etapp 2 och 3 kan byta plats om du vill se UI-resultat snabbare, men **då mäter vi inte förbättringarna i etapp 3 mot ett granskat evalset**.

## Beslut och underlag jag behöver från dig
1. **Evalsetet:** 30–60 minuter då du granskar och kompletterar de frågor jag föreslår, plus ~40 egna i din egen formulering. Utan detta är varje kvalitetspåstående ett utkast.
2. **Smak i UI:** accentfärg/stämning (föreslag: lugn, nästan svartblå med en kall accent, men säg om du vill åt annat), och om du vill ha **konversationer** (A5) eller räcker "Ny konversation".
3. **Dokumentmängd för generalisering:** vilka 3–4 andra dokument (årsredovisning, detaljplan, policy …) får vi lägga till som testmaterial, och är de offentliga?
4. **Inställningar på din dator** (separata ok): `OLLAMA_KEEP_ALIVE`, `.wslconfig`, ev. en ny modell via Ollama om vi jämför fler.
5. **Scope:** A5 (konversationer) och B7 (OCR/tabeller) är utökningar jämfört med projektplanen. Säg om de ska med eller vänta.

## Risker
| Risk | Konsekvens | Åtgärd |
|---|---|---|
| Förbättringar som bara gäller protokoll | Ser bra ut på demomaterialet, sämre på annat | Andra dokumentuppsättningen i B0, reservväg för icke-protokoll |
| Överanpassning till evalsetet | Falsk säkerhet | dev/test-delning, intervall, riktiga frågor från A7 |
| Strömmande svar + strukturerat svar krockar | Dubbelt arbete | Gör A2 först, designa strömmen så att den bär `stod`/`citat` som sista händelse |
| Omrankare/större embedding ökar latens och VRAM | Långsammare app, minnesbrist med LLM | Mät latens/VRAM i varje experiment, beslutsregeln tillåter max +2 s |
| LLM-domaren är partisk | Felaktiga kvalitetssiffror | Annan domare + 30 handbedömda stickprov |
| Mycket UI-arbete utan feedback | Fel riktning | Skärmbilder efter varje etapp; du bestämmer innan nästa etapp börjar |

## Definition av "klart" för den här planen
- Granskat evalset (dev/test) och alla huvudmått med konfidensintervall i `eval/README.md`.
- Svaret strömmas, har Markdown, klickbara citat med förhandsvisning, stopp/återgenerera/kopiera och tumme.
- Dokument och svar visas sida vid sida med markerat utdrag.
- Minst B1–B4 mätta och antingen införda eller förkastade med siffror.
- Kända svaga frågetyper svarar bra eller märker tydligt att de är ofullständiga.
- Ett kommando startar hela miljön och värmer upp modellen; säkerhetskopia och återställning är testade.
- README med utvärderingstabell, skärmbilder och demovideo; ADR:er för besluten.
