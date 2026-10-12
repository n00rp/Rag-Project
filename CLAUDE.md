# Projektkontext för Claude

Portfolioprojekt: svensk dokumentassistent med RAG över kommunala öppna dokument. Användaren (junior, AI/ML-utbildning, söker jobb i Sverige) vill att projektet blir **färdigt, visuellt polerat och sticker ut**. Budget 0 kr.

- Full plan, stack, scope och "definition of done": [docs/projektplan.md](docs/projektplan.md). Följ den fas för fas.
- Stacken är beslutad (.NET + Python/FastAPI + Postgres/pgvector + React/TS + Ollama). Byt inte utan att användaren ber om det.
- Respektera "Utanför scope". Nya idéer går till `docs/ideas.md`, inte in i koden.
- Arbetet sker på två datorer: laptop (utan GPU) och stationär (RTX 5080, kör Ollama). Se [docs/dev-setup.md](docs/dev-setup.md).
- Språk: kommunicera på svenska. Kod, commit-meddelanden och identifierare på engelska.
- Lägg **aldrig** till `Co-Authored-By`, "Generated with Claude Code" eller liknande attribution i commits eller PR-beskrivningar. Användaren vill inte ha Claude som contributor på GitHub.
- Hemligheter hör hemma i `.env` (ej incheckad), aldrig i repot.
