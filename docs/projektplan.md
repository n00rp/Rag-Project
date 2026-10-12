# Projektuppdrag: Svensk dokumentassistent med RAG (portfolio-flaggskepp)

## Syfte och framgångskriterier
Detta är **det enda stora portfolioprojektet** inför jobbsökandet. Det ska visa att jag kan få AI att fungera i en riktig produkt: integration, utvärdering, säkerhet och drift. Det ska inte vara en tutorial-klon.

**Projektet är lyckat om:**
1. Det är **klart och live**: en publik demo-URL som fungerar utan inloggningsbesvär.
2. Det ser **professionellt ut**: en rekryterare ska tycka det ser ut som en riktig produkt inom 5 sekunder.
3. Det **funkar pålitligt** med seed-data, utan krascher på huvudflödet.
4. Det har **mätbara resultat**: en utvärderingsrapport som visar hur bra RAG-flödet är och vad jag förbättrade.
5. Det går att **förklara i en intervju**: varje arkitekturbeslut är motiverat i en ADR.

## Tre regler som skyddar mot att det blir halvfärdigt
1. **Vertikal skiva först.** Efter fas 1 ska hela flödet (uppladdning → fråga → svar med källa) fungera, även om det är fult och enkelt. Allt därefter är förbättringar av något som redan fungerar.
2. **Skära, aldrig utöka.** Allt i "Utanför scope" är förbjudet tills "Definition of done" är uppfylld. Nya idéer läggs i `docs/ideas.md`, inte i koden.
3. **Alltid deploybart.** `main` ska alltid gå att bygga och köra. Deploya tidigt (fas 1) och fortsätt deploya efter varje fas.

Tidsbudget: **6–8 veckor** deltid. Om en fas drar över tiden, skär i dess "bör ha"-punkter, aldrig i kvalitetsfasen (fas 5).

## Produkten
En webbapp där man ställer frågor till en samling **svenska offentliga dokument** och får svar med exakta källhänvisningar (dokument + sida + markerat utdrag).

**Domän (beslutad):** svenska kommunala dokument från öppen data: beslutsunderlag, protokoll och kommunala planer. De är offentliga, gratis, innehåller få personuppgifter och är tillräckligt röriga för att göra problemet intressant. Välj en eller två kommuner (gärna en jag har lokal koppling till) och ladda ned ca 100–300 dokument som demosamling. Kontrollera licens/villkor och gallra bort dokument med känsliga personuppgifter innan de läggs i repot eller demon. En nischad domän gör projektet minnesvärt och ger en naturlig demo ("Vad beslutade nämnden om skolskjuts 2025?").

**Användarflöden:**
- Besökaren öppnar demon och ser en förladdad dokumentsamling med exempelfrågor att klicka på.
- Besökaren kan skapa konto (eller använda ett demokonto) och ladda upp egna PDF:er, som bara hen själv ser.
- Besökaren ställer en fråga, ser svaret strömma in och kan klicka på källorna för att se PDF-sidan med utdraget markerat.
- Om svaret saknar stöd i dokumenten ska systemet **säga det** i stället för att gissa.

## Teknikstack (beslutad, byt inte under projektets gång)
| Del | Val | Motivering |
|---|---|---|
| Frontend | React + TypeScript + Vite, Tailwind, shadcn/ui | Snabbt att få ett polerat utseende |
| Backend/API | C# / .NET (senaste LTS), Minimal APIs eller Controllers, EF Core | Auth, användare, dokumentmetadata, kö, orkestrering |
| AI-tjänst | Python + FastAPI | Parsning, chunking, embeddings, retrieval, generering, utvärdering |
| Databas | PostgreSQL med **pgvector** | En databas i stället för två, färre rörliga delar |
| Bakgrundsjobb | Hangfire (.NET) eller enkel kö i Postgres | Asynkron bearbetning utan extra infrastruktur |
| Embeddings | Flerspråkig modell som klarar svenska (t.ex. multilingual-e5), körd lokalt | Gratis, ingen datalämning, bra svenska |
| LLM | **Lokal modell via Ollama** (OpenAI-kompatibelt API) bakom ett eget interface | Budget 0; RTX 5080 16 GB räcker för modeller i 8–14B-klassen (kvantiserade) |
| Loggning/observability | Serilog + OpenTelemetry, health checks | Visar produktionstänk |
| Test | xUnit + Testcontainers, pytest, Playwright (1–2 E2E-test) | Riktiga databaser, inte in-memory |
| CI/CD | GitHub Actions: build, test, lint, deploy | Grön badge i README |
| Hosting | Se avsnittet "Budget 0" nedan | Live-demo utan kostnad |

**Varför .NET framför Python?** .NET äger användare, auth, metadata, jobbkö och API-kontrakt. Python äger allt som rör AI. Den gränsen ska förklaras i en ADR.

## Budget 0: LLM och hosting
Mål: ingen löpande kostnad. Beslut tas i denna ordning, och inget kräver betalning.

**LLM-lagret**
- Utveckling och utvärdering körs mot **Ollama på min egen RTX 5080**. Kandidatmodeller (välj via evalet i fas 3, inte på magkänsla): en Qwen-, Gemma- eller Llama-modell på ca 8–14B parametrar, kvantiserad så att den ryms i 16 GB VRAM tillsammans med embeddingmodellen. Svenskan är ofta modellernas svaga punkt, så jämför minst två modeller.
- Modellvalet är ett **experiment i README** (korrekthet på svenska, latens, VRAM).
- All LLM-åtkomst går via ett eget interface (`ILlmClient`/motsvarande i Python), så att en annan leverantör kan pluggas in senare utan att resten ändras.

**Hosting av demon (välj ett alternativ senast i fas 1, byt inte efter det)**
| Alternativ | Hur | Fördel | Nackdel |
|---|---|---|---|
| A. Hybrid (rekommenderas) | Appen (frontend + .NET + Python + Postgres) på en gratis moln-VM, t.ex. Oracle Cloud Always Free; LLM:en nås från hemmadatorn via Cloudflare Tunnel eller Tailscale | Riktig live-URL, riktig GPU, 0 kr | Demon svarar bara när hemmadatorn är på; behöver en reservplan (se nedan) |
| B. Allt hemma | Allt körs lokalt och exponeras med Cloudflare Tunnel | Enklast att sätta upp | Samma beroende av datorn, dessutom säkerhetsansvar för hemnätet |
| C. Gratis LLM-API | Gratisnivåer hos någon leverantör för demon | Alltid uppe | Kvotor och villkor ändras; osäkert över tid |

**Reservplan för när GPU:n är offline:** demon har en **inspelad exempelsession** och förberäknade svar på exempelfrågorna, och UI:t visar tydligt "live-AI är offline just nu" i stället för att krascha. Dessutom en 60–90 sekunders demovideo i README. Så kan en rekryterare alltid se hur det fungerar, även när datorn är avstängd.

**Skydd av demon:** rate limit per IP och användare, litet maxantal tokens, kö med en samtidig generering åt gången (GPU:n är en flaskhals), och ingen tunnel som exponerar mer än LLM-endpointen.

**Räkna på resurserna redan i fas 1:** embeddingmodell + LLM + Postgres måste samsas om 16 GB VRAM och RAM. Embeddings kan köras på CPU om det behövs.

## Utanför scope (förbjudet tills allt annat är klart)
- Fler än en vektordatabas eller flera LLM-leverantörer i produktion.
- Fler filformat än PDF (Word läggs till sist, om tid finns).
- Mikrotjänster utöver .NET + Python, Kubernetes, Kafka, event sourcing.
- Egen modellträning eller fine-tuning.
- Roller, team, delning av dokument, betalning, e-postflöden.
- Agent-funktioner, verktygsanrop, bildanalys.

## Milstolpar

### Fas 1: Vertikal skiva och deploy (vecka 1–2)
Mål: hela flödet fungerar end-to-end och ligger live, även om det är fult.
- Monorepo: `/frontend`, `/backend`, `/ai-service`, `/docs`, `/eval`, `docker-compose.yml`.
- `docker compose up` startar allt (Postgres+pgvector, .NET, Python, frontend) **med migrationer och seed-data automatiskt**.
- Ladda upp PDF → extrahera text per sida → chunka → embedda → spara med metadata (dokument, sida).
- Fråga → hämta top-k chunks → bygg prompt → svar + källor.
- Enkel frontend: uppladdning, chatt, källista.
- CI som bygger och testar; första deployen live.
- **Checkpoint:** någon utomstående kan öppna URL:en och få ett svar med källa.

### Fas 2: Säkerhet, robusthet och bakgrundsbearbetning (vecka 3)
- JWT-auth, registrering/inloggning, plus ett demokonto.
- **Dataisolering:** varje retrieval filtreras på användare/samling. Ett automatiskt test bevisar att användare A aldrig kan hämta användare B:s chunks.
- Uppladdning är asynkron: status (köad → bearbetas → klar/fel) visas i UI.
- Validering av filer (typ, storlek, antal sidor), rate limiting per användare och dagskvot för LLM-anrop.
- Skydd mot prompt injection i dokumenttext (tydlig avgränsning av kontext, instruktioner om att behandla dokumenttext som data) och en dokumenterad beskrivning av begränsningarna.
- Global felhantering med ProblemDetails, hemligheter via miljövariabler.
- Hantering av skannade PDF:er: minst detektera och visa ett tydligt meddelande (OCR är "bör ha").

### Fas 3: Kvalitet på svaren och utvärdering (vecka 4–5) ← projektets viktigaste del
Det här är det som får projektet att sticka ut.
- **Evalset:** minst 40–60 frågor med förväntat svar och rätt källsida, handskrivna av mig mot demosamlingen. Ligger i `/eval`.
- **Automatiserat utvärderingsskript** som mäter:
  - Retrieval: träffar rätt sida/chunk i top-k (recall@k, MRR).
  - Svarskvalitet: korrekthet och förankring i källorna (LLM-som-domare, stickprovskontrollerad manuellt).
  - Latens per fråga och GPU-/minnesåtgång (kostnad är 0 kr, men resursåtgången redovisas).
- **Experiment redan förberett:** rensning av upprepade sidhuvuden (`STRIP_PAGE_BOILERPLATE` av/på) på Göteborgs-protokollen. Se README, "Vad riktiga protokoll lärde oss".
- **Minst tre experiment** med tabell och slutsats i README, t.ex. chunkstorlek, överlapp, embeddingmodell, hybridsökning (nyckelord + vektor) och omrankning.
- Svaret ska nekas när stödet är för svagt ("Jag hittar inget stöd i dokumenten"), och detta mäts i evalet med frågor som saknar svar.
- Utvärderingen körs i CI på ett litet urval så regressioner syns.

### Fas 4: Produktkänsla och UI (vecka 5–6)
Mål: ser ut som en riktig produkt.
- Konsekvent designsystem (shadcn/ui), mörkt/ljust läge, responsivt ner till mobil.
- Streaming av svar (SSE), skelettladdning, tomma lägen, tydliga felmeddelanden.
- **Källvisare:** klick på en källa öppnar PDF-sidan med utdraget markerat.
- Drag-and-drop-uppladdning med förloppsindikator.
- Exempelfrågor på startsidan, chatthistorik, möjlighet att ge tummen upp/ner på svar (sparas och kan användas i evalet).
- Tillgänglighet: tangentbordsnavigering, kontrast, semantisk HTML (kontrolleras med Lighthouse, mål ≥ 90).
- Branding: namn, logotyp, favicon, en välgjord startsida.

### Fas 5: Polering, dokumentation och lansering (vecka 7–8)
- Stabil demo: seed-data återställs automatiskt, rate limits på plats, health checks gröna, offline-läge testat genom att stänga av GPU-tjänsten.
- Observability: strukturerade loggar med korrelations-id mellan .NET och Python, spårning av latens per fråga.
- Tester: enhetstester för kärnlogik, integrationstester med Testcontainers, 1–2 Playwright-flöden. Siktar på meningsfull täckning av kärnlogiken, inte ett visst procenttal.
- **README** (se nedan), ADR-filer i `docs/adr/`, arkitekturdiagram (Mermaid), skärmbilder och en 60–90 sekunders demo-GIF/video.
- Rensa repot: `.editorconfig`, linters, Dependabot, inga hemligheter i historiken, meningsfulla commits.
- Lägg länken överst i CV, LinkedIn och GitHub-profilens pinned repos.

## README ska innehålla (i den ordningen)
1. Titel, en mening om vad det är, **länk till live-demo** och demo-GIF.
2. Funktioner i punktlista.
3. Arkitekturdiagram och kort förklaring av ansvarsfördelningen .NET/Python.
4. **Utvärderingsresultat:** tabell över experimenten och vad jag valde och varför.
5. Säkerhet och begränsningar (dataisolering, prompt injection, kända svagheter).
6. Köra lokalt: ett kommando (`docker compose up`).
7. Teststrategi och CI-badge.
8. Länkar till ADR:er och "Vad jag skulle göra härnäst".

## Definition of done (projektet är klart när alla är sanna)
- [ ] Live-demo fungerar för en utomstående utan instruktioner, och degraderar snyggt när GPU:n är offline.
- [ ] Ingen löpande kostnad (0 kr/månad).
- [ ] `docker compose up` ger ett fungerande system med seed-data.
- [ ] Dataisolering bevisas av automatiserat test.
- [ ] Evalrapport med minst tre experiment finns i README.
- [ ] Svaret nekas korrekt på frågor utan stöd i dokumenten.
- [ ] Källvisaren markerar rätt utdrag i PDF:en.
- [ ] CI är grön (build, test, lint).
- [ ] README, ADR:er, diagram, skärmbilder och demo-video finns.
- [ ] Lighthouse ≥ 90 på tillgänglighet, UI fungerar på mobil.
- [ ] Inga hemligheter i repot, rate limits på plats.
- [ ] Demosamlingen innehåller bara dokument jag har rätt att publicera.

## Risker och motåtgärder
| Risk | Motåtgärd |
|---|---|
| Scope växer | Förbjudet-listan ovan; idéer till `docs/ideas.md` |
| Fastnar i infrastruktur | Deploya i fas 1; håll antalet tjänster nere (pgvector) |
| Demon är nere när GPU-datorn är av | Reservplan: inspelad session, förberäknade svar, demovideo, tydligt offline-läge i UI |
| Lokal modell är svag på svenska eller för långsam | Jämför modeller i evalet, begränsa kontextlängd, strömma svar, kö med en generering åt gången |
| Missbruk av publik demo | Rate limits, token-tak, inloggning för frågor, tunnel som bara exponerar LLM-endpointen |
| Svenska fungerar dåligt med embeddings | Flerspråkig modell, mät och jämför i fas 3 |
| Projektet ser generiskt ut | Nischad domän, evalrapporten, polerad UI |
| Tappar motivation i mitten | Varje fas slutar med ett synligt, deployat resultat |

## Instruktion till Claude
Hjälp mig att genomföra projektet **fas för fas** enligt planen ovan.
1. Börja med fas 1: ge mig en detaljerad repostruktur, `docker-compose.yml` (inklusive migrationer, seed och Ollama), samt grunduppsättning för .NET-API:et, Python/FastAPI-tjänsten och frontend, så att den vertikala skivan fungerar end-to-end mot en lokal modell. Hjälp mig också att välja hostingalternativ enligt avsnittet "Budget 0".
2. Påminn mig om "Utanför scope" om jag föreslår något som inte ligger i planen.
3. Avsluta varje fas med att kontrollera relevant punkt i "Definition of done" innan vi går vidare.
4. Prioritera kvalitet och slutförande före nya funktioner.
