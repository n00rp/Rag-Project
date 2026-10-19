"""Builds eval/evalset.jsonl (v2) from three sources, so every question has a documented origin:

  * evalset_v1.jsonl: the first draft (51 + 16 questions), kept as it was;
  * hand-written questions below (paraphrases, amounts, persons, dates, cross-document, false premise,
    and question types the system is known to handle badly);
  * generated questions whose answer follows from the structure of the protocols (case numbers, "who
    replaced whom", sections by date).

Every expected section is checked to exist, every stated fact is checked to occur in the section text, and
every "absent" word of a question without an answer is checked not to occur anywhere in the corpus. A
question that fails a check stops the build, so the set cannot drift from the documents.

Nothing here has been reviewed by a person yet (reviewed: false). Run:

    ai-service/.venv/Scripts/python eval/build_evalset.py
"""

import hashlib
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from sections import load_sections  # noqa: E402

FILES = {
    "KF24": "KF_protokoll_20240321.pdf",
    "KF25": "KF_protokoll_20251127.pdf",
    "KS2411": "KS_protokoll_20241127.pdf",
    "KS0409": "KS_protokoll_20250409.pdf",
    "KS0611": "KS_protokoll_20250611.pdf",
    "KS1126": "KS_protokoll_20251126.pdf",
}
BODY = {"KF": "kommunfullmäktiges", "KS": "kommunstyrelsens"}

# (type, question, [(file, §), ...], reference answer or None, facts that must occur in the section text)
HAND: list[tuple] = [
    # --- decisions, paraphrased: the question does not repeat the title of the item
    ("beslut", "Vad ansåg kommunstyrelsen om motionen om att införa lagen om valfrihet i vård- och omsorgsboenden?",
     [("KS2411", 995)], "Motionen avslås.", ["väckta motionen avslås"]),
    ("beslut", "Hur gick det med SD-motionen om att Göteborgs måltidspolicy ska likna Uddevallas?",
     [("KS0409", 323)], "Motionen avslås.", ["väckta motionen avslås"]),
    ("beslut", "Vilket beslut föreslog kommunstyrelsen om motionen om trafiklösning från Wannholt och Höstmad?",
     [("KS0409", 325)], "Motionen avslås.", ["väckta motionen avslås"]),
    ("beslut", "Vad blev utfallet för motionen om nattågslinjer från Darvik och Bönfors?",
     [("KS0409", 322)], "Motionen anses besvarad.", ["anses besvarad"]),
    ("beslut", "Vad beslutades om motionen om att öppna friidrottsanläggningar för allmänheten?",
     [("KS0409", 308)], "Motionen anses besvarad.", ["anses besvarad"]),
    ("beslut", "Beviljades hemställan från Intraservice om att utreda personuppgiftsansvaret kring Navet?",
     [("KF24", 115)], "Nej, hemställan avslås.", ["avslås"]),
    ("beslut", "Godkändes inhyrningsbeslutet för förskolan på Grönebackens gata?",
     [("KS0409", 303)], "Ja, inhyrningsbeslutet godkänns.", ["godkänns"]),
    ("beslut", "Godkändes delårsrapporten för Tolkförmedling Väst 2024?",
     [("KS2411", 993)], "Ja, den godkänns.", ["godkänns"]),
    ("beslut", "Vad beslutades om Göteborg Energis önskan att investera i sol- och vindkraft utanför kommunen?",
     [("KS2411", 1001)], "Hemställan tillstyrks med tillägget att investeringarna ska kunna visa god affärsnytta för bolaget.",
     ["god affärsnytta"]),
    ("beslut", "Vilken strategi ställde sig Göteborgs Stad bakom när det gäller god och nära vård?",
     [("KS0409", 295)], "Färdplan – länsgemensam strategi för god och nära vård.", ["länsgemensam strategi"]),
    ("beslut", "Vilken uppgift gavs till Grefab om miljödifferentierade båtplatsavgifter?",
     [("KF25", 506)], "Att ta fram förslag på en enklare form av miljödifferentiering som kan genomföras inom befintligt kundregister.",
     ["befintligt kundregister"]),
    ("beslut", "Vad hände med uppdraget att utreda bilpoolslösningar för stadens bilar?",
     [("KF25", 508)], "Redovisningen antecknas och uppdraget förklaras fullgjort.", ["förklaras fullgjort"]),
    ("beslut", "Vad blev det av uppdraget att utöka Volontär i skolan till alla utbildningsområden, enligt redovisningen i november 2025?",
     [("KF25", 505)], "Redovisningen antecknas och uppdraget förklaras fullgjort.", ["förklaras fullgjort"]),
    ("beslut", "Vilket underlag antogs för kvarteret Gösen i Gamlestaden?",
     [("KF25", 493)], "Detaljplanen för centrum, bostäder med mera inom kvarteret Gösen, reviderad 23 maj 2025, antas.",
     ["kvarteret Gösen", "23 maj 2025"]),
    # --- amounts and numbers
    ("belopp", "Hur stort villkorat kapitaltillskott får Göteborgs Stadshus AB lämna till AB Liseberg Skår 40:17?",
     [("KF24", 108)], "Högst 1 100 mnkr.", ["1 100 mnkr"]),
    ("belopp", "Hur mycket höjdes grundskolenämndens kommunbidragsram i kompletterande budget mars 2024?",
     [("KF24", 109)], "Med 100 mnkr för 2024 och framåt.", ["100 mnkr för 2024"]),
    ("belopp", "Hur mycket fick äldre samt vård- och omsorgsnämnden för digitala hjälpmedel 2024?",
     [("KF24", 109)], "12 mnkr.", ["12 mnkr för 2024 för inköp av digitala hjälpmedel"]),
    ("belopp", "Vilken projektbudget godkändes för program Masthuggskajen?",
     [("KF24", 111)], "2 340 mnkr (2017 års prisnivå).", ["2 340 mnkr"]),
    ("belopp", "Hur stor projektbudget beslutades för Citybuss Norra Älvstranden och pendlingscykelbanan?",
     [("KF24", 112)], "195 mnkr, varav 38 mnkr är riskreserv.", ["195 mnkr", "38 mnkr"]),
    ("belopp", "Hur stort var utdelningskravet från Göteborgs Stadshus AB som föll bort för 2025?",
     [("KF25", 490)], "350 mnkr, förutsatt ett positivt balanskravsresultat.", ["350 mnkr"]),
    ("belopp", "Inom vilket belopp tillstyrktes Higabs utökade investering i Göteborgs konstmuseum?",
     [("KF25", 495)], "Inom 1 050–1 120 mnkr i 2025 års kostnadsläge.", ["1 050-1 120 mnkr"]),
    ("belopp", "Hur mycket av den kompletterande budgeten i maj 2025 gick till grundskolenämnden av de 36 mnkr i schablonmedel?",
     [("KS0611", 558)], "6 mnkr.", ["6 mnkr till grundskolenämnden"]),
    ("belopp", "Hur mycket investeringsmedel överfördes från vatten och avlopp till investeringar i avfall 2025?",
     [("KS0611", 558)], "24 mnkr.", ["24 mnkr från investeringar vatten- och avlopp till investeringar avfall"]),
    ("belopp", "Hur stort belopp av kommunbidraget flyttades från kommunstyrelsen till äldre samt vård- och omsorgsnämnden för offentliga måltider?",
     [("KS0611", 558)], "0,5 mnkr.", ["0,5 mnkr"]),
    # --- dates and times
    ("datum", "När sades samarbetsavtalet om Kvalitetsmässan upp?",
     [("KF24", 113)], "Den 1 maj 2024.", ["1 maj 2024"]),
    ("datum", "När och var justerades kommunfullmäktiges protokoll från mars 2024?",
     [("KF24", 100)], "På Stadshuset den 4 april 2024 klockan 14:00.", ["4 april 2024, klockan 14:00"]),
    ("datum", "Från vilket datum förordnades Beatrice Klein som politisk sekreterare för V?",
     [("KS2411", 1018)], "Från och med den 10 januari 2025.", ["10 januari 2025"]),
    ("datum", "Under vilken tid gäller Mathias Axelssons förordnande som politisk sekreterare?",
     [("KS0409", 331)], "19 maj 2025 till och med 31 december 2026.", ["19 maj 2025", "31 december 2026"]),
    ("datum", "Till och med när förlängdes förordnandet för Jonas Bergstedts som vikarierande politisk sekreterare för D?",
     [("KS2411", 1019)], "Till och med den 31 januari 2025.", ["31 januari 2025"]),
    ("datum", "Vilken dag skrev stadsledningskontoret sitt tjänsteutlåtande om samrådsunderlaget inför rambudget 2026?",
     [("KS0409", 309)], "Den 17 mars 2025.", ["17 mars 2025"]),
    ("datum", "Hur länge gäller planen för stadens omvärlds- och intressebevakning?",
     [("KF25", 502)], "Fyra år i taget.", ["fyra år i taget"]),
    # --- persons and roles
    ("person", "Vem fick fullmakt att föra Göteborgs Stads talan i ärendet om de lokala ordningsföreskrifterna?",
     [("KS0409", 302)], "Förste stadsjuristen Erica Farberger, eller den hon sätter i sitt ställe.", ["Erica Farberger"]),
    ("person", "Vilka ledamöter yrkade bifall till yrkandet om europeisk försvarsindustri?",
     [("KS0409", 317)], "Axel Josefson (M), Jörgen Fogelklou (SD) och tjänstgörande Emmyly Bönfors (C).", ["Axel Josefson (M)", "Emmyly Bönfors (C)"]),
    ("person", "Vem var ordförande vid kommunstyrelsens sammanträde där yrkandet om försvarsindustrin avslogs?",
     [("KS0409", 317)], "Jonas Attenius (S).", ["Jonas Attenius (S)"]),
    ("person", "Vem var det som tjänstgörande ersättare för C i omröstningen om försvarsindustrin?",
     [("KS0409", 317)], "Emmyly Bönfors.", ["Emmyly Bönfors"]),
    ("person", "Vem anmälde jäv i ärendet om Förvaltningshögskolans partnerskap?",
     [("KS2411", 985), ("KS2411", 994)], "Daniel Bernmar (V).", ["Daniel Bernmar (V)"]),
    # --- details inside one item
    ("detalj", "Hur många röstade ja respektive nej i omröstningen om yrkandet om europeisk försvarsindustri?",
     [("KS0409", 317)], "Åtta röstade Ja (för avslag) och fem röstade Nej.", ["röstar Ja (8)", "röstar Nej (5)"]),
    ("detalj", "När bordlades yrkandet om försvarsindustri första gången?",
     [("KS0409", 317)], "Den 26 mars 2025.", ["26 mars 2025"]),
    ("detalj", "Vilka motioner bordlades när klockan hade passerat 21:36 vid kommunfullmäktiges sammanträde i mars 2024?",
     [("KF24", 119)], "Motionerna under paragraferna 124–140.", ["124–140"]),
    ("detalj", "Vilka områden ska högvattenskyddet längs Göta älv skydda?",
     [("KF25", 496)], "Bland annat delar av Lindholmen, Gullbergsstrand, Partihallsområdet och Slakthusområdet/Marieholm.",
     ["Lindholmen", "Gullbergsstrand", "Partihallsområdet"]),
    ("detalj", "Vilken fastighet gäller Tre Stiftelsers hemställan om försäljning?",
     [("KF25", 492)], "Olivedal 6:31 och tomträtten till Göteborg Sävenäs 91:1.", ["Olivedal 6:31"]),
    ("detalj", "Vad är pilotkommunens uppdrag som Göteborgs Stad anmäler intresse för?",
     [("KF25", 497)], "Att under 2026 förebygga och motverka antimuslimsk rasism, i ett uppdrag från Myndigheten för stöd till trossamfund.",
     ["antimuslimsk rasism", "2026"]),
    ("person", "Till vilken ordförande riktades interpellationen om arbetstidsförkortning inom förskolan?",
     [("KF24", 104)], "Förskolenämndens ordförande (interpellationen är från Anneli Rhedin, M).", ["förskolenämndens ordförande"]),
    ("person", "Vem ställde interpellationen om en eventuell nedläggning av Trollängsskolan?",
     [("KF25", 532)], "Axel Darvik (L).", ["Axel Darvik (L)"]),
    ("person", "Till vilken nämnds ordförande ställdes interpellationen om försäljningen av Cirkus Lorensberg?",
     [("KF25", 533)], "Exploateringsnämndens ordförande.", ["exploateringsnämndens ordförande"]),
    ("person", "Vem ställde interpellationen om att minska administrationen inom äldre- och omsorgsverksamheten i mars 2024?",
     [("KF24", 141)], "Elisabet Lann (KD).", ["Elisabet Lann (KD)"]),
    # --- spans several documents: the answer exists in more than one protocol
    ("flera dokument", "Vilka beslut har fattats om Tre Stiftelser?",
     [("KF25", 492), ("KS1126", 903), ("KS2411", 1014)], None, []),
    ("flera dokument", "Hur har frågan om att Göteborg ska delta som pilotkommun mot antimuslimsk rasism behandlats?",
     [("KF25", 497), ("KS1126", 909)], None, []),
    ("flera dokument", "Var behandlades den kompletterande budgeten i oktober 2025?",
     [("KF25", 491), ("KS1126", 910)], None, []),
    ("flera dokument", "Vad har beslutats om att Göteborgs Stad ska ta hem Skatteverkets uppgifter i Navet?",
     [("KF24", 115), ("KF25", 504)], None, []),
    ("flera dokument", "Vad har sagts om Göteborg Energis slutrapport för Fjärrkyla Älvstaden?",
     [("KF25", 511), ("KS0611", 556)], None, []),
    ("flera dokument", "Hur har motionen om ett migrationspolitiskt bokslut behandlats?",
     [("KS0409", 306), ("KF25", 517)], None, []),
    ("flera dokument", "Vad har hänt med motionen om Sankt Sigfrids plan och en öppen markanvisningstävling?",
     [("KS0409", 324), ("KF25", 516)], None, []),
    ("flera dokument", "Hur har förslaget om volontärer i skolan hanterats i kommunfullmäktige?",
     [("KF24", 140), ("KF25", 505)], None, []),
    ("flera dokument", "Vilka beslut gäller Göteborgs konstmuseum?",
     [("KF25", 494), ("KF25", 495)], None, []),
    # --- false premise: the answer must correct the question
    ("falsk premiss", "Varför bifölls yrkandet om att tillåta investeringar i europeisk försvarsindustri?",
     [("KS0409", 317)], "Yrkandet bifölls inte; det avslogs.", ["avslås"]),
    ("falsk premiss", "Varför avslogs motionen om friidrottsanläggningar för allmänheten?",
     [("KS0409", 308)], "Motionen avslogs inte; den ansågs besvarad.", ["anses besvarad"]),
    ("falsk premiss", "Varför bordlades motionen om nattågslinjer vid kommunstyrelsens sammanträde i april 2025?",
     [("KS0409", 322)], "Motionen bordlades inte; den ansågs besvarad.", ["anses besvarad"]),
    ("falsk premiss", "Varför godkändes den nya beräkningsgrunden för avgifter för offentlig plats utan ändringar?",
     [("KF25", 498)], "Den godkändes med ändringar enligt punkt 1–4 i yrkandet från MP, S och V.", ["punkt 1–4 i yrkande från MP, S och V"]),
]

# Question types the system answers badly today (see eval/README.md). Tracked, not part of the headline numbers.
LIMITS: list[tuple] = [
    ("sammanfattning", "Sammanfatta kommunstyrelsens sammanträde 2025-04-09.", [("KS0409", 317)], None, []),
    ("sammanfattning", "Vilka frågor om motioner behandlades vid kommunstyrelsen i april 2025?", [("KS0409", 305)], None, []),
    ("sammanfattning", "Ge en överblick över besluten om politiska sekreterare.", [("KS0409", 331)], None, []),
    ("jämförelse", "Vad är skillnaden mellan hur motionen om måltidspolicy och motionen om nattågslinjer avgjordes?",
     [("KS0409", 323), ("KS0409", 322)], "Måltidsmotionen avslogs medan nattågsmotionen ansågs besvarad.", ["avslås", "anses besvarad"]),
    ("jämförelse", "Vilka ärenden hade samma utfall som SD:s yrkande om pensionskapital vid kommunstyrelsen 2025-04-09?",
     [("KS0409", 319)], None, []),
]

NEGATIVE_OUT_OF_DOMAIN = [
    ("Vem är Sveriges statsminister?", ["statsminister"]),
    ("Hur lagar man pannkakor?", ["pannkak"]),
    ("Vad är huvudstaden i Australien?", ["Australien", "Canberra"]),
    ("Hur många planeter finns det i solsystemet?", ["planet"]),
    ("Vad kostar en Tesla Model 3?", ["Tesla"]),
    ("Hur fungerar en kärnreaktor?", ["kärnreaktor"]),
    ("Vem skrev boken om Pippi Långstrump?", ["Pippi"]),
    ("Vilken är världens högsta byggnad?", ["högsta byggnad"]),
]
NEGATIVE_LOOKALIKE = [
    ("Vad beslutade kommunstyrelsen om avgiftsfri kollektivtrafik för pensionärer?", ["avgiftsfri kollektivtrafik"]),
    ("Vilket beslut fattades om att bygga en ny konserthall vid Gullbergsvass?", ["konserthall"]),
    ("Vad beslutade fullmäktige om att förbjuda privata fyrverkerier?", ["fyrverker"]),
    ("Vad blev beslutet om att införa tiggeriförbud i Göteborg?", ["tiggeri"]),
    ("Vilket yrkande om att förbjuda böneutrop behandlades av kommunstyrelsen?", ["böneutrop", "bönerop"]),
    ("Vad beslutades om att sälja Slottsskogsvallen?", ["Slottsskogsvallen"]),
    ("Vad beslutades om att införa en kommunal e-sportarena?", ["e-sport"]),
    ("Vad beslutade fullmäktige om rekrytering av en kommunikationschef?", ["kommunikationschef"]),
    ("Vad beslutades om att Göteborg ska vara värd för Eurovision?", ["Eurovision"]),
    ("Vilket beslut togs om en ny arena för Örgryte IS?", ["Örgryte"]),
    ("Vad beslutades om krav på cykelhjälm för barn?", ["cykelhjälm"]),
    ("Vilket yrkande gällde ett förbud mot plastpåsar i butiker?", ["plastpåse"]),
    ("Vad beslutades om att stänga djurparken i Slottsskogen?", ["djurpark"]),
    ("Vilket beslut fattades om att införa fyra dagars skolvecka?", ["fyra dagars skolvecka", "fyradagarsvecka"]),
    ("Vad beslutade kommunstyrelsen om att införa en kommunal tandvårdsförsäkring?", ["tandvårdsförsäkring"]),
    # invented case and section numbers: keyword search must not make these look supported
    ("Vad gäller ärende SLK-2030-00001?", ["SLK-2030-00001"]),
    ("Vad står i ärende SLK-2025-99999?", ["SLK-2025-99999"]),
    ("Vad behandlades under § 9999 i kommunstyrelsens protokoll från 2025-04-09?", ["§ 9999"]),
    ("Vad beslutades i § 8888 vid kommunfullmäktiges sammanträde 2024-03-21?", ["§ 8888"]),
    ("Vad beslutades om att bygga en gondolbana över Göta älv?", ["gondol"]),
]


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    return re.sub(r"\s+", " ", text)


def split_of(qid: str) -> str:
    """Deterministic ~60/40 split into dev (tune on it) and test (leave alone until the end)."""
    return "test" if int(hashlib.sha1(qid.encode()).hexdigest()[:8], 16) % 10 < 4 else "dev"


def main() -> None:
    sections = load_sections(HERE.parent / "data" / "goteborg")
    by_key = {(s.file, s.number): s for s in sections}
    corpus = norm(" ".join(s.text for s in sections)).lower()
    rows: list[dict] = []
    problems: list[str] = []

    for line in (HERE / "evalset_v1.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            r.update(source="utkast-1", reviewed=False)
            rows.append(r)

    def expected(pairs):
        out = []
        for short, num in pairs:
            key = (FILES[short], num)
            if key not in by_key:
                problems.append(f"§ {num} finns inte i {FILES[short]}")
            out.append([FILES[short], num])
        return out

    def add(kind, source, items, scored=True, start=100):
        n = start + sum(1 for r in rows if r["id"].startswith("q") and int(r["id"][1:]) >= start)
        for typ, question, pairs, answer, facts in items:
            exp = expected(pairs)
            text = norm(" ".join(by_key[tuple(e)].text for e in exp if tuple(e) in by_key))
            for fact in facts:
                if norm(fact) not in text:
                    problems.append(f"fakta saknas i källan: '{fact}' ({question[:50]})")
            n += 1
            rows.append(dict(id=f"q{n}", type=typ, question=question, answerable=True, expected=exp, answer=answer,
                             source=source, reviewed=False, scored=scored))

    add("hand", "hand-2", HAND)
    add("limit", "hand-2", LIMITS, scored=False)

    # --- generated: case numbers and "section N in the protocol of <date>"
    rng = random.Random(42)
    candidates = [s for s in sections if s.decision and len(s.title) > 25 and "Förteckning" not in s.title]
    rng.shuffle(candidates)
    gen = []
    for s in candidates[:12]:
        # The same case number can appear in several protocols; every section that mentions it is a correct answer.
        where = [(key_of(o), o.number) for o in sections if s.case_number in o.text]
        gen.append(("identifierare", f"Vad gäller ärende {s.case_number}?", where, s.title[:120], []))
    for s in candidates[12:22]:
        d = re.search(r"(\d{4})(\d{2})(\d{2})", s.file)
        date = f"{d.group(1)}-{d.group(2)}-{d.group(3)}"
        gen.append(("identifierare", f"Vad behandlades under § {s.number} i {BODY[s.file[:2]]} protokoll från {date}?",
                    [(key_of(s), s.number)], s.title[:120], []))
    add("gen", "auto-identifierare", gen)

    # --- generated: who replaced whom
    pattern = re.compile(r"i stället för (.+?)(?: som avsagt sig)? för tiden .*? utses (.+?)\.")
    persons = []
    for s in sections:
        m = pattern.search(s.decision)
        role = re.search(r"Val av ledamot i (.+?) i stället för", s.title)
        if m and role:
            persons.append(("person", f"Vem valdes in som ledamot i {role.group(1)} i stället för {m.group(1)}?",
                            [(key_of(s), s.number)], m.group(2), [m.group(2)]))
    add("gen", "auto-person", persons)

    # --- generated: motions and interpellations, with the outcome taken from the decision line
    already = {tuple(map(tuple, r["expected"])) for r in rows if r.get("expected")}
    outcomes = {"avslås": "Motionen avslås.", "anses besvarad": "Motionen anses besvarad.", "bifalles": "Motionen bifalles."}
    motions = []
    for s in sections:
        if not (s.file.startswith("KS_") and s.title.startswith("Motion av ")):
            continue
        hit = next((k for k in outcomes if k in s.decision), None)
        if hit and ((s.file, s.number),) not in already:
            motions.append(("beslut", f"Vad föreslog kommunstyrelsen att kommunfullmäktige skulle besluta om motionen {s.title[7:]}?",
                            [(key_of(s), s.number)], outcomes[hit], [hit]))
    add("gen", "auto-motion", motions)
    interp = []
    for s in sections:
        m = re.match(r"Interpellation av (.+?) till (.+?) (?:om|angående) (.+)", s.title)
        when = re.search(r"bordläggs till sammanträdet den (\d+ \w+ \d{4})", s.decision)
        if m and when and ((s.file, s.number),) not in already:
            interp.append(("detalj", f"Till vilket sammanträde bordlades interpellationen från {m.group(1)} om {m.group(3)[:90]}?",
                           [(key_of(s), s.number)], f"Till sammanträdet den {when.group(1)}.", [when.group(1)]))
    add("gen", "auto-interpellation", interp)

    # --- generated: counting and listing (tracked only; the answer is derived from the decision lines)
    ks0409 = [s for s in sections if s.file == FILES["KS0409"] and re.search(r"\bavslås\b", s.decision)]
    sd = [s for s in sections if s.file.startswith("KS_") and s.title.startswith("Yrkande från SD") and "avslås" in s.decision]
    add("limit", "auto-aggregering", [
        ("aggregering", "Hur många yrkanden och motioner avslogs vid kommunstyrelsens sammanträde 2025-04-09?",
         [(key_of(s), s.number) for s in ks0409], f"Minst {len(ks0409)} (efter beslutsraderna).", []),
        ("aggregering", "Vilka yrkanden från SD avslogs vid kommunstyrelsens sammanträden?",
         [(key_of(s), s.number) for s in sd], "; ".join(f"{s.title[:90]} (§ {s.number})" for s in sd), []),
    ], scored=False)

    # --- negatives
    n = 100
    for q, absent in NEGATIVE_OUT_OF_DOMAIN + NEGATIVE_LOOKALIKE:
        for term in absent:
            if norm(term).lower() in corpus:
                problems.append(f"'{term}' finns i dokumenten ({q[:50]})")
        n += 1
        typ = "saknas" if (q, absent) in NEGATIVE_OUT_OF_DOMAIN else "saknas-svår"
        rows.append(dict(id=f"n{n}", type=typ, question=q, answerable=False, absent_terms=absent,
                         source="hand-2", reviewed=False, scored=True))

    if problems:
        print("\n".join(problems))
        raise SystemExit("evalset byggdes inte")

    rows = apply_review(rows, by_key)

    for r in rows:
        r.setdefault("scored", True)
        r["split"] = split_of(r["id"])
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "dubbla id:n"
    (HERE / "evalset.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    answerable = [r for r in rows if r["answerable"] and r["scored"]]
    print(f"{len(rows)} frågor: {len(answerable)} besvarbara (räknas), "
          f"{sum(1 for r in rows if r['answerable'] and not r['scored'])} frågetyper vi vet är svaga (följs separat), "
          f"{sum(1 for r in rows if not r['answerable'])} utan svar")
    for part in ("dev", "test"):
        print(part, sum(1 for r in answerable if r["split"] == part), "besvarbara,",
              sum(1 for r in rows if not r["answerable"] and r["split"] == part), "utan svar")


def apply_review(rows: list[dict], by_key: dict) -> list[dict]:
    """Applies review/decisions.json (made by apply_review.py): reviewed flags, removals, edits, own questions."""
    path = HERE / "review" / "decisions.json"
    if not path.exists():
        return rows
    data = json.loads(path.read_text(encoding="utf-8"))
    decisions = data.get("decisions", {})
    out = []
    for r in rows:
        d = decisions.get(r["id"])
        if d and d["verdict"] == "ta bort":
            continue
        if d:
            r["reviewed"] = True
            if d["verdict"] == "ändra":
                r["question"] = d.get("question", r["question"])
                if "answer" in d:
                    r["answer"] = d["answer"]
        out.append(r)
    for i, own in enumerate(data.get("own", []), start=1):
        # "<file short name> § <n>" in the third column gives the expected section; without it the question cannot
        # be scored for retrieval yet and is kept out of the numbers until someone adds it.
        m = re.search(r"(KF24|KF25|KS2411|KS0409|KS0611|KS1126)\s*§\s*(\d+)", own.get("where", ""))
        expected = [[FILES[m.group(1)], int(m.group(2))]] if m and (FILES[m.group(1)], int(m.group(2))) in by_key else []
        out.append(dict(id=f"e{i}", type="egen", question=own["question"], answerable=True, expected=expected,
                        answer=own["answer"] or None, source="egen", reviewed=True, scored=bool(expected)))
    return out


def key_of(section) -> str:
    for short, name in FILES.items():
        if name == section.file:
            return short
    raise KeyError(section.file)


if __name__ == "__main__":
    main()
