# ADR 0006: Strukturerat svar (avstängt) och hantering av översiktsfrågor

- **Status:** Accepterad (strukturerat svar finns men är avstängt)
- **Datum:** 2026-10-19

## Kontext
Två svaga frågetyper återstod efter att sökningen blivit bra:
- **Delvis stöd och falska antaganden.** Utdragen handlar om ämnet men saknar det som efterfrågas (en totalsumma som inte står i protokollet), eller motsäger frågan ("Varför bifölls…" när det avslogs). Nekandet avgörs idag av en mening i svaret, så svaret blir antingen "inget stöd" eller godtar antagandet.
- **Översiktsfrågor** ("sammanfatta", "hur många yrkanden", "lista alla") kräver en genomgång av många ärenden men får fem utdrag.

## Beslut
- **Strukturerat svar** (`STRUCTURED_ANSWER`): modellen börjar med `STÖD: fullt|delvis|inget`, och nekandet avgörs av raden. Hela kedjan finns (ai-service, .NET, kolumnen `Support`, gränssnittets notis), men **inställningen är avstängd**. Mätt (`eval/README.md`, experiment 7): totalsumman och flera falska antaganden blev rätt, men två svar blev nekanden i stället för svar och korrekthet på test sjönk 0,84 → 0,79 (inom bruset), och beslutsregeln i ADR 0003 ("ingen försämring på test") uppfylldes inte. Latensen på dev fördubblades.
- **Översiktsfrågor** känns igen av ett medvetet snävt mönster (`rag.BROAD`). De får 12 utdrag i stället för 5, modellen instrueras att bara redovisa det den ser och säga att översikten kan vara ofullständig, och gränssnittet visar märket "Översikt av de mest relevanta utdragen, kan vara ofullständig". De sju sådana frågorna i frågesetet räknas inte i siffrorna.

## Konsekvenser
- (+) Översiktssvar är ärligare om sin täckning, utan att påstå mer än de kan.
- (+) Det går att slå på strukturerat svar utan ny kod när det finns en kalibrerad domare eller riktiga bedömningar att avgöra på; då bör `inget` inte kunna ersätta ett svar som sökningen själv är säker på.
- (−) Falska antaganden rättas fortfarande bara ibland (0 av 4 i baslinjen), och totalsummefrågor nekas.
- (−) Översikter, räkningar och listor bygger på ett urval och är inte fullständiga; bättre underlag (sammanfattningar per ärende vid indexering) är inte byggt.
- (−) Mönstret för översiktsfrågor prioriterar precision framför täckning: "Vilka yrkanden från SD avslogs…" känns inte igen.
- (−) Ett oanvänt kodspår (`support`-kedjan) finns kvar i alla lager; det kostar underhåll tills beslutet om att slå på eller ta bort det är fattat.
