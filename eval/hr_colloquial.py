"""HR questions phrased the way a manager would say them, not the way the texts say them.

Same format as hr_questions.py: (area, question, [regex that must all match the answer], source key, absent terms).
The facts are the same kind (and often the same) as in hr_questions.py, so a difference in the score between the two sets
is a difference in wording, not in what the documents contain. Run with `hr_check.py --questions=hr_colloquial`.
Written by the developer, not yet reviewed by an HR professional.
"""

N = ()

QUESTIONS = [
    # --- AB 25, in everyday words
    ("AB", "Hur länge kan jag låta en ny medarbetare prova innan hen blir fast anställd?", [r"6 (kalender)?månader|sex"], "AB25.pdf", N),
    ("AB", "Min medarbetare säger upp sig, hur lång tid har hen på sig innan hen slutar?", [r"3 månader|tre månader"], "AB25.pdf", N),
    ("AB", "Vi måste dra ner personal. En som är 63 och jobbat hos oss i 15 år, hur lång uppsägningstid ska hen ha?", [r"ett år|12 månader"], "AB25.pdf", N),
    ("AB", "Hur mycket semester har en 44-åring?", [r"\b31\b"], "AB25.pdf", N),
    ("AB", "Vad får personalen extra för att jobba på lördagar och söndagar?", [r"66,10"], "AB25.pdf", N),
    ("AB", "Vilken är den högsta ersättningen för att jobba obekväma tider, till exempel julafton?", [r"126,90"], "AB25.pdf", N),
    ("AB", "Jag vill ge en anställd en varning, får jag det?", [r"varning"], "AB25.pdf", N),
    ("AB", "Får min medarbetare ha ett jobb vid sidan av?", [r"anmäl"], "AB25.pdf", N),
    ("AB", "Hur lång tid i förväg måste jag ge ut schemat?", [r"14 dagar"], "AB25.pdf", N),
    ("AB", "Hur länge får en anställd vara hemma med barn och ändå få lön av oss?", [r"270"], "AB25.pdf", N),
    ("AB", "Hur mycket av lönen får en förälder som är hemma med barnet?", [r"77,6"], "AB25.pdf", N),
    ("AB", "Måste en medarbetare som varit sjuk i över en vecka ha läkarintyg?", [r"7 kalenderdagar|sju"], "AB25.pdf", N),
    ("AB", "Vad får jag betala för en timmes jour?", [r"30 ?%|30 procent"], "AB25.pdf", N),
    ("AB", "Hur mycket övertid kan en anställd ta ut som ledighet och spara?", [r"\b200\b"], "AB25.pdf", N),
    ("AB", "Får man tid eller pengar för övertid, och hur mycket?", [r"1 ?½|1 1⁄2|180 ?%|1,5"], "AB25.pdf", N),
    ("AB", "En anställd som hyr bostad av oss ska sluta. Hur snabbt kan vi säga upp hyresavtalet?", [r"en månad|1 månad"], "AB25.pdf", N),
    ("AB", "Kan jag skicka hem en anställd som misstänks för brott?", [r"avstäng"], "AB25.pdf", N),
    # --- LAS
    ("LAS", "Vad räknas som ett godtagbart skäl att säga upp någon?", [r"arbetsbrist", r"personligen"], "LAS_", N),
    ("LAS", "En medarbetare har stulit från oss, kan jag avskeda hen på en gång?", [r"grovt|åsidosatt"], "LAS_", N),
    ("LAS", "Hur snabbt måste jag agera om jag vill avskeda någon efter att jag fått veta vad som hänt?", [r"två månader"], "LAS_", N),
    ("LAS", "Hur många nyckelpersoner kan jag låta slippa turordningen när vi drar ner?", [r"\btre\b|\b3\b"], "LAS_", N),
    ("LAS", "Jag vill ta tillbaka en person som fick gå på grund av arbetsbrist, har hen förtur?", [r"företrädesrätt"], "LAS_", N),
    ("LAS", "En timanställd har jobbat hos oss i över ett år, blir hen fast anställd?", [r"tillsvidare"], "LAS_", N),
    ("LAS", "Vad händer om jag glömmer säga till att en provanställning inte ska bli fast?", [r"tillsvidare"], "LAS_", N),
    ("LAS", "När får jag anställa någon bara en kort period?", [r"vikariat", r"säsong"], "LAS_", N),
    # --- Semesterlagen
    ("SemL", "Hur länge får man vara ledig i sträck på sommaren?", [r"fyra veckor"], "Semesterlag", N),
    ("SemL", "Kan en anställd spara semesterdagar till nästa år, och hur länge?", [r"fem år"], "Semesterlag", N),
    ("SemL", "Hur mycket semester får den som börjar jobba i oktober?", [r"\bfem\b|\b5\b"], "Semesterlag", N),
    # --- Sjuklönelagen
    ("SjLL", "Hur mycket lön får man de första dagarna man är sjuk?", [r"80 procent|80 %"], "Sjuklonelag", N),
    ("SjLL", "Vad är karensdag och hur mycket dras?", [r"20 procent|20 %"], "Sjuklonelag", N),
    ("SjLL", "Hur många dagar betalar arbetsgivaren sjuklön?", [r"14|fjorton|tretton"], "Sjuklonelag", N),
    ("SjLL", "När måste en sjuk medarbetare visa läkarintyg för att få sjuklön?", [r"sjunde|\b7\b"], "Sjuklonelag", N),
    # --- Föräldraledighet, diskriminering
    ("FörL", "En medarbetare med litet barn vill jobba mindre, hur mycket kortare tid kan hen kräva?", [r"fjärdedel|25 ?%|25 procent"], "Foraldraledighetslag", N),
    ("FörL", "Min medarbetare ska bli pappa och vill vara hemma, hur tidigt ska hen säga till?", [r"två månader|2 månader"], "Foraldraledighetslag", N),
    ("FörL", "Min medarbetare har ett sjukt barn, vad gäller då?", [r"tillfällig föräldrapenning"], "Foraldraledighetslag", N),
    ("FörL", "Hur länge får en förälder vara helt hemma med sitt barn?", [r"18 månader"], "Foraldraledighetslag", N),
    ("DL", "Får jag välja bort någon som är gravid när vi rekryterar?", [r"graviditet|diskriminer"], "Diskrimineringslag", N),
    ("DL", "Vad ska jag göra om någon blivit trakasserad på jobbet?", [r"utreda"], "Diskrimineringslag", N),
    ("DL", "Måste vi gå igenom lönerna varje år?", [r"varje år|årligen"], "Diskrimineringslag", N),
    # --- MBL, ATL, AML, LOA, visselblåsare
    ("MBL", "Måste jag prata med facket innan vi ändrar i verksamheten?", [r"förhandl"], "MBL_", N),
    ("ATL", "Hur mycket vila måste personalen ha mellan två arbetspass?", [r"elva|\b11\b"], "Arbetstidslag", N),
    ("ATL", "Hur mycket sammanhängande ledigt måste man ha varje vecka?", [r"trettiosex|\b36\b"], "Arbetstidslag", N),
    ("ATL", "Hur länge får någon jobba utan paus?", [r"fem timmar"], "Arbetstidslag", N),
    ("ATL", "Hur många extra timmar kan en deltidsanställd be om under ett år?", [r"\b200\b"], "Arbetstidslag", N),
    ("AML", "Vem har ansvaret för att arbetsmiljön är bra?", [r"arbetsgivar"], "Arbetsmiljolag", N),
    ("LOA", "Vem ska få jobbet när vi anställer inom kommunen?", [r"förtjänst", r"skicklighet"], "LOA_", N),
    ("Visselblåsare", "Får en anställd som larmat om missförhållanden straffas av chefen?", [r"repressalier"], "Visselblasarlag", N),
    # --- Saknar svar i dokumenten: ska nekas
    ("Saknas", "Hur gör jag skattedeklarationen för en anställd?", [], "", ("skattedeklaration",)),
    ("Saknas", "Får vi bidrag när vi anställer en ungdom?", [], "", ("nystartsjobb", "ungdomsjobb")),
    ("Saknas", "Får jag kamerabevaka personalrummet?", [], "", ("kamerabevak", "kameraövervak")),
    ("Saknas", "Hur ska jag rekrytera via LinkedIn?", [], "", ("linkedin",)),
    ("Saknas", "Hur många semesterdagar har anställda i Danmark?", [], "", ("danmark",)),
]
