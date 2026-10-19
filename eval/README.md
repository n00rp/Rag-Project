# Utvärdering

Två generationer av evalsetet finns i den här mappen:

- **v2 (nu, `evalset.jsonl`)**: 143 räknade besvarbara frågor, 7 frågetyper som vi vet är svaga (följs separat) och 40 frågor utan svar i dokumenten, uppdelade i **dev** (att tuna mot) och **test** (att titta på när ett beslut ska fattas). Byggs av `build_evalset.py`, som kontrollerar att varje förväntat ärende (§) finns, att varje påstått faktum står i källtexten och att orden i nej-frågorna verkligen saknas i dokumenten.
- **v1 (`evalset_v1.jsonl`)**: det första utkastet med 51 + 16 frågor. Experimenten längre ned (kapitel "Experiment 1–4") är gjorda på v1 och ska läsas som riktning, inte som siffror att jämföra med v2.

**Ingen fråga är granskad av en människa än** (`reviewed: false`). Det är den viktigaste begränsningen: frågorna är skrivna av mig utifrån protokollens rubriker och struktur, vilket gör sökningen lättare än den blir för riktiga användare. Granskningen sker med `make_review.py` → fyll i `review/evalset-review.md` → `apply_review.py` → `build_evalset.py` (se "Granska och komplettera" nedan).

## Så körs det
```bash
cd ai-service      # alla kommandon kör med ai-service/.venv: .venv/Scripts/python <skript>
python ../eval/run_all.py                        # retrieval + svar med gemma3:12b, domare qwen3:14b + llama3.1:8b
python ../eval/run_all.py --skip-answers                # bara retrieval (ca en minut)
python ../eval/retrieval.py --label x --doc-header      # ett retrieval-experiment med egna inställningar
python ../eval/summarize_answers.py ../eval/results/baseline-v2-answers.json   # sammanfatta en sparad körning
```
- Alla huvudsiffror visas med **95 % bootstrap-intervall**. Med 56–87 frågor per del är en skillnad på 0,02 oftast brus.
- **Tröskeln för "inget stöd"** väljs på dev och används oförändrad på test.
- **Domare:** LLM-domare bedömer korrekthet och förankring. En modell dömer aldrig sig själv. "Korrekt" kräver att **alla** domare håller med (strikt); spannet uppåt (minst en domare) redovisas också. `calibrate.py` jämför domarna med en människas bedömning av ett urval (`--review-sample N` skriver `review/answer-samples.md`).
- Frågor utan facit (bara rätt källa) räknas som korrekta om svaret citerar en källa på rätt sida.

## Baslinje (evalset v2, 2026-10-19)
Konfiguration: sidhuvud rensas, dokumentrubrik i varje chunk, 900/150 tecken, `min_score` 0,83, e5-small, `top_k` 5, modell gemma3:12b. Rådata i `results/baseline-v2-*.json`.

**Sökning** (rätt sida bland träffarna; intervall = 95 %):

| Del | Frågor | R@1 | R@3 | MRR |
|---|---|---|---|---|
| dev, alla | 87 | 0,84 [0,76–0,91] | 0,86 [0,78–0,93] | 0,855 |
| dev, utan identifierare | 73 | 0,97 [0,93–1,00] | 0,99 [0,96–1,00] | 0,979 |
| dev, bara identifierare | 14 | 0,14 [0,00–0,36] | 0,21 [0,00–0,43] | 0,208 |
| test, alla | 56 | 0,71 [0,59–0,82] | 0,79 [0,68–0,88] | 0,754 |
| test, utan identifierare | 42 | 0,93 [0,83–1,00] | 1,00 [1,00–1,00] | 0,964 |
| test, bara identifierare | 14 | 0,07 [0,00–0,21] | 0,14 [0,00–0,36] | 0,121 |

**Svar** (gemma3:12b; domare qwen3:14b + llama3.1:8b, domarna överens i 90–94 % av fallen):

| Del | Korrekt (strikt) | Minst en domare | Felaktigt nekade | Citat rätt | Nekar obesvarbara |
|---|---|---|---|---|---|
| dev, alla | 0,71 [0,62–0,80] | 0,75 | 0,22 | 0,74 | 1,00 (22 av 22) |
| dev, utan identifierare | 0,79 [0,70–0,88] | 0,84 | 0,12 | 0,82 | 1,00 |
| test, alla | 0,66 [0,54–0,79] | 0,71 | 0,21 | 0,73 | 1,00 (18 av 18) |
| test, utan identifierare | 0,83 [0,71–0,93] | 0,90 | 0,02 | 0,93 | 1,00 |

Svarstid: median 1,1 s, 90:e percentilen 2,7 s.

**Per frågetyp** (korrekta svar, andel):

| Typ | Antal | Korrekt | Kommentar |
|---|---|---|---|
| beslut | 29 | 86 % | |
| ämne | 23 | 91 % | |
| belopp | 10 | 90 % | |
| flera dokument | 9 | 89 % | svarar ofta från ett av dokumenten |
| person | 25 | 80 % | några felaktiga nekanden ("inget stöd") trots att svaret finns |
| datum | 7 | 71 % | |
| detalj (röster, datum i ärendet) | 7 | 71 % | |
| **identifierare** (ärendenummer, § + datum) | 28 | **21 %** | sökningen hittar inte ärendet: 75 % blir nekade |
| **falsk premiss** ("Varför bifölls…" när det avslogs) | 4 | **0 %** | systemet rättar inte frågan, och nekar eller accepterar antagandet |
| saknad totalsumma | 1 | 0 % | nekas med "inget stöd" |

### Vad baslinjen visar
1. **Vanliga frågor fungerar bra, men inte lika bra som v1 antydde.** Utan identifierare är sökningen i princip perfekt (MRR 0,96–0,98), men *svaren* är korrekta i ca 80 % (spann 79–90 % beroende på domare). Det som skiljer är bland annat felaktiga nekanden, svar som blandar ihop två protokoll (q02: jäv i både november 2024 och april 2025) och svar med överflödig eller felaktig tilläggsinformation.
2. **Ärendenummer och paragrafer är det största enskilda hålet.** 28 av 143 frågor (20 %), korrekta svar 21 %. Det är en retrieval-brist (embeddings tolkar `SLK-2025-00392` dåligt), vilket experiment 4 (hybridsökning) pekade på med bara 6 frågor; nu finns 28 att mäta på.
3. **Falska antaganden accepteras eller nekas, men rättas inte.** Det är precis fallet som ett strukturerat svar (`fullt/delvis/inget stöd`, plan B6) ska lösa.
4. **Alla 40 frågor utan svar nekas** (0 av 40 felaktiga svar), men tröskeln är ställd på samma frågor, så siffran är optimistisk för frågor som liknar protokollens innehåll mer än mina.
5. **Domarna är inte kalibrerade mot en människa.** De är oense i 6–10 % av fallen och gör synliga misstag åt båda hållen (qwen underkände "Nej, hemställan avslås" som svar på en ja/nej-fråga med facit "Nej, hemställan avslås"; llama underkände ett svar med rätt datum). Därför redovisas både strikt och lätt gräns. Kalibreringen görs med `calibrate.py` när ett urval är bedömt (se nedan).

## Förbättring 1 (etapp 3): ärendenummer, datum och okända nummer
Baslinjen visade att ärendenummer och paragrafer var det största hålet. Tre ändringar i tjänsten (`app/rag.py`, `app/db.py`), alla med tester:

1. **Hybridsökning bara för frågor med ärendenummer eller `§ N`:** vektorsökning + Postgres fulltextsökning (svenska, endast ord som finns i högst 1 % av chunkarna), ihopslagna med Reciprocal Rank Fusion (textvikt 2). Övriga frågor går som förut, så de påverkas inte (experiment 4 visade att hybrid för alla frågor kostar träffsäkerhet).
2. **Datumfilter:** står `2025-04-09` i frågan söker vi först bara i chunks som har datumet (det står i dokumentrubriken); finns det inget faller sökningen tillbaka på allt.
3. **Okänt nummer nekas direkt:** nämner frågan ett ärendenummer eller en paragraf som inte finns i något av ägarens dokument finns inget stöd, hur lik frågan än är ett protokoll (påhittade nummer fick likhet 0,82–0,89). En träff via nyckelord räknas dessutom som bevis i sig och nekas inte på låg likhet.

**Sökning** (retrieval, rätt sida bland träffarna; samma evalset v2, dev/test):

| Konfiguration | MRR dev, alla | MRR test, alla | Identifierare MRR dev / test |
|---|---|---|---|
| Ingen av ändringarna (vektor) | 0,855 | 0,754 | 0,21 / 0,12 |
| Bara datumfilter | 0,861 | 0,765 | – |
| Bara hybrid för identifierare | 0,968 | 0,904 | – |
| **Hybrid + datumfilter (nu standard)** | **0,977** [0,94–1,00] | **0,959** [0,91–0,99] | **0,96 / 0,91** |

Övriga frågetyper är oförändrade (MRR 0,98 dev / 0,98 test). Varianter av hybriden (ordfilter 1/2/5 % och textvikt 0,25–2) är mätta i `results/e3/`; strängt ordfilter (1 %) gav bäst resultat på identifierare men sämre på övriga frågor, vilket är anledningen till att den bara används när frågan har ett nummer. Beslutsregeln (minst +0,02 på dev, ingen försämring på test) är uppfylld.

**Svar** (hela kedjan, gemma3:12b, domare qwen3:14b + llama3.1:8b; strikt = båda domarna godkänner):

| | Baslinje dev | Nu dev | Baslinje test | Nu test |
|---|---|---|---|---|
| Korrekt, alla frågor | 0,71 | **0,76** (spann 0,76–0,87) | 0,66 | **0,84** (0,84–0,93) |
| Identifierarfrågor korrekta | 21 % | **68 %** | | |
| Identifierarfrågor nekade | 75 % | 0 % | | |
| Frågor utan svar som nekas | 40 av 40 | **44 av 44** (inkl. 4 med påhittade nummer) | | |
| Domarna överens (dev) | 94 % | 83 % | | |

Falska antaganden ("Varför bifölls…") rättas fortfarande inte (0 av 4); det hör till plan B6. **Domarnas överensstämmelse sjönk till 83 %** (strikt och lätt gräns skiljer 11 procentenheter på dev), så den strikta siffran är en undre gräns och en kalibrering mot en människa (`calibrate.py`) är angelägen.

## Granska och komplettera frågorna
```bash
python ../eval/make_review.py          # skapar review/evalset-review.md (frågor, facit, rätt källa i klartext)
# ... fyll i filen: ett x per fråga (stämmer / ändra / ta bort), lägg egna frågor sist ...
python ../eval/apply_review.py         # sparar besluten i review/decisions.json
python ../eval/build_evalset.py        # bygger om evalset.jsonl med besluten (reviewed, borttagna, ändrade, egna frågor)
```
`make_review.py` skriver inte över en fil som redan har markeringar (använd `--force`). Egna frågor skrivs `fråga | facit | KS0409 § 317`; utan dokument och § kan de inte räknas i sökmåtten förrän ärendet har angetts.

För att kalibrera domarna: kör `answers.py --review-sample 12`, bedöm svaren i `review/answer-samples.md` (rätt/fel) och kör `calibrate.py`.

---

# Äldre experiment (evalset v1, utkast med 51 + 16 frågor)

`evalset_v1.jsonl` har 44 frågor med känd rätt § (sidintervallet räknas ut ur PDF:erna) och 16 frågor som saknar svar i dokumenten (8 uppenbart utanför domänen, 8 som låter som protokollen men saknar stöd; skriptet kontrollerar att orden verkligen saknas). Frågorna är skrivna som ett första utkast från protokollens rubriker. Resultaten nedan är gjorda med `retrieval.py`/`answers.py` i deras tidigare form (utan dev/test-delning och utan intervall).

## Retrieval
```bash
cd ai-service
.venv/Scripts/python ../eval/retrieval.py --label baseline -v --json ../eval/results/baseline.json
.venv/Scripts/python ../eval/retrieval.py --label strip+header --doc-header
```
Varje konfiguration indexeras under ett engångs-`owner_id` som tas bort efteråt. Träff = någon av de översta k chunkarna ligger på rätt sida i rätt dokument. Kolumnen "tröskel" visar den bästa poängtröskeln för "inget stöd": andel besvarbara frågor som behålls / andel obesvarbara som nekas.

| Konfiguration | Rensa sidhuvud | Dokumentrubrik | Storlek/överlapp | R@1 | R@3 | R@5 | MRR | Top-1-poäng (besvarbar / obesvarbar) | Tröskel: behålls / nekas |
|---|---|---|---|---|---|---|---|---|---|
| baseline | ja | nej | 900/150 | 0.86 | 0.93 | 0.93 | 0.894 | 0.883 / 0.819 | 98% / 100% |
| no-strip | nej | nej | 900/150 | 0.91 | 1.00 | 1.00 | 0.951 | 0.878 / 0.817 | 98% / 100% |
| strip+header | ja | ja | 900/150 | 0.95 | 1.00 | 1.00 | 0.973 | 0.879 / 0.814 | 98% / 100% |
| nostrip+header | nej | ja | 900/150 | 0.98 | 1.00 | 1.00 | 0.989 | 0.875 / 0.813 | 93% / 100% |
| size300 | ja | nej | 300/50 | 0.82 | 0.93 | 0.93 | 0.875 | 0.887 / 0.815 | 100% / 100% |
| size500 | ja | nej | 500/85 | 0.86 | 0.95 | 0.95 | 0.902 | 0.885 / 0.817 | 98% / 100% |
| size1500 | ja | nej | 1500/250 | 0.86 | 0.93 | 0.93 | 0.894 | 0.879 / 0.817 | 100% / 94% |
| overlap0 | ja | nej | 900/0 | 0.86 | 0.93 | 0.93 | 0.894 | 0.883 / 0.817 | 100% / 100% |
| overlap300 | ja | nej | 900/300 | 0.82 | 0.93 | 0.93 | 0.871 | 0.883 / 0.820 | 100% / 100% |

## Slutsatser (n = 44, en skillnad på en fråga är 2,3 procentenheter, tolka försiktigt)
- **Sidhuvudsrensningen sänker träffsäkerheten** (MRR 0,894 mot 0,951 utan rensning). Skillnaden är de tre frågorna som anger sammanträdesdatum: datumet och organet står bara i sidhuvudet.
- **En kort dokumentrubrik** (de tre första raderna på dokumentets första sida, t.ex. protokollnummer, datum och organ) i början av varje chunk, tillsammans med rensningen, ger MRR 0,973 och recall@3 = 1,00. Utan rensning men med rubrik blir MRR 0,989 men nej-svaret sämre (93 % behålls), så rensning + rubrik är det bättre kompromissvalet.
- **Chunkstorlek och överlapp** gör nästan ingen skillnad mellan 500 och 1500 tecken; 300 tecken är något sämre, och överlapp 300 är något sämre än 0-150.
- **Nej-svar:** poängen skiljer perfekt (AUC 1,00) men marginalen är smal: snitt ca 0,88 för besvarbara mot ca 0,82 för obesvarbara, och bästa tröskel ligger mellan 0,84 och 0,86 i alla konfigurationer. e5-poängen är hoptryckta, så en tröskel behöver sättas försiktigt och verifieras mot fler frågor.
- Retrievalen är inte hela bilden: den första riktiga frågan (försvarsindustri, § 317) hittades av retrievalen men fick ändå svaret "inget stöd" av LLM:en. Svarssteget måste mätas separat.

## Svar (hela RAG-kedjan, `answers.py`)
```bash
cd ai-service
.venv/Scripts/python ../eval/answers.py --models qwen3:14b gemma3:12b llama3.1:8b --judge qwen3:14b
```
Samma 44 + 16 frågor, top-5 chunks, `temperature 0,1`, rensning + dokumentrubrik, `min_score` av. "Korrekt" = inte nekad och godkänd av domaren mot facit (frågor utan facit: citerad sida är rätt). "Citat" = svaret citerar en källa på rätt sida. VRAM är det totala minnet på kortet när bara den modellen var laddad.

| Modell | Korrekt (besvarbara) | Felaktigt nekade | Citat rätt | Nekar obesvarbara | Latens median / p90 (s) | VRAM (GB) |
|---|---|---|---|---|---|---|
| qwen3:14b | 84% | 9% | 91% | 100% | 4.8 / 7.0 | 10.9 |
| gemma3:12b | 93% | 5% | 95% | 94% | 1.2 / 3.1 | 10.6 |
| llama3.1:8b | 61% | 30% | 57% | 100% | 0.6 / 1.2 | 6.9 |

- **gemma3:12b** är bäst: högst korrekthet, bäst citat och näst snabbast. Dess enda fel bland obesvarbara var en fråga om en kommunal bilpool, där den byggde svaret på ett löst relaterat utdrag.
- **llama3.1:8b** är snabbast och minst, men nekar nästan var tredje besvarbar fråga ("Jag hittar inget stöd") trots att rätt utdrag fanns.
- **qwen3:14b** är sämre än gemma och ca 4x långsammare (orsaken är inte undersökt; Qwen3 har ett tänkande-läge som inte är avstängt i `OllamaLlm`). Den svarade "ja" på frågor om jäv som inte förekom.
- **Domaren** är samma modell som qwen3:14b och gillar sina egna svar; "förankring" blev 100 % för alla tre, vilket är för snällt för att vara en slutsats. Jag har läst igenom de felaktiga och nekade svaren, men inte kontrollerat de godkända för hand.

### Tröskeln `min_score` (gemma3:12b)
Tröskeln avgör bara om vi alls svarar (bästa träffens poäng); alla top-5-träffar används sedan som sammanhang.

| min_score | Korrekt | Felaktigt nekade | Citat rätt | Nekar obesvarbara |
|---|---|---|---|---|
| 0 | 93% | 5% | 95% | 94% |
| 0.83 | 93% | 5% | 95% | 100% |
| 0.84 | 93% | 7% | 93% | 100% |
| 0.85 | 91% | 9% | 91% | 100% |

0,83 behåller korrektheten och nekar alla obesvarbara frågor; 0,84 och 0,85 kostar redan svar. Poängen gäller e5-small med dokumentrubrik och måste ställas om om embeddingmodellen byts.

**Lärdom:** första versionen filtrerade *varje* träff mot tröskeln. Då försvann rätt chunk för frågan om försvarsindustri (§ 317, sida 36 fick 0,8296 mot tröskeln 0,83 och föll bort, så LLM:en såg bara jävsanmälan på sida 3). e5-poängen är hoptryckta (top-10 ligger inom ca 0,03), så en tröskel får aldrig användas för att välja ut sammanhang, bara för att avgöra om svar ska ges. Rättat i `rag.py`, med test.

### Försök: mjukare nekande när ämnet finns men det efterfrågade saknas (förkastat)
Fråga q45 ("Hur stor var den kompletterande budgeten i maj 2025?") nekas, fast § 558 hittas som träff 1 (0,854, över tröskeln). Protokollet anger ingen totalsumma, bara delbelopp, så nekandet är sakligt försvarbart men "inget stöd" är missvisande. Jag testade att komplettera systemprompten med "om utdragen handlar om ämnet men inte innehåller det som efterfrågas, säg det och redovisa vad de i stället säger" (gemma3:12b, `min_score` 0,83, 45 + 16 frågor, rådata i `results/prompt-v1.json` och `prompt-v2.json`).

| Prompt | Korrekt (besvarbara) | Nekar obesvarbara | Citat rätt |
|---|---|---|---|
| nuvarande | 91 % | 100 % | 93 % |
| mjukare nekande | 87 % | 100 % | 91 % |

- **Löste inte q45:** modellen svarade fortfarande "Jag hittar inget stöd för det i dokumenten" och la bara till en förklaring efter meningen ("anger inte storleken på ... budgeten"), utan delbeloppen. Eftersom svaret innehåller nekandemeningen räknas det som ett nekande och källorna tas bort.
- **Två frågor försämrades** (q39, q40): svaren tappade `[1]`-hänvisningarna och domaren underkände dem. Med 45 frågor är två frågor inom bruset, men det finns ingen förbättring att vinna tillbaka dem med.
- **Beslut:** prompten ändras inte. En riktig åtgärd kräver troligen att nekandet inte avgörs av en sträng i svaret (t.ex. ett separat steg eller strukturerat svar), vilket inte är byggt.

### Experiment 4: hybridsökning (nyckelord + vektor)
```bash
cd ai-service
.venv/Scripts/python ../eval/retrieval.py --doc-header --hybrid --idf --max-df 0.01 --label hybrid-df1-51
```
Vektorsökningen kompletteras med Postgres fulltextsökning (`to_tsvector('swedish', …)`, frågans ord som OR-fråga) och de två rankningarna slås ihop med Reciprocal Rank Fusion (k = 60). `--idf --max-df X` använder bara ord som finns i högst X av chunkarna, så att vanliga ord inte dränker identifierare som ärendenummer. Chunkens poäng för `min_score` är fortfarande cosine.

Evalsetet har utökats till 51 besvarbara frågor: 6 nya **identifierarfrågor** ("Vad gäller ärende SLK-2025-00392?", "Vad behandlades under § 1003?"), där embeddings är svaga och nyckelordssökning borde vinna. De skrevs innan jag körde hybriden, men n = 6 är för litet för säkra slutsatser.

| Konfiguration | MRR alla (51) | R@1 | R@3 | MRR övriga (45) | MRR identifierare (6) | R@1 identifierare | Nej-svar AUC |
|---|---|---|---|---|---|---|---|
| Vektor (nuvarande) | 0.889 | 0.86 | 0.92 | 0.974 | 0.250 | 0.17 | 1.00 |
| Hybrid, alla ord, vikt 1 | 0.717 | 0.67 | 0.71 | 0.806 | 0.052 | 0.00 | 1.00 |
| Hybrid, ord i ≤ 5 % av chunks, vikt 1 | 0.885 | 0.84 | 0.92 | 0.940 | 0.472 | 0.33 | 1.00 |
| Hybrid, ≤ 5 %, textvikt 0,25 | 0.887 | 0.84 | 0.92 | 0.950 | 0.417 | 0.33 | 1.00 |
| Hybrid, ≤ 1 %, vikt 1 | 0.879 | 0.82 | 0.94 | 0.898 | 0.741 | 0.67 | 0.99 |
| Hybrid, ≤ 1 %, textvikt 0,5 | 0.880 | 0.84 | 0.92 | 0.930 | 0.500 | 0.50 | 1.00 |
| Hybrid, ≤ 2 %, textvikt 0,5 | 0.893 | 0.86 | 0.92 | 0.945 | 0.500 | 0.50 | 1.00 |
| Router: ärendenummer/§ i frågan → hybrid ≤ 1 %, annars vektor (simulerad) | 0.947 | 0.92 | 0.98 | 0.974 | 0.741 | 0.67 | - |

- **Ingen konfiguration slår vektorsökningen på de vanliga frågorna.** Utan filter på ordens vanlighet blir hybriden mycket sämre (MRR 0,974 → 0,806 på de 45 övriga), eftersom vanliga ord som "kommunstyrelsens" och "sammanträde" ger brus i textrankningen.
- **På identifierarfrågor hjälper nyckelordssökningen tydligt:** MRR 0,25 → 0,74 och R@1 0,17 → 0,67 med bara ord i högst 1 % av chunkarna. Vektorsökningen hittar ofta inte ett ärendenummer alls (4 av 6 utanför topp 10).
- **Priset:** på övriga frågor sjunker MRR från 0,974 till 0,90–0,95. Totalt över alla 51 är skillnaden liten (0,874–0,893 mot 0,889): ingen hybrid är bättre överlag.
- **Felsökning:** en identifierare som finns i exakt en chunk hamnade först utanför topp 10, eftersom chunks som matchar flera måttligt vanliga ord ("ärende", "gäller") fick högre `ts_rank_cd` än chunken med det sällsynta ärendenumret. Därför fungerar strikt ordfilter bättre än vikter.
- **Risk för överanpassning:** variationerna (filtergräns, vikt) valdes på samma frågor som de mäts på. Skillnader på någon tiondel MRR med n = 6 ska inte tas som säkra.
- **Slutsats och beslut:** hybridsökning införs **inte** i tjänsten. En enkel router (om frågan innehåller ett ärendenummer eller "§ N" → hybrid, annars vektor) ger i simuleringen MRR 0,947 mot 0,889 för ren vektor på de 51 frågorna, men det är en simulering på en handvald delmängd. Den bör bara byggas om användarna faktiskt söker på ärendenummer, och mätas på fler identifierarfrågor först.
