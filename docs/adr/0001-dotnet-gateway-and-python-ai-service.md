# ADR 0001: .NET API framför en separat Python-tjänst för AI

- **Status:** Accepterad
- **Datum:** 2026-10-12

## Kontext
Applikationen behöver både "vanlig" produktfunktionalitet (användare, dokumenthantering, jobbkö, API-kontrakt) och AI-arbete (PDF-parsning, chunking, embeddings, retrieval, LLM-anrop, utvärdering). Python har det rikaste ekosystemet för det senare, medan .NET är ett starkt val för det förra och ett mål med projektet är att visa båda färdigheterna.

## Beslut
- **.NET (ASP.NET Core)** äger användare/auth, dokumentmetadata, filer, bakgrundsjobb och det publika API:et som frontend pratar med.
- **Python (FastAPI)** äger allt som rör AI och är bara nåbar internt från .NET.
- Tjänsterna pratar HTTP/JSON. Python-tjänsten anropas alltid med en `owner_id` och filtrerar på den i varje databasfråga, så dataisolering inte hänger på att .NET "kommer ihåg" något.

## Konsekvenser
- (+) Tydlig ansvarsfördelning och AI-delen kan utvecklas, testas och bytas utan att API:et påverkas.
- (+) LLM-leverantören ligger bakom ett eget interface och kan bytas (lokal Ollama nu, annan leverantör senare).
- (−) Ett extra nätverkshopp och två tjänster att drifta. Hanteras med Docker Compose och en typad klient (`AiServiceClient`) som översätter fel (`503`/`ai_unavailable`) till något frontend kan visa.
- (−) Dubbel uppsättning tester. Båda sidor testas mot en riktig Postgres, och .NET testas mot en fejkad AI-klient.
