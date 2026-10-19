# ADR 0005: Strömma svar som NDJSON

- **Status:** Accepterad
- **Datum:** 2026-10-19

## Kontext
Ett svar från en lokal modell tar 1–3 s (och 17–28 s vid kallstart). Att visa texten ord för ord, med källorna först, gör verktyget upplevt snabbare och ger användaren något att stoppa. Strömmen går genom tre led: Ollama → ai-service → .NET → nginx → webbläsare.

## Beslut
- Strömmen är **NDJSON** (`application/x-ndjson`, en JSON-händelse per rad) med händelserna `sources`, `support`, `token`, `done` och `error`, i stället för Server-Sent Events. Webbläsaren skickar en `POST` med `fetch` (SSE klarar bara `GET` utan bibliotek), och NDJSON är trivialt att läsa rad för rad. nginx körs med `proxy_buffering off` för `/api/`.
- **Källor skickas före texten**, så att användaren ser vad svaret bygger på medan det skrivs.
- **Samma `rag.retrieve()`** används av både vanliga och strömmande vägen, så att de inte kan glida isär.
- **Ett stoppat eller avbrutet svar sparas** som det var, med flaggan `Interrupted` (migration), och finns kvar efter omladdning. Ett fel mitt i strömmen ger en `error`-händelse, inte ett tyst avbrott.
- Ett nekande som modellen själv skriver ("Jag hittar inget stöd…") strömmas som vilken text som helst; först i den avslutande `done`-händelsen står det `grounded: false`, och då släpper gränssnittet de utlovade källorna. En fråga som sökningen redan nekat ger bara en `done`.
- Ett **spårid** (W3C `traceparent`) följer med mellan tjänsterna; loggarna är JSON och innehåller aldrig frågetexten.

## Konsekvenser
- (+) Första ordet efter ca 0,2 s med varm modell, källor efter ca 0,3 s genom nginx. Stopp med `Esc`.
- (+) Avbrott och fel mitt i strömmen har egna tester i både .NET och frontend.
- (−) En egen läsare (`lib/stream.ts`) som måste hantera rader och tecken som delas mellan delar, i stället för färdigt SSE-stöd.
- (−) Proxyer som buffrar svar (ett vanligt fel i hosting) bryter strömmen; nginx-konfigurationen i repot är anpassad, andra miljöer måste kontrolleras.
