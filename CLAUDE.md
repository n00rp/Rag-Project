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
- **Fas 1 klar** (lokalt end-to-end med *falska* backends): uppladdning → bakgrundsindexering → fråga → svar med källor, PDF-visare, ljust/mörkt, mobil, offline-läge. Tester: ai-service 38 (nu 41), backend 21, frontend 13, alla gröna.
- **Gjort efter fas 1:** Å/Ä/Ö-normalisering (NFKC) + regressionstester i alla lager; borttagning av upprepade sidhuvuden (`app/boilerplate.py`, `STRIP_PAGE_BOILERPLATE`) verifierad på de sex riktiga protokollen; demoskript.
- **Verifierat på stationären (2026-10-12, RTX 5080):** baslinjetester gröna (ai-service 38, backend 21, frontend 13); riktig embeddingmodell (e5-small, dim 384) indexerade alla sex protokoll (397 sidor, 602 chunks); Ollama med riktig LLM svarar via hela kedjan. Tokens/s för en kort svensk sammanfattning (fristående mätning, VRAM = totalt använt, modeller kan ligga kvar i minnet): qwen3:14b 81, gemma3:12b 89, llama3.1:8b 126. Alla tre ger begriplig svenska; qwen3:14b är inställd i `.env` (jämförd i RAG-svar i fas 3, se nedan).
- **Första kvalitetsintrycket (qwen3:14b):** "Vem anmälde jäv 2025-04-09?" ger Hampus Magnusson med rätt källa (s. 36, § 317). "Investeringar i europeisk försvarsindustri" ger felaktigt "inget stöd" trots att § 317 på s. 36 behandlar det: retrieval-miss, underlag till evalsetet. Träffpoängen är mycket platta (0,81-0,87 för alla källor), så `min_score` kunde inte tunas förrän evalsetet fanns (gjort i fas 3, se nedan).
- **Docker verifierat:** `docker compose up --build` bygger alla tre images (ai-service 1,9 GB) och stacken svarar end-to-end; ai-service når Ollama via WSL-gatewayen (se dev-setup.md). Docker-volymen `uploads` är separat från filerna som laddades upp via lokal körning, så PDF-visaren behöver nya uppladdningar i Docker.
- **INTE verifierat än:** CI efter fas 3-ändringarna (CI var grönt t.o.m. 596701a). Miljö: lokal Postgres i WSL (`postgresql@16`) måste vara avstängd, den tar port 5432; Python når inte goteborg.se utan Windows-certifikatlagret (första `fetch` gav SSL-fel, löste sig efter en curl-förfrågan).
- **Fas 3 påbörjad (2026-10-12):** `eval/` har evalset (44 besvarbara + 16 obesvarbara, utkast som användaren ska granska), `retrieval.py` (recall@k/MRR/nej-svar-tröskel) och `answers.py` (hela kedjan + LLM-domare). Resultat i `eval/README.md`. Slutsatser: sidhuvudsrensning utan dokumentrubrik sänker MRR (0,894 mot 0,951), rensning + rubrik ger 0,973 och är nu standard (`DOC_HEADER`); `min_score` satt till 0,83 och gäller bara bästa träffen (e5-small, mätt: behåller korrektheten, nekar alla obesvarbara; tröskel per träff tappade § 317, se eval/README.md); gemma3:12b bäst (93 % korrekt, 1,2 s median), llama3.1:8b nekar för mycket (30 %), qwen3:14b 84 % och 4,8 s. Domaren är qwen3 själv, så "förankring" (100 %) är för snällt. Kvar i fas 3: granska/utöka evalset för hand, hybridsökning/omrankning som experiment, eval i CI, tänkande-läge för Qwen3, LLM_MODEL=gemma3:12b i docker-miljön (images är inte ombyggda efter detta).
- **Härnäst:** fas 2 (JWT/inloggning bakom `ICurrentUser`, rate limits, kvoter, uppladdningsskydd) och fas 3 (evalset 40–60 frågor, retrieval-/svarsmått, ≥3 experiment, `min_score`-tröskel, nej-svar). Fas 3 är det som får projektet att sticka ut.
- **Öppna beslut:** vilken Ollama-modell (välj via eval, jämför ≥2 på svenska); hosting av demon (rekommenderat: appen på gratis moln-VM, LLM via Cloudflare Tunnel/Tailscale från hemmadatorn, reservläge när GPU:n är av; se projektplanen "Budget 0").

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
- `min_score` är 0 (av) tills fas 3 har tunat den. e5-modeller kräver prefixen `query: `/`passage: ` (görs i `embeddings.py`). Dimension 384; byte av modell kräver ny kolumn/omindexering.
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
