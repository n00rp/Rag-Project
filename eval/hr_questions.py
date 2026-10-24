"""HR questions for a public-sector employer, with facts taken from the sources in data/hr and data/ab.

Each entry: (topic, question, [regex that must all match the answer], source key, absent terms)
- `source key` is a start of the file name the fact comes from (checked by `hr_check.py --verify` against its text).
- An entry with an empty regex list is a question the documents cannot answer: the answer must be a refusal, and its
  `absent` terms (words that must not occur in any document) are checked the same way.
Written by the developer from the texts, not yet reviewed by an HR professional (see eval/README.md).
"""

N = ()  # no absent terms

QUESTIONS = [
    # --- AB 25
    ("AB", "Hur lång provanställning får man ha?", [r"6 (kalender)?månader|sex"], "AB25.pdf", N),
    ("AB", "Vad är uppsägningstiden när arbetsgivaren säger upp en tillsvidareanställd som arbetat i över ett år?", [r"6 månader|sex månader"], "AB25.pdf", N),
    ("AB", "Hur lång uppsägningstid har en medarbetare som själv vill sluta?", [r"3 månader|tre månader"], "AB25.pdf", N),
    ("AB", "Hur lång uppsägningstid gäller för en 62-åring med 12 års anställning som sägs upp på grund av arbetsbrist?", [r"ett år|12 månader"], "AB25.pdf", N),
    ("AB", "Hur många semesterdagar får en medarbetare som fyller 45 år i år?", [r"\b31\b"], "AB25.pdf", N),
    ("AB", "Hur många semesterdagar har en 35-åring?", [r"\b25\b"], "AB25.pdf", N),
    ("AB", "Hur många semesterdagar har man från det år man fyller 50?", [r"\b32\b"], "AB25.pdf", N),
    ("AB", "Vilken kompensation får en medarbetare som får sin semester förlagd utanför juni–augusti?", [r"5000|3000"], "AB25.pdf", N),
    ("AB", "Hur många timmar i veckan är ordinarie arbetstid för en heltidsanställd?", [r"40 timmar"], "AB25.pdf", N),
    ("AB", "Hur lång är veckoarbetstiden för den som arbetar både vardag och helg?", [r"38 timmar( och)? 15 minuter|38,25"], "AB25.pdf", N),
    ("AB", "Hur mycket ledighet får man för en timmes enkel övertid?", [r"1 ?½|1 1⁄2|1,5|en och en halv"], "AB25.pdf", N),
    ("AB", "Hur mycket ledighet får man för en timmes kvalificerad övertid?", [r"2 timmar|två timmar"], "AB25.pdf", N),
    ("AB", "Hur många timmar övertidsledighet får man spara?", [r"\b200\b"], "AB25.pdf", N),
    ("AB", "Hur stort är tillägget för obekväm arbetstid på helger (O-tillägg B) per timme?", [r"66,10"], "AB25.pdf", N),
    ("AB", "Hur högt är O-tillägg A per timme?", [r"126,90"], "AB25.pdf", N),
    ("AB", "Hur mycket ersätts jour per timme i procent av timlönen för de första 50 timmarna?", [r"30 ?%|30 procent"], "AB25.pdf", N),
    ("AB", "Vilken disciplinpåföljd kan en arbetsgivare ge enligt AB?", [r"varning"], "AB25.pdf", N),
    ("AB", "Måste en medarbetare anmäla en bisyssla?", [r"anmäl"], "AB25.pdf", N),
    ("AB", "När kan arbetsgivaren förbjuda en bisyssla?", [r"hindrande|konkurrer"], "AB25.pdf", N),
    ("AB", "Hur lång uppsägningstid har ett hyresavtal för en personalbostad?", [r"en månad|1 månad"], "AB25.pdf", N),
    ("AB", "Hur länge och med hur mycket får man föräldrapenningtillägg?", [r"180", r"10 procent|10 %"], "AB25.pdf", N),
    ("AB", "Hur många dagar kan man få föräldralön?", [r"270"], "AB25.pdf", N),
    ("AB", "Hur lång tid i förväg ska föräldraledighet anmälas enligt AB?", [r"3 månader|tre månader"], "AB25.pdf", N),
    ("AB", "Från vilken dag krävs läkarintyg enligt AB?", [r"7 kalenderdagar|sju"], "AB25.pdf", N),
    # --- kommentarer och redogörelse
    ("AB-kommentar", "Vad innebär provanställningen i AB jämfört med 6 § LAS enligt kommentaren?", [r"ersätter"], "AB25-kommentarer", N),
    ("AB-kommentar", "Vad händer med ersättningen om arbetsgivaren ger besked om att provanställningen inte blir tillsvidare för sent?", [r"ersättning"], "AB25-kommentarer", N),
    ("AB-kommentar", "Vad ändrades i § 1 Inledning när AB 25 kom?", [r"lokala kollektivavtal"], "AB25-redogorelsetext", N),
    # --- LAS
    ("LAS", "Vad krävs för att en uppsägning ska vara giltig enligt LAS?", [r"saklig"], "LAS_", N),
    ("LAS", "Vilka är sakliga skäl för uppsägning?", [r"arbetsbrist", r"personligen"], "LAS_", N),
    ("LAS", "Hur många arbetstagare får arbetsgivaren undanta från turordningen?", [r"\btre\b|\b3\b"], "LAS_", N),
    ("LAS", "Hur länge måste någon ha varit anställd för att få företrädesrätt till återanställning?", [r"tolv månader|12 månader"], "LAS_", N),
    ("LAS", "Vilken är den minsta uppsägningstiden enligt LAS?", [r"en månad|1 månad"], "LAS_", N),
    ("LAS", "Hur lång uppsägningstid har en arbetstagare med minst tio års anställning enligt LAS?", [r"sex månader|6 månader"], "LAS_", N),
    ("LAS", "Hur lång provanställning tillåter LAS?", [r"sex månader|6 månader"], "LAS_", N),
    ("LAS", "Vad händer om ingen säger något när provanställningen löper ut?", [r"tillsvidare"], "LAS_", N),
    ("LAS", "Hur långt i förväg ska besked lämnas om att en tidsbegränsad anställning inte förlängs?", [r"en månad|1 månad"], "LAS_", N),
    ("LAS", "I vilka fall får man ha en tidsbegränsad anställning?", [r"vikariat", r"säsong"], "LAS_", N),
    # --- Semesterlagen
    ("SemL", "Hur många semesterdagar har man rätt till enligt semesterlagen?", [r"tjugofem|\b25\b"], "Semesterlag", N),
    ("SemL", "Hur många semesterdagar har den som börjar arbeta efter 31 augusti?", [r"\bfem\b|\b5\b"], "Semesterlag", N),
    ("SemL", "Hur länge får sparade semesterdagar ligga kvar?", [r"fem år"], "Semesterlag", N),
    ("SemL", "Hur många semesterdagar får man spara?", [r"tjugo|\b20\b|överskjutande|mer än"], "Semesterlag", N),
    # --- Sjuklönelagen
    ("SjLL", "Hur stor är sjuklönen?", [r"80 procent|80 %"], "Sjuklonelag", N),
    ("SjLL", "Hur stort är karensavdraget?", [r"20 procent|20 %"], "Sjuklonelag", N),
    ("SjLL", "Hur lång är sjuklöneperioden?", [r"14|fjorton|tretton"], "Sjuklonelag", N),
    ("SjLL", "Från vilken dag kan arbetsgivaren kräva läkarintyg för sjuklön?", [r"sjunde|\b7\b"], "Sjuklonelag", N),
    ("SjLL", "Vad ska en medarbetare lämna till arbetsgivaren för att få sjuklön?", [r"försäkran"], "Sjuklonelag", N),
    ("SjLL", "När ska arbetsgivaren anmäla ett sjukfall till Försäkringskassan?", [r"sju kalenderdagar|7 kalenderdagar|sju dagar"], "Sjuklonelag", N),
    # --- Föräldraledighetslagen
    ("FörL", "Hur länge har en förälder rätt att vara helt ledig för vård av barn?", [r"18 månader"], "Foraldraledighetslag", N),
    ("FörL", "Hur mycket får arbetstiden förkortas för en förälder till ett litet barn?", [r"fjärdedel|25 ?%|25 procent"], "Foraldraledighetslag", N),
    ("FörL", "Hur många perioder får föräldraledigheten delas upp i per år?", [r"\btre\b|\b3\b"], "Foraldraledighetslag", N),
    ("FörL", "Hur lång tid i förväg ska föräldraledighet anmälas enligt lagen?", [r"två månader|2 månader"], "Foraldraledighetslag", N),
    ("FörL", "Får arbetsgivaren missgynna någon på grund av föräldraledighet?", [r"(?i)inte|förbjud|missgynn"], "Foraldraledighetslag", N),
    # --- MBL
    ("MBL", "När måste arbetsgivaren förhandla med facket innan beslut enligt MBL?", [r"viktigare förändring"], "MBL_", N),
    ("MBL", "Vad ska arbetsgivaren löpande informera facket om?", [r"produktionsmässigt|ekonomiskt|personalpolitik"], "MBL_", N),
    ("MBL", "Vad gäller om arbetsgivaren vill anlita någon som inte är anställd, till exempel en konsult?", [r"förhandla"], "MBL_", N),
    # --- Arbetstidslagen
    ("ATL", "Hur många timmar får ordinarie arbetstid vara högst per vecka enligt arbetstidslagen?", [r"40 timmar"], "Arbetstidslag", N),
    ("ATL", "Hur lång dygnsvila ska en arbetstagare ha?", [r"elva|\b11\b"], "Arbetstidslag", N),
    ("ATL", "Hur lång veckovila ska en arbetstagare ha?", [r"trettiosex|\b36\b"], "Arbetstidslag", N),
    ("ATL", "Hur mycket mertid får tas ut per år?", [r"\b200\b"], "Arbetstidslag", N),
    ("ATL", "Hur länge får en medarbetare arbeta i följd utan rast?", [r"fem timmar|\b5 timmar"], "Arbetstidslag", N),
    ("ATL", "Hur mycket jourtid får tas ut under fyra veckor?", [r"48"], "Arbetstidslag", N),
    # --- Arbetsmiljölagen, diskriminering, LOA
    ("AML", "Vad innebär systematiskt arbetsmiljöarbete?", [r"planera", r"kontrollera"], "Arbetsmiljolag", N),
    ("AML", "Vad ska arbetsgivaren göra vid en arbetsskada?", [r"utreda"], "Arbetsmiljolag", N),
    ("DL", "Hur ofta ska arbetsgivaren göra en lönekartläggning?", [r"varje år|årligen"], "Diskrimineringslag", N),
    ("DL", "Vilka diskrimineringsgrunder finns?", [r"etnisk", r"funktionsnedsättning", r"ålder"], "Diskrimineringslag", N),
    ("LOA", "Vad ska avgöra vid en anställning inom offentlig sektor?", [r"förtjänst", r"skicklighet"], "LOA_", N),
    ("LOA", "Vad gäller enligt LOA för bisysslor som kan skada förtroendet?", [r"opartiskhet|anseende"], "LOA_", N),
    # --- Frågor som kombinerar källor
    ("Flera", "Skiljer sig semesterdagarna i AB från semesterlagen?", [r"\b25\b", r"31|32"], "AB25.pdf", N),
    ("Flera", "Vad gäller för uppsägningstid enligt AB jämfört med LAS?", [r"6 månader|sex månader"], "AB25.pdf", N),
    ("Flera", "Hur lång tid före föräldraledighetens början ska den anmälas, enligt AB och enligt lagen?", [r"3 månader|tre månader", r"två månader|2 månader"], "AB25.pdf", N),
    # --- Flera ämnen i en fråga (söks del för del)
    ("Flera ämnen", "Berätta om provanställning, uppsägningstid för en arbetstagare och semesterdagar vid 45 år", [r"6 (kalender)?månader|sex", r"3 månader|tre månader", r"\b31\b"], "AB25.pdf", N),
    ("Flera ämnen", "Vad gäller för sjuklön, karensavdrag och läkarintyg?", [r"80 procent|80 %", r"20 procent|20 %", r"sjunde|\b7\b"], "Sjuklonelag", N),
    ("Flera ämnen", "Hur lång är dygnsvila, veckovila och längsta tid att arbeta utan rast?", [r"elva|\b11\b", r"trettiosex|\b36\b", r"fem timmar"], "Arbetstidslag", N),
    # --- Saknar svar i dokumenten: ska nekas
    ("Saknas", "Vad är lönen för en nyexaminerad lärare?", [], "", ("nyexaminerad",)),
    ("Saknas", "Hur många dagar är man ledig när man gifter sig?", [], "", ("gifter sig", "bröllop")),
    ("Saknas", "Hur hög är lönen för en rörmokare?", [], "", ("rörmokare",)),
    ("Saknas", "Hur beskattas en förmånsbil?", [], "", ("förmånsbil",)),
    ("Saknas", "Vilka regler gäller för arbete från ett hemmakontor?", [], "", ("hemmakontor", "hemarbete")),
    ("Saknas", "Hur hög är minimilönen för en städare?", [], "", ("städare", "minimilön")),
    ("Saknas", "Hur ansöker man om körkortstillstånd?", [], "", ("körkort",)),
]
