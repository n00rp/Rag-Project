# Överlämning: komma igång på den stationära datorn (RTX 5080)

Mål med den här sessionen: köra projektet med **riktig embeddingmodell och riktig LLM** för första gången, och se hur svenskan och de riktiga protokollen fungerar. Fas 1 är redan klar och testad med falska backends på laptopen; allt nedan är det som återstår att verifiera.

> Claude: läs först [CLAUDE.md](../CLAUDE.md) (läses automatiskt) och sedan detta dokument. Du behöver inte läsa resten av repot förrän en uppgift kräver det. Kör `git log --oneline -15` för att se var vi står.

## 0. Förutsättningar (kontrollera, installera bara det som saknas)
| Verktyg | Kontroll | Anmärkning |
|---|---|---|
| Git | `git --version` | |
| WSL2 + Ubuntu + Docker Engine | `wsl -l -v`, `wsl -d Ubuntu -- docker --version` | Stegen står i [dev-setup.md](dev-setup.md). Docker Desktop används inte. |
| .NET 10 SDK | `dotnet --list-sdks` | `winget install Microsoft.DotNet.SDK.10` |
| Node 22 | `node --version` | |
| Python 3.12 | `python --version` | |
| NVIDIA-drivrutin (aktuell, RTX 5080 är Blackwell) | `nvidia-smi` | Gammal drivrutin eller gammal Ollama kan sakna stöd för kortet. |
| Ollama | `ollama --version` | Installeras på Windows, körs där (använder GPU direkt). |

Fråga användaren innan du installerar systemprogram.

## 1. Hämta repot och konfigurera
```bash
git clone https://github.com/n00rp/Rag-Project.git
cd Rag-Project
cp .env.example .env
```
I `.env` på den här datorn: `EMBEDDING_BACKEND=sentence-transformers`, `LLM_BACKEND=ollama`, `OLLAMA_BASE_URL=http://localhost:11434`, `LLM_MODEL=<modellen från steg 3>`. Hemligheter skrivs aldrig i repot.

Håll WSL vaken innan du startar databasen (se CLAUDE.md, "Miljöfallgropar").

## 2. Kör alla tester först (baslinje)
```bash
docker compose up -d db
```
```bash
cd ai-service && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt && .venv/Scripts/python -m pytest -q
cd ../backend && dotnet test
cd ../frontend && npm install && npm test
```
Förväntat: ai-service 38, backend 21, frontend 13 gröna. Går något rött, åtgärda det innan något annat och rapportera skillnaden mot laptopen.

## 3. Ollama och modell
1. Hämta en kandidatmodell som ryms i 16 GB VRAM (ca 8–14B parametrar, kvantiserad). Jämför minst två på svenska, t.ex. en Qwen-, en Gemma- och en Llama-modell. Kolla vilka som finns aktuellt med `ollama list` / ollama.com innan du väljer; namnen ändras.
2. Testa att den svarar: `ollama run <modell> "Sammanfatta kort vad en kommunstyrelse gör."` och kontrollera att svenskan är rimlig och att GPU används (`nvidia-smi`).
3. Notera tokens/sekund och VRAM-användning, det ska in i README som en del av modelljämförelsen i fas 3.

## 4. Riktiga embeddings (första gången)
```bash
cd ai-service
.venv/Scripts/pip install -r requirements-ml.txt     # torch (CPU) + sentence-transformers, stor nedladdning
```
Första starten laddar ner `intfloat/multilingual-e5-small` (ca 0,5 GB). Verifiera att dimensionen blir 384 (annars stoppar tjänsten med ett tydligt fel). **Viktigt:** vektorerna från den falska embeddern är inkompatibla; ta bort gamla chunks innan du indexerar om (`TRUNCATE rag.chunks;` eller ta bort och ladda upp dokumenten igen).

Starta tjänsterna för hand (enklast för felsökning), i tre terminaler:
```bash
cd ai-service && .venv/Scripts/python -m uvicorn app.main:app --port 8000
cd backend/src/DocAssistant.Api && dotnet run --urls http://localhost:5174
cd frontend && npm run dev
```
Hämta och ladda upp demodokumenten:
```bash
python scripts/demo_docs.py fetch
python scripts/demo_docs.py seed
```
Öppna http://localhost:5173 och ställ riktiga frågor, t.ex.:
- "Vad beslutade kommunstyrelsen om investeringar i europeisk försvarsindustri?" (ämnet förekommer i `KS_protokoll_20250409.pdf`: sida 3 är en jävsanmälan i § 289 som hänvisar till frågan, själva ärendet är § 317. Kontrollera i PDF:en vad som faktiskt är rätt källa innan du bedömer svaret.)
- "Vem anmälde jäv vid sammanträdet 2025-04-09?" (Hampus Magnusson)
- "Vilka beslut fattades om finansverksamheten?"

Kontrollera att källorna pekar på rätt sida och att PDF-visaren öppnar rätt ställe. Det här är första riktiga kvalitetsmätningen; anteckna vad som går bra och dåligt (det blir underlag för evalsetet).

## 5. Hela stacken i Docker (aldrig körd tidigare)
```bash
docker compose up --build
```
Detta bygger ai-service-imagen med torch för första gången och kan avslöja problem. Känd fråga att lösa: ai-service i Docker måste nå Ollama som körs på Windows. `host.docker.internal` pekar mot WSL-VM:en, inte Windows. Alternativ: kör Ollama i WSL, använd Windows-värdens IP från WSL, eller kör ai-service direkt på värden under utveckling. Verifiera vad som funkar och dokumentera det i [dev-setup.md](dev-setup.md) och `.env.example`.

## 6. Kontrollera CI på GitHub
Öppna fliken Actions på https://github.com/n00rp/Rag-Project. CI (ai-service, backend, frontend) har aldrig setts köra. Åtgärda röda jobb. Typiska orsaker: sökväg/versionsskillnader, `-warnaserror` i backend-bygget, TrueType-typsnitt som saknas i Linux-runnern (testerna hoppar då över; `DejaVuSans` brukar finnas).

## 7. Därefter (i den här ordningen)
1. Uppdatera CLAUDE.md "Status" med vad som nu är verifierat, och skriv upp resultaten (modell, tokens/s, första kvalitetsintrycket).
2. **Fas 3 påbörjas** eftersom riktiga embeddings nu finns: skapa `eval/` med ett första evalset (frågor + förväntad sida) mot de sex protokollen, ett skript som mäter recall@k/MRR, och tuna `min_score` så att frågor utan stöd ger "Jag hittar inget stöd i dokumenten". Mät rensningen av sidhuvuden av/på (`STRIP_PAGE_BOILERPLATE`).
3. Därefter fas 2 (inloggning, rate limits, kvoter) enligt [projektplan.md](projektplan.md).

## Arbetsregler (påminnelse)
- Commit och push ofta; `git pull --rebase` när du börjar. Inga `Co-Authored-By`-rader.
- Dokumentera under arbetet (README/ADR/CLAUDE.md), inte efteråt.
- Rapportera ärligt: vad som är körd/verifierat och vad som inte är det.
