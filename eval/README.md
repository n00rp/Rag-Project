# Utvärdering

`evalset.jsonl` har 44 frågor med känd rätt § (sidintervallet räknas ut ur PDF:erna) och 16 frågor som saknar svar i dokumenten (8 uppenbart utanför domänen, 8 som låter som protokollen men saknar stöd; skriptet kontrollerar att orden verkligen saknas). Frågorna är skrivna som ett första utkast från protokollens rubriker och ska granskas och kompletteras för hand (se projektplanen).

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
