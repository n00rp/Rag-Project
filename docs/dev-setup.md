# Utvecklingsmiljö på två datorer

| Dator | Roll |
|---|---|
| Laptop | Kodning, frontend, API, tester. Ingen GPU. |
| Stationär (RTX 5080 16 GB) | Kör Ollama och tung AI-körning, evaluering, ev. demo-host. |

## Arbetsflöde
- `main` ska alltid gå att bygga. Jobba i korta grenar (`feat/...`, `fix/...`), merga ofta.
- **Innan du slutar på en dator:** commit + push (även WIP på en gren).
- **När du börjar på en dator:** `git pull --rebase`.
- Repot är enda källan. Ingen kod förs över med USB eller molndrive.

## Första gången på en ny dator
1. Installera: Git, Docker Desktop, .NET SDK (LTS), Node 22, Python 3.12.
2. `git clone <repo-url>` och `cp .env.example .env`, fyll i lokala värden.
3. Stationär: installera Ollama och hämta modellen som anges i `LLM_MODEL`.

## Laptop → GPU på stationären
Laptopen har ingen GPU. Låt den prata med Ollama på stationären:
1. Installera [Tailscale](https://tailscale.com) (gratis) på båda datorerna och logga in med samma konto.
2. På stationären: låt Ollama lyssna på nätverket (miljövariabel `OLLAMA_HOST=0.0.0.0`) och tillåt port 11434 **bara** för Tailscale-nätet i brandväggen.
3. På laptopen: sätt `OLLAMA_BASE_URL=http://<stationarens-tailscale-namn>:11434` i `.env`.

Exponera aldrig Ollama mot det öppna internet.

## Gitkonfiguration
Kontrollera att commit-identiteten är den du vill visa på GitHub (`git config user.name` / `user.email`). Radslut hanteras av `.gitattributes`.
