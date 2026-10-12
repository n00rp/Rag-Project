# Svensk dokumentassistent (RAG)

Ställ frågor till svenska kommunala dokument och få svar med exakta källhänvisningar.

> **Status:** under uppbyggnad (fas 1). Se [docs/projektplan.md](docs/projektplan.md).

Live-demo, arkitekturdiagram, utvärderingsresultat och köra-lokalt-instruktioner läggs till här när de finns.

## Struktur
| Mapp | Innehåll |
|---|---|
| `frontend/` | React + TypeScript |
| `backend/` | .NET API (auth, metadata, jobbkö) |
| `ai-service/` | Python/FastAPI (parsning, embeddings, retrieval, generering) |
| `eval/` | Evalset och utvärderingsskript |
| `docs/` | Projektplan, ADR:er, utvecklingsguide |
| `data/` | Lokal data (inte i git) |

Arbeta på flera datorer: se [docs/dev-setup.md](docs/dev-setup.md).
