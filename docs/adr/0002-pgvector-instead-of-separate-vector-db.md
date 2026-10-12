# ADR 0002: pgvector i Postgres i stället för en separat vektordatabas

- **Status:** Accepterad
- **Datum:** 2026-10-12

## Kontext
RAG kräver likhetssökning över embeddings. Vanliga alternativ är en dedikerad vektordatabas (Qdrant, Chroma, Pinecone) eller pgvector-tillägget i Postgres. Projektet har budget 0 kr, ska gå att köra med ett enda `docker compose up`, och mängden data är liten (hundratals dokument, tiotusentals chunks).

## Beslut
Använd **pgvector** i samma Postgres-instans som resten av applikationen. AI-tjänsten äger schemat `rag`; .NET äger `public`. Sökning görs med HNSW-index och cosinuslikhet.

## Konsekvenser
- (+) En databas att drifta, säkerhetskopiera och förklara. Färre rörliga delar i demon.
- (+) Metadatafiltrering (t.ex. `owner_id`, `document_id`) är vanlig SQL i samma fråga som likhetssökningen, vilket gör dataisolering enkel att granska och testa.
- (+) Transaktionell omindexering: ett dokument ersätts atomiskt.
- (−) Färre avancerade vektorfunktioner än specialiserade databaser. Hybridsökning (nyckelord + vektor) måste byggas med Postgres full-text-sök.
- (−) Skalar sämre vid hundratals miljoner vektorer. Det ligger långt utanför projektets behov och byte är isolerat till `ai-service/app/db.py`.
