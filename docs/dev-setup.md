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
1. Installera: Git, Docker Engine i WSL2 (se nedan), .NET SDK (LTS), Node 22, Python 3.12.
2. `git clone <repo-url>` och `cp .env.example .env`, fyll i lokala värden.
3. Stationär: installera Ollama och hämta modellen som anges i `LLM_MODEL`.

## Docker utan Docker Desktop (Docker Engine i WSL2)
Gratis, utan licensvillkor, och `docker compose up` fungerar likadant. Gör detta på båda datorerna.

1. **Kontrollera WSL2** (PowerShell):
   ```powershell
   wsl --status
   wsl -l -v
   ```
   Du ska se en Ubuntu-distribution med VERSION 2. Saknas den: `wsl --install -d Ubuntu` och starta om datorn.
2. **Aktivera systemd** så att Docker startar automatiskt. I Ubuntu-terminalen (`wsl`):
   ```bash
   cat /etc/wsl.conf
   ```
   Om `[boot]` med `systemd=true` saknas, lägg till det:
   ```bash
   printf '[boot]\nsystemd=true\n' | sudo tee -a /etc/wsl.conf
   ```
   Kör sedan `wsl --shutdown` i PowerShell och öppna Ubuntu igen.
3. **Installera Docker Engine** enligt [officiella guiden för Ubuntu](https://docs.docker.com/engine/install/ubuntu/) (apt-repot, inte `docker.io` från Ubuntus egna paket). Installera `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin` och `docker-compose-plugin`.
4. **Kör utan sudo:**
   ```bash
   sudo usermod -aG docker $USER
   ```
   Stäng och öppna Ubuntu-terminalen igen.
5. **Testa:**
   ```bash
   docker run --rm hello-world
   docker compose version
   ```
6. **Portar:** containrar som publicerar en port (t.ex. `5432`) nås från Windows på `localhost:5432`.

**WSL stänger av sig själv när ingen terminal är öppen** och tar då med sig containrarna. Håll den vaken medan du utvecklar (PowerShell):
```powershell
Start-Process -WindowStyle Hidden wsl -ArgumentList '-d','Ubuntu','--','sleep','infinity'
```
Starta sedan databasen: `wsl -d Ubuntu -- bash -c "cd /mnt/c/<sökväg-till-repot> && docker compose up -d db"`. Du kan också bara ha en Ubuntu-terminal öppen.

**Var ska repot ligga?** Det fungerar att köra från `/mnt/c/Programering/ProjectFolder`, men filåtkomst över `/mnt/c` är långsam. Om det blir segt (särskilt `node_modules` och byggen), klona en kopia i WSL:s eget filsystem (`~/projects/Rag-Project`) och arbeta därifrån.

**GPU på stationären (valfritt, senare):** Ollama kan köras direkt i Windows (enklast). Vill du containerisera den behövs NVIDIA Container Toolkit i WSL2 och en aktuell Windows-drivrutin med WSL-stöd.

## Docker (WSL2) → Ollama på Windows (verifierat)
`host.docker.internal` och `localhost` når inte Windows från en container i WSL2 (NAT-läge). Det som fungerar:
1. Windows-värden syns från WSL på gatewayen: `wsl -d Ubuntu -- ip route show default` (här `172.18.208.1`, adaptern `vEthernet (WSL ...)`).
2. Låt Ollama lyssna **bara** på den adressen, inte `0.0.0.0` (PowerShell, starta sedan om Ollama):
   ```powershell
   [Environment]::SetEnvironmentVariable('OLLAMA_HOST','172.18.208.1:11434','User')
   ```
3. `.env`: `OLLAMA_BASE_URL=http://172.18.208.1:11434`.
Adressen kan ändras efter en omstart av WSL/Windows; kontrollera då steg 1 igen. Körs ai-service direkt på Windows (utan Docker) behöver `.env` i stället `http://172.18.208.1:11434` om `OLLAMA_HOST` är satt enligt ovan, annars `http://localhost:11434`.

**Fallgropar på stationären:** en apt-installerad Postgres i Ubuntu (`postgresql@16`) upptar port 5432 och måste stoppas (`sudo systemctl disable --now postgresql`). Python kan få SSL-fel mot goteborg.se; verifieringen ska inte stängas av.

## Laptop → GPU på stationären
Laptopen har ingen GPU. Låt den prata med Ollama på stationären:
1. Installera [Tailscale](https://tailscale.com) (gratis) på båda datorerna och logga in med samma konto.
2. På stationären: låt Ollama lyssna på nätverket (miljövariabel `OLLAMA_HOST=0.0.0.0`) och tillåt port 11434 **bara** för Tailscale-nätet i brandväggen.
3. På laptopen: sätt `OLLAMA_BASE_URL=http://<stationarens-tailscale-namn>:11434` i `.env`.

Exponera aldrig Ollama mot det öppna internet.

## Gitkonfiguration
Kontrollera att commit-identiteten är den du vill visa på GitHub (`git config user.name` / `user.email`). Radslut hanteras av `.gitattributes`.
