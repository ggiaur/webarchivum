"""Authoritative Fejér vármegyei (Fejér county) place names, used as the
ground truth for locality filtering — "does this candidate page actually have
a Fejér megyei connection" per the task's stated criteria (local people,
institutions, history).

Source: https://www.fejer.hu/telepulesek (official county government page),
fetched 2026-07-31. 108 municipalities. This is real, sourced data — not a
guessed or partial list.
"""

FEJER_MUNICIPALITIES = [
    "Aba", "Adony", "Alap", "Alcsútdoboz", "Alsószentiván", "Bakonycsernye",
    "Bakonykúti", "Balinka", "Baracs", "Baracska", "Beloiannisz", "Besnyő",
    "Bicske", "Bodajk", "Bodmér", "Cece", "Csabdi", "Csákberény", "Csákvár",
    "Csókakő", "Csór", "Csősz", "Daruszentmiklós", "Dég", "Dunaújváros",
    "Előszállás", "Enying", "Ercsi", "Etyek", "Fehérvárcsurgó", "Felcsút",
    "Füle", "Gánt", "Gárdony", "Gyúró", "Hantos", "Igar", "Iszkaszentgyörgy",
    "Isztimér", "Iváncsa", "Jenő", "Kajászó", "Káloz", "Kápolnásnyék",
    "Kincsesbánya", "Kisapostag", "Kisláng", "Kőszárhegy", "Kulcs",
    "Lajoskomárom", "Lepsény", "Lovasberény", "Magyaralmás", "Mány",
    "Martonvásár", "Mátyásdomb", "Mezőfalva", "Mezőkomárom", "Mezőszentgyörgy",
    "Mezőszilas", "Moha", "Mór", "Nadap", "Nádasdladány", "Nagykarácsony",
    "Nagylók", "Nagyveleg", "Nagyvenyim", "Óbarok", "Pákozd", "Pátka",
    "Pázmánd", "Perkáta", "Polgárdi", "Pusztaszabolcs", "Pusztavám",
    "Rácalmás", "Ráckeresztúr", "Sárbogárd", "Sáregres", "Sárkeresztes",
    "Sárkeresztúr", "Sárkeszi", "Sárosd", "Sárszentágota", "Sárszentmihály",
    "Seregélyes", "Soponya", "Söréd", "Sukoró", "Szabadbattyán",
    "Szabadegyháza", "Szabadhídvég", "Szár", "Székesfehérvár", "Tabajd",
    "Tác", "Tordas", "Újbarok", "Úrhida", "Vajta", "Vál", "Velence", "Vereb",
    "Vértesacsa", "Vértesboglár", "Zámoly", "Zichyújfalu",
]

# Common alternate/adjective forms worth matching too ("fejér megyei",
# "vármegyei" spelling variants).
FEJER_COUNTY_TERMS = [
    "Fejér megye", "Fejér vármegye", "Fejér megyei", "Fejér vármegyei",
]

ALL_LOCALITY_TERMS = FEJER_MUNICIPALITIES + FEJER_COUNTY_TERMS
