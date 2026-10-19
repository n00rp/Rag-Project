# ADR 0004: Sökning – dokumentrubrik, tröskel på bästa träffen och hybrid bara för nummer

- **Status:** Accepterad
- **Datum:** 2026-10-19

## Kontext
Protokollen upprepar ett sidhuvud på varje sida. Att ta bort det är det "uppenbart rätta", men mätningen visade att MRR sjönk (0,951 → 0,894), eftersom sammanträdesdatumet bara står där. Vidare gav embeddings (e5-small) hoptryckta likheter (top-10 inom ca 0,03), och en vektorsökning hittar ärendenummer (`SLK-2025-00392`) och paragrafer (`§ 319`) dåligt: rätt svar i 21 % av identifierarfrågorna. Samma ärendenummer och paragrafnummer finns dessutom i flera protokoll.

## Beslut
1. **Rensa sidhuvuden, men lägg en kort dokumentrubrik** (de tre första raderna på dokumentets första sida) i början av varje chunk (`chunking.add_header`, avgränsad med `HEADER_SEP` så att utdrag visas utan rubriken). MRR 0,894 → 0,973.
2. **`min_score` (0,83) avgör bara om vi alls svarar**, mätt på bästa träffen. Den används aldrig för att välja ut sammanhang: en per-träff-tröskel tappade rätt chunk (§ 317 fick 0,8296 mot 0,83).
3. **Hybridsökning bara när frågan har ett ärendenummer eller `§ N`:** vektorsökning och Postgres fulltext (`to_tsvector('swedish')`, bara ord som finns i högst 1 % av chunkarna, genererad `content_tsv`-kolumn med GIN-index), ihopslagna med Reciprocal Rank Fusion (textvikt 2). Alla andra frågor går som förut, eftersom hybrid för alla frågor kostade träffsäkerhet.
4. **Datumfilter:** ett ISO-datum i frågan begränsar sökningen till chunks med det datumet (det står i rubriken); finns inga faller sökningen tillbaka på alla.
5. **Okänt nummer nekas direkt.** Nämner frågan ett ärendenummer eller en paragraf som inte finns i ägarens dokument finns inget stöd, hur lik frågan än är ett protokoll (påhittade nummer fick likhet 0,82–0,89). En träff via nyckelord räknas som bevis i sig och nekas inte på låg likhet.

## Konsekvenser
- (+) Identifierarfrågor: MRR 0,21 → 0,96 (dev) och 0,12 → 0,91 (test); korrekta svar 21 % → 68 %. Övriga frågor oförändrade (MRR 0,98).
- (+) Frågor utan svar nekas fortfarande alla (44 av 44, varav 4 med påhittade nummer).
- (−) Tröskeln och rubriken är anpassade till e5-small och protokollens första rader. Byte av embeddingmodell kräver att `min_score` mäts om; andra dokumenttyper kan få en slumpmässig rubrik.
- (−) Tröskeln valdes på samma frågeset som den mäts på (dev) och är ännu inte prövad på riktiga användares frågor.
- (−) Detekteringen av identifierare är en regex; ett nummer som skrivs på ett annat sätt går den vanliga vägen.
