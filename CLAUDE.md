# Projektminne för Claude

Läses automatiskt vid sessionsstart. Håll den här filen kort och aktuell: den ersätter att läsa in hela historiken. Uppdatera avsnittet "Status" när något ändras. Stegvis guide för stationären: [docs/handoff-desktop.md](docs/handoff-desktop.md).

## Användaren och arbetssätt
- Junior utvecklare med AI/ML-utbildning som söker jobb i Sverige. Projektet är portfolio-flaggskeppet och ska vara **färdigt, visuellt polerat, funktionellt starkt och sticka ut**. Hellre ett klart projekt än flera halvfärdiga. Budget 0 kr.
- Kommunicera på **svenska**. Kod, identifierare och commit-meddelanden på engelska.
- **Aldrig** `Co-Authored-By`, "Generated with Claude Code" eller liknande i commits/PR (användaren vill inte ha Claude som contributor). Commits ska ha bra rubrik + brödtext som förklarar *varför*.
- Håll dokumentationen aktuell (README, ADR i `docs/adr/`, den här filen) i samma commit som ändringen.
- Verifiera på riktigt innan du säger att något fungerar (kör testerna, kör flödet). Rapportera ärligt vad som inte är testat.
- Följ [docs/projektplan.md](docs/projektplan.md) fas för fas; "Utanför scope" är förbjudet. Nya idéer går till `docs/ideas.md`. Stacken är beslutad och byts inte utan att användaren ber om det.
- Ladda ner filer, installera system-program och pusha bara när användaren har bett om det.

## Vad det är
**Kommunkoll**: ladda upp kommunala PDF:er, ställ frågor på svenska, få svar (RAG) med dokument + sida som källa; klick öppnar PDF:en på rätt sida. Demosamling: sex Göteborgs-protokoll (`python scripts/demo_docs.py fetch|seed`). Repo: https://github.com/n00rp/Rag-Project

## Arkitektur
React 19/TS/Vite/Tailwind 4 (`frontend/`) → .NET 10 minimal API + EF Core (`backend/`, äger användare/metadata/jobbkö/filer) → Python/FastAPI (`ai-service/`, äger PDF→chunks→embeddings→sökning→LLM) → Postgres 17 + pgvector (schema `public` för .NET, `rag` för Python). LLM via Ollama bakom ett eget interface. Se ADR 0001/0002 och README.

| Tjänst | Dev-port | Docker-port |
|---|---|---|
| frontend (Vite / nginx) | 5173 | 3000 |
| .NET API | 5174 | 8080 |
| ai-service | 8000 | 8000 |
| Postgres | 5432 | 5432 |

## Status (uppdatera!)
- **Läge (2026-10-19):** allt kör lokalt (RTX 5080, Ollama gemma3:12b, Docker i WSL2). Ingen inloggning (fas 2 väntar) och ingen publik demo; hosting är ett senare beslut. Styrdokument: [docs/forbattringsplan.md](docs/forbattringsplan.md) (etapp 1-6 gjorda utom det som står under "Kvar").
- **Byggt:** strömmande svar (NDJSON, stopp, avbrutna svar sparas), premium-UI med dockad källvisare/kommandopalett/tumme upp-ned, hybridsökning för ärendenummer och § + datumfilter + nekande av okända nummer, översiktsfrågor (flagga `broad`), strukturerat svar med stödnivå (byggt men **avstängt**, `STRUCTURED_ANSWER`), JSON-loggar med spårid, `scripts/start|stop|backup|restore.ps1`, inspelad exempelsession för offline-läge.
- **Tester (alla gröna 2026-10-19):** ai-service 112, backend 35, frontend 54. CI (ESLint, ruff, `dotnet format`, alla tester): commits t.o.m. `4e25897` är pushade 2026-10-19 men CI-resultatet har inte kunnat läsas (repot är privat, webbläsarpanelen inte inloggad); senare commits är lokala. Pusha bara när användaren ber om det.
- **Utvärdering:** `eval/` (frågeset v2, dev/test, intervall, två domare). MRR 0,977 dev / 0,959 test; identifierarfrågor 21 % -> 68 % korrekta; 44 av 44 obesvarbara nekas. Allt är i [eval/README.md](eval/README.md); experimenten (sidhuvud, chunkstorlek, tröskel, hybrid, grannchunkar, strukturerat svar) och vad som förkastades står där och i ADR 0003-0006.
- **HR-biblioteket (2026-10-24):** AB 25 + kommentarer + bilagor + 12 lagar (`python scripts/fetch_hr_docs.py --seed`, data i `data/hr` och `data/ab`, git-ignorerade) och 77 HR-frågor (`eval/hr_questions.py`, körs med `eval/hr_check.py`). Nytt: `app/columns.py` (tvåkolumnsläsning, pdfplumber), avstavningsfix i `normalize_text`, rubriketiketter per Kap./§ för avtal och lagar (`heading_style`; avstängd för protokoll, där den sänkte sökningen). Resultat: 48/70 rätt med e5-small, **64/70 (91 %) med e5-base + omrankare bge-reranker-v2-m3 på GPU**, protokollen oförändrade (MRR 0,977/0,959); strömmat genom appen: källor efter 0,25 s, första ordet 0,7–0,9 s, helt svar 0,8–2,6 s (sökning 0,27 s; använd 127.0.0.1, inte localhost, i Pythonklienter: localhost ger +2 s IPv6-väntan). **Infört lokalt:** `.env` har `AI_SERVICE_HOST=windows`, så `scripts/start.ps1` kör ai-service som Windows-process (`ai-service/.venv` har CUDA-torch 2.11+cu128, RTX 5080) och API-containern pekar dit via `AI_SERVICE_URL`; modell e5-base, dim 768, `MIN_SCORE` 0,82; `scripts/reindex.py` indexerar om allt (3 min) efter modellbyte; dimensionsbyte kräver `RESET_VECTORS_ON_DIM_CHANGE=true` en gång. Docker-läget (tomt `AI_SERVICE_HOST`) kör CPU utan omrankare. Modellen är `gemma3-12b-8k` (lokal Ollama-variant med num_ctx 8192; standardens 4096 kapade översiktssvar). Frågor som listar flera ämnen delas upp (`rag.topics`). Senaste körning: 66/73 (80 frågor inkl. 3 flerämnesfrågor). `HYBRID_ALL` och `TOP_K=8` mätta, inte införda. Se eval/README.md.
- **Kända svagheter:** frågorna är ogranskade (`reviewed: false`) och domarna okalibrerade mot en människa; falska antaganden rättas inte; översikter är urval; skannade PDF:er/tabeller stöds inte; mobil Lighthouse-prestanda 81.
- **Kvar / väntar på användaren:** granska frågorna (`python eval/make_review.py` -> fyll i `eval/review/evalset-review.md` -> `apply_review.py` -> `build_evalset.py`) och bedöma `eval/review/answer-samples.md` för `calibrate.py`; push; öppna beslut: accentfärg, konversationer (A5), andra dokumenttyper, `OLLAMA_KEEP_ALIVE`/`.wslconfig`, OCR/tabeller (B7). Ej byggt: Playwright-E2E, eval i CI, mobil prestanda >= 90.
- **Miljö:** lokal Postgres i WSL måste vara avstängd (tar port 5432); Python når inte goteborg.se utan Windows-certifikatlagret (gör en curl-förfrågan först). Detaljer i [docs/dev-setup.md](docs/dev-setup.md).

## Kommandon
```bash
docker compose up -d db                                   # databasen (i WSL: docker körs där)
cd ai-service && .venv/Scripts/python -m pytest -q        # kräver db; EMBEDDING_BACKEND/LLM_BACKEND=fake i tester
cd backend && dotnet test                                 # kräver db; skapar engångsdatabaser
cd frontend && npm test && npm run build
cd backend && dotnet tool run dotnet-ef migrations add <Namn> --project src/DocAssistant.Api --output-dir Data/Migrations
```
Köra tjänsterna för hand: se README "Utveckla tjänst för tjänst". `.env.example` listar alla variabler (`EMBEDDING_BACKEND`, `LLM_BACKEND`, `OLLAMA_BASE_URL`, `LLM_MODEL` …).

## Viktiga designbeslut och fallgropar
- **Dataisolering:** `owner_id` är obligatorisk i varje vektorfråga (`ai-service/app/db.py`); .NET sätter den via `ICurrentUser` (idag `DemoUser` = "demo"). Test bevisar att ägare A inte ser B:s data. Rör aldrig detta utan att behålla testet.
- **Källhänvisningar:** prompten numrerar utdragen `[1]..[k]` i samma ordning som `sources`; frontend gör `[n]` klickbart. Ändra inte ordningen på ett ställe.
- **Svenska:** all text och alla frågor normaliseras med `app/text.normalize_text` (NFKC, tar bort NUL). Test-PDF:er med åäö måste använda inbäddat TrueType-typsnitt (se `tests/test_swedish_text.py`, `TEST_TTF_FONT`).
- **Boilerplate-rensning:** maskera bara sidans *eget* nummer, aldrig alla siffror (då försvinner `§ 289 Ärendenummer SLK-…`). Bara första 6/sista 3 icke-tomma raderna räknas.
- `min_score` är 0,82 (e5-base; 0,83 var e5-small) och gäller bara bästa träffen (ADR 0004). e5-modeller kräver prefixen `query: `/`passage: ` (görs i `embeddings.py`). Dimension 768; byte av modell kräver `RESET_VECTORS_ON_DIM_CHANGE` och `scripts/reindex.py`. Tester kör mot samma dev-databas: kör inte med annan `EMBEDDING_DIM` än databasens.
- PDF-filen serveras **inline** (inget nedladdningsnamn) så att iframe-visaren fungerar; frontend använder `#page=N&navpanes=0`.
- AI-tjänsten nere → .NET returnerar `503` med `code: "ai_unavailable"` (central `ApiExceptionHandler`); frontend visar offline-läge.
- Backend-tester använder en riktig Postgres (engångsdatabas per testklass), inte in-memory. `TEST_PG_ADMIN` åsidosätter anslutningen.
- `.NET`-paketen för EF Core är fästa på samma version (10.0.12) för att undvika versionskonflikt med Npgsql-providern.

## Miljöfallgropar (Windows)
- Docker Engine körs i **WSL2 (Ubuntu)**, inte Docker Desktop. WSL stänger av sig själv och stoppar då containrar: håll den vaken (`wsl -d Ubuntu -- sleep infinity` i bakgrunden) eller ha en Ubuntu-terminal öppen. Docker-kommandon körs via `wsl -d Ubuntu -u martin -- bash -c "cd /mnt/c/... && docker ..."`.
- PowerShell-konsolen visar åäö som `�` när Python skriver UTF-8. Det är bara visningen: kör Python med `-X utf8`, skriv till fil och läs filen som UTF-8 när du verifierar text.
- Kör Python som läser nedladdade filer med `-I` och från en annan mapp än datamappen.
- Vite-mallen med `--no-interactive` gav vanilla-TS; projektet är manuellt konfigurerat för React.
- `.claude/` är git-ignorerad (lokal preview-konfiguration).
