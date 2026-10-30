"""Pages par commune (100 communes × 4 langues) et page « Pour les communes ».

Appelé par build.render_all APRÈS l'écriture des tableaux de bord : la feuille
de style et la barre de série sont reprises des pages déjà rendues, pour que
les pages communales restent identiques au reste du site. Les textes sont ici
(configuration par langue), pas dans les dictionnaires des gabarits.
"""
import html as html_mod
import json
import re
import unicodedata

CPATH = {"en": "/municipality/", "fr": "/fr/commune/", "de": "/de/gemeinde/", "lb": "/lb/gemeng/"}
FORPATH = {"en": "/for-municipalities/", "fr": "/fr/pour-les-communes/", "de": "/de/fuer-gemeinden/",
           "lb": "/lb/fir-gemengen/"}
HOME = {"en": "/", "fr": "/fr/", "de": "/de/", "lb": "/lb/"}
SIM = {"en": "/simulator/", "fr": "/fr/simulateur/", "de": "/de/rechner/", "lb": "/lb/rechner/"}
LANGS = ("en", "fr", "de", "lb")
ORDER = ("en", "fr", "de", "lb")
FLAG_LABEL = {"en": "EN", "fr": "FR", "de": "DE", "lb": "LU"}
SMALL_BINS = 4   # classes détaillées de 30 kW ou moins (0-5, 5-10, 10-15, 15-30)


def slug(name):
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def esc(s):
    return html_mod.escape(str(s), quote=True)


# ──────────────── textes ──────────────────────────────────────────────────
def _ord(r, lang):
    if lang == "fr":
        return "1er" if r == 1 else f"{r}e"
    if lang == "en":
        suf = "th" if 10 <= r % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(r % 10, "th")
        return f"{r}{suf}"
    return f"{r}."


S = {
    "fr": {
        "rank": lambda r: f"{_ord(r, 'fr')} sur 100",
        "title": lambda c, n, mw, y: f"Photovoltaïque à {c} : {n} installations, {mw} MW ({y})",
        "desc": lambda c, k, mw, date, n, wpc: (f"{c} (canton de {k}) : {mw} MW de photovoltaïque raccordés au {date}, "
                                                f"{n} installations, {wpc} W par habitant. Tailles des installations, "
                                                f"tranches du Klimabonus Gemengen et comparaison avec les communes voisines."),
        "eyebrow": lambda k: f"Commune · canton de {k}",
        "h1": lambda c: f"Le photovoltaïque à <span class=\"sun\">{c}</span>",
        "stand": lambda c, mw, date, n, wpc, med, gkw, gp, fq: (
            f"<strong>{mw} MW</strong> de photovoltaïque raccordés au {date} sur <strong>{n} installations</strong>, "
            f"soit {wpc} W par habitant (médiane des communes : {med} W). Depuis le relevé {fq} : "
            f"<strong>{gkw} kW</strong> ({gp} %)."),
        "k_pv": "Puissance PV", "k_pv_sub": lambda n: f"{n} installations",
        "k_share": "Part du PV", "k_share_sub": lambda t: f"de la capacité décentralisée ({t} MW toutes filières)",
        "k_wpc": "W par habitant", "k_ipk": "Installations / 1 000 hab.",
        "k_ipk_sub": lambda rk, r: f"{rk} · toitures de 30 kW ou moins : {r} / 1 000",
        "k_g": lambda fq: f"Ajouts depuis {fq}", "k_hist": lambda d: f"Depuis le {d}",
        "k_hist_val": lambda dn: f"{dn} inst.", "k_hist_sub": lambda dmw: f"{dmw} MW · suivi hebdomadaire",
        "k_pop": "Population", "k_pop_sub": "habitants (RNPP)",
        "med": lambda m: f"médiane {m}",
        "sizes_h": "Tailles des installations",
        "sizes_lede": lambda c, sn, sc: (f"À {c}, <strong>{sn} % des installations font 30 kW ou moins</strong> "
                                         f"(surtout des toitures), pour <strong>{sc} % de la puissance</strong>."),
        "k_cnt": "part des installations", "k_cap": "part de la capacité", "inst": "inst.",
        "hist_note": lambda d: f"Entre parenthèses : variation nette depuis le {d}.",
        "kb_h": "Selon les tranches des aides aux communes",
        "kb_cols": ("Tranche", "Installations", "Puissance", "Aide pour une centrale communale"),
        "kb_aid": ("Klimabonus des particuliers", "50 % (plafond 675 €/kWc)", "45 % (505 €/kWc)",
                   "40 % (425 €/kWc)", "au cas par cas"),
        "kb_note": ("Barème 2025 du Klimabonus Gemengen (guide pratique, révisé chaque année) ; une ombrière de "
                    "parking est aidée à 45 % (990 €/kWc). Les données Leneda ne disent pas si une installation "
                    "appartient à la commune ou à un particulier."),
        "cmp_h": "Comparaison", "cmp_canton": lambda k: f"Communes du canton de {k}",
        "cmp_size": "Communes de taille comparable",
        "cmp_cols": ("Commune", "Canton", "PV (MW)", "Install.", "W/hab.", "Inst./1 000 hab.", "Ajouts (kW)"),
        "cmp_lede": lambda fq: f"Classées par W par habitant. « Ajouts » : puissance ajoutée depuis le relevé {fq}.",
        "links_h": "Aller plus loin",
        "l_dash": "Graphique interactif de la commune", "l_sim": "Simulateur : est-ce rentable sur votre toit ?",
        "l_for": "Pour les communes : ce que montre cette page", "l_csv": "Données des 100 communes (CSV)",
        "prev": "Commune précédente", "next": "Commune suivante", "all": "Toutes les communes",
        "foot": lambda date: (
            f"Données : jeu « La production d'énergie électrique au Luxembourg » publié par Leneda sur "
            f"data.public.lu (CC0), relevé du {date} ; population : RNPP (CC0). Chiffres de puissance raccordée "
            f"(kW), pas d'énergie produite. Données dérivées sous licence CC BY 4.0."),
        "privacy": ("Mesure d'audience sans cookie : Cloudflare Web Analytics et des compteurs de clics anonymes "
                    "(aucune adresse IP ni identifiant enregistrés)."),
        "by": "Analyse : Sitraka Forler",
        "crumb_home": "Le photovoltaïque au Luxembourg",
    },
    "en": {
        "rank": lambda r: f"{_ord(r, 'en')} of 100",
        "title": lambda c, n, mw, y: f"Solar PV in {c}: {n} installations, {mw} MW ({y})",
        "desc": lambda c, k, mw, date, n, wpc: (f"{c} (canton of {k}): {mw} MW of solar PV connected as of {date}, "
                                                f"{n} installations, {wpc} W per inhabitant. Installation sizes, "
                                                f"Klimabonus Gemengen bands and comparison with nearby municipalities."),
        "eyebrow": lambda k: f"Municipality · canton of {k}",
        "h1": lambda c: f"Solar PV in <span class=\"sun\">{c}</span>",
        "stand": lambda c, mw, date, n, wpc, med, gkw, gp, fq: (
            f"<strong>{mw} MW</strong> of solar PV connected as of {date} across <strong>{n} installations</strong>, "
            f"or {wpc} W per inhabitant (municipal median: {med} W). Since the {fq} reading: "
            f"<strong>{gkw} kW</strong> ({gp}%)."),
        "k_pv": "PV capacity", "k_pv_sub": lambda n: f"{n} installations",
        "k_share": "PV share", "k_share_sub": lambda t: f"of decentralised capacity ({t} MW all technologies)",
        "k_wpc": "W per inhabitant", "k_ipk": "Installations / 1,000 inh.",
        "k_ipk_sub": lambda rk, r: f"{rk} · rooftops of 30 kW or less: {r} / 1,000",
        "k_g": lambda fq: f"Added since {fq}", "k_hist": lambda d: f"Since {d}",
        "k_hist_val": lambda dn: f"{dn} inst.", "k_hist_sub": lambda dmw: f"{dmw} MW · weekly tracking",
        "k_pop": "Population", "k_pop_sub": "inhabitants (RNPP)",
        "med": lambda m: f"median {m}",
        "sizes_h": "Installation sizes",
        "sizes_lede": lambda c, sn, sc: (f"In {c}, <strong>{sn}% of installations are 30 kW or less</strong> "
                                         f"(mostly rooftops), for <strong>{sc}% of capacity</strong>."),
        "k_cnt": "share of installations", "k_cap": "share of capacity", "inst": "inst.",
        "hist_note": lambda d: f"In brackets: net change since {d}.",
        "kb_h": "By municipal subsidy band",
        "kb_cols": ("Band", "Installations", "Capacity", "Subsidy for a municipal plant"),
        "kb_aid": ("household Klimabonus", "50% (cap €675/kWp)", "45% (€505/kWp)", "40% (€425/kWp)", "case by case"),
        "kb_note": ("2025 Klimabonus Gemengen scale (practical guide, revised every year); a car-park canopy gets "
                    "45% (€990/kWp). The Leneda data do not say whether an installation is municipal or private."),
        "cmp_h": "Comparison", "cmp_canton": lambda k: f"Municipalities in the canton of {k}",
        "cmp_size": "Municipalities of similar size",
        "cmp_cols": ("Municipality", "Canton", "PV (MW)", "Inst.", "W/inh.", "Inst./1,000 inh.", "Added (kW)"),
        "cmp_lede": lambda fq: f"Ranked by W per inhabitant. “Added”: capacity added since the {fq} reading.",
        "links_h": "Go further",
        "l_dash": "Interactive chart for this municipality", "l_sim": "Calculator: is solar worth it on your roof?",
        "l_for": "For municipalities: what this page shows", "l_csv": "Data for all 100 municipalities (CSV)",
        "prev": "Previous municipality", "next": "Next municipality", "all": "All municipalities",
        "foot": lambda date: (
            f"Data: “La production d'énergie électrique au Luxembourg” published by Leneda on data.public.lu (CC0), "
            f"reading of {date}; population: RNPP (CC0). Connected capacity (kW), not energy produced. Derived "
            f"data under CC BY 4.0."),
        "privacy": ("Cookie-free audience measurement: Cloudflare Web Analytics and anonymous click counters "
                    "(no IP address or identifier stored)."),
        "by": "Analysis: Sitraka Forler",
        "crumb_home": "Solar PV in Luxembourg",
    },
    "de": {
        "rank": lambda r: f"Platz {r} von 100",
        "title": lambda c, n, mw, y: f"Photovoltaik in {c}: {n} Anlagen, {mw} MW ({y})",
        "desc": lambda c, k, mw, date, n, wpc: (f"{c} (Kanton {k}): {mw} MW Photovoltaik angeschlossen, Stand {date}, "
                                                f"{n} Anlagen, {wpc} W pro Einwohner. Anlagengrößen, Stufen des "
                                                f"Klimabonus Gemengen und Vergleich mit Nachbargemeinden."),
        "eyebrow": lambda k: f"Gemeinde · Kanton {k}",
        "h1": lambda c: f"Photovoltaik in <span class=\"sun\">{c}</span>",
        "stand": lambda c, mw, date, n, wpc, med, gkw, gp, fq: (
            f"<strong>{mw} MW</strong> Photovoltaik angeschlossen (Stand {date}) auf <strong>{n} Anlagen</strong>, "
            f"also {wpc} W pro Einwohner (Median der Gemeinden: {med} W). Seit der Erhebung {fq}: "
            f"<strong>{gkw} kW</strong> ({gp} %)."),
        "k_pv": "PV-Leistung", "k_pv_sub": lambda n: f"{n} Anlagen",
        "k_share": "PV-Anteil", "k_share_sub": lambda t: f"der dezentralen Leistung ({t} MW alle Technologien)",
        "k_wpc": "W pro Einwohner", "k_ipk": "Anlagen / 1 000 Einw.",
        "k_ipk_sub": lambda rk, r: f"{rk} · Dächer bis 30 kW: {r} / 1 000",
        "k_g": lambda fq: f"Zubau seit {fq}", "k_hist": lambda d: f"Seit dem {d}",
        "k_hist_val": lambda dn: f"{dn} Anl.", "k_hist_sub": lambda dmw: f"{dmw} MW · wöchentlich verfolgt",
        "k_pop": "Bevölkerung", "k_pop_sub": "Einwohner (RNPP)",
        "med": lambda m: f"Median {m}",
        "sizes_h": "Anlagengrößen",
        "sizes_lede": lambda c, sn, sc: (f"In {c} haben <strong>{sn} % der Anlagen 30 kW oder weniger</strong> "
                                         f"(meist Dächer), mit <strong>{sc} % der Leistung</strong>."),
        "k_cnt": "Anteil der Anlagen", "k_cap": "Anteil der Leistung", "inst": "Anl.",
        "hist_note": lambda d: f"In Klammern: Nettoveränderung seit dem {d}.",
        "kb_h": "Nach Stufen der Gemeindeförderung",
        "kb_cols": ("Stufe", "Anlagen", "Leistung", "Förderung für eine Gemeindeanlage"),
        "kb_aid": ("Klimabonus für Privathaushalte", "50 % (max. 675 €/kWp)", "45 % (505 €/kWp)",
                   "40 % (425 €/kWp)", "im Einzelfall"),
        "kb_note": ("Klimabonus Gemengen, Stand 2025 (Praxisleitfaden, jährlich angepasst); eine "
                    "Parkplatzüberdachung wird mit 45 % gefördert (990 €/kWp). Die Leneda-Daten sagen nicht, ob "
                    "eine Anlage der Gemeinde oder Privatleuten gehört."),
        "cmp_h": "Vergleich", "cmp_canton": lambda k: f"Gemeinden im Kanton {k}",
        "cmp_size": "Gemeinden ähnlicher Größe",
        "cmp_cols": ("Gemeinde", "Kanton", "PV (MW)", "Anl.", "W/Einw.", "Anl./1 000 Einw.", "Zubau (kW)"),
        "cmp_lede": lambda fq: f"Sortiert nach W pro Einwohner. „Zubau“: seit der Erhebung {fq} hinzugekommene Leistung.",
        "links_h": "Weiter",
        "l_dash": "Interaktive Grafik der Gemeinde", "l_sim": "Rechner: lohnt sich Solar auf Ihrem Dach?",
        "l_for": "Für Gemeinden: was diese Seite zeigt", "l_csv": "Daten aller 100 Gemeinden (CSV)",
        "prev": "Vorherige Gemeinde", "next": "Nächste Gemeinde", "all": "Alle Gemeinden",
        "foot": lambda date: (
            f"Daten: „La production d'énergie électrique au Luxembourg“, veröffentlicht von Leneda auf "
            f"data.public.lu (CC0), Erhebung vom {date}; Bevölkerung: RNPP (CC0). Angeschlossene Leistung (kW), "
            f"nicht erzeugte Energie. Abgeleitete Daten unter CC BY 4.0."),
        "privacy": ("Reichweitenmessung ohne Cookies: Cloudflare Web Analytics und anonyme Klickzähler "
                    "(keine IP-Adresse, keine Kennung gespeichert)."),
        "by": "Analyse: Sitraka Forler",
        "crumb_home": "Photovoltaik in Luxemburg",
    },
    "lb": {
        "rank": lambda r: f"Plaz {r} vun 100",
        "title": lambda c, n, mw, y: f"Photovoltaik zu {c}: {n} Installatiounen, {mw} MW ({y})",
        "desc": lambda c, k, mw, date, n, wpc: (f"{c} (Kanton {k}): {mw} MW Photovoltaik ugeschloss, Stand {date}, "
                                                f"{n} Installatiounen, {wpc} W pro Awunner. Gréisste vun den "
                                                f"Installatiounen, Tranche vum Klimabonus Gemengen a Verglach mat "
                                                f"den Nopeschgemengen."),
        "eyebrow": lambda k: f"Gemeng · Kanton {k}",
        "h1": lambda c: f"Photovoltaik zu <span class=\"sun\">{c}</span>",
        "stand": lambda c, mw, date, n, wpc, med, gkw, gp, fq: (
            f"<strong>{mw} MW</strong> Photovoltaik ugeschloss (Stand {date}) op <strong>{n} Installatiounen</strong>, "
            f"also {wpc} W pro Awunner (Median vun de Gemengen: {med} W). Zënter dem Relevé {fq}: "
            f"<strong>{gkw} kW</strong> ({gp} %)."),
        "k_pv": "PV-Leeschtung", "k_pv_sub": lambda n: f"{n} Installatiounen",
        "k_share": "PV-Undeel", "k_share_sub": lambda t: f"vun der dezentraler Kapazitéit ({t} MW all Filièren)",
        "k_wpc": "W pro Awunner", "k_ipk": "Installatiounen / 1 000 Aw.",
        "k_ipk_sub": lambda rk, r: f"{rk} · Diech bis 30 kW: {r} / 1 000",
        "k_g": lambda fq: f"Zouwuess zënter {fq}", "k_hist": lambda d: f"Zënter dem {d}",
        "k_hist_val": lambda dn: f"{dn} Inst.", "k_hist_sub": lambda dmw: f"{dmw} MW · all Woch verfollegt",
        "k_pop": "Populatioun", "k_pop_sub": "Awunner (RNPP)",
        "med": lambda m: f"Median {m}",
        "sizes_h": "Gréisste vun den Installatiounen",
        "sizes_lede": lambda c, sn, sc: (f"Zu {c} hunn <strong>{sn} % vun den Installatiounen 30 kW oder manner</strong> "
                                         f"(meeschtens Diech), fir <strong>{sc} % vun der Leeschtung</strong>."),
        "k_cnt": "Undeel vun den Installatiounen", "k_cap": "Undeel vun der Kapazitéit", "inst": "Inst.",
        "hist_note": lambda d: f"An de Klameren: Nettoännerung zënter dem {d}.",
        "kb_h": "No de Tranche vun de Gemengenhëllefen",
        "kb_cols": ("Tranche", "Installatiounen", "Leeschtung", "Hëllef fir eng Gemengenanlag"),
        "kb_aid": ("Klimabonus fir Privatleit", "50 % (Plafong 675 €/kWp)", "45 % (505 €/kWp)",
                   "40 % (425 €/kWp)", "vu Fall zu Fall"),
        "kb_note": ("Bareem 2025 vum Klimabonus Gemengen (praktesche Guide, all Joer iwwerschafft); e "
                    "Parkplazendaach kritt 45 % (990 €/kWp). D'Leneda-Donnéeë soen net, ob eng Installatioun der "
                    "Gemeng oder engem Privatmann gehéiert."),
        "cmp_h": "Verglach", "cmp_canton": lambda k: f"Gemengen am Kanton {k}",
        "cmp_size": "Gemenge vun änlecher Gréisst",
        "cmp_cols": ("Gemeng", "Kanton", "PV (MW)", "Inst.", "W/Aw.", "Inst./1 000 Aw.", "Zouwuess (kW)"),
        "cmp_lede": lambda fq: f"Sortéiert no W pro Awunner. „Zouwuess“: Leeschtung derbäi zënter dem Relevé {fq}.",
        "links_h": "Weider",
        "l_dash": "Interaktiv Grafik vun der Gemeng", "l_sim": "Rechner: rentéiert Solar op Ärem Daach?",
        "l_for": "Fir Gemengen: wat dës Säit weist", "l_csv": "Donnéeë vun allen 100 Gemengen (CSV)",
        "prev": "Gemeng virdrun", "next": "Nächst Gemeng", "all": "All Gemengen",
        "foot": lambda date: (
            f"Donnéeën: „La production d'énergie électrique au Luxembourg“, publizéiert vu Leneda op "
            f"data.public.lu (CC0), Relevé vum {date}; Populatioun: RNPP (CC0). Ugeschloss Leeschtung (kW), "
            f"net produzéiert Energie. Ofgeleet Donnéeën ënner CC BY 4.0."),
        "privacy": ("Moossung ouni Cookien: Cloudflare Web Analytics an anonym Klickzieler "
                    "(keng IP-Adress, keen Identifiant gespäichert)."),
        "by": "Analyse: Sitraka Forler",
        "crumb_home": "Photovoltaik zu Lëtzebuerg",
    },
}

FOR = {
    "fr": {
        "title": "Pour les communes : vos données photovoltaïques, prêtes à présenter",
        "desc": ("Une page par commune, mise à jour chaque semaine : puissance raccordée, tailles des installations, "
                 "tranches du Klimabonus Gemengen, progression et comparaison avec les communes voisines."),
        "eyebrow": "Pour les communes",
        "h1": "Vos données photovoltaïques, <span class=\"sun\">prêtes à présenter</span>",
        "paras": [
            "Chaque commune a sa page, mise à jour chaque lundi à partir des données ouvertes de Leneda : puissance "
            "raccordée, nombre d'installations, part du solaire, watts par habitant, tailles des installations, "
            "et comparaison avec les communes du canton et les communes de taille comparable.",
            "Les tailles sont aussi présentées selon les tranches du <strong>Klimabonus Gemengen</strong> (30, 200 et "
            "500 kWc, 5 MWc) : on voit d'un coup d'œil ce qui relève des aides aux communes et ce qui relève du "
            "Klimabonus des particuliers.",
            "Leneda remplace chaque semaine son fichier « une ligne par installation », sans garder d'historique. "
            "Depuis le 14 septembre 2026, une copie est archivée ici chaque semaine : chaque page communale montre "
            "la progression depuis cette date.",
            "Tous les chiffres sont téléchargeables en CSV, sous licence CC BY 4.0, pour vos propres analyses ou un "
            "point au conseil communal.",
        ],
        "limits_h": "Ce que ces données ne disent pas",
        "limits": ("Elles décrivent la puissance raccordée (kW), pas l'énergie produite (kWh), et ne distinguent pas "
                   "les installations communales des installations privées. Le suivi de vos propres bâtiments "
                   "demande vos propres données."),
        "contact_h": "Une question, un besoin pour votre commune ?",
        "contact": ("Écrivez à <a href=\"mailto:hello@sitraka.lu?subject=Commune%20%3A%20solaire.sitraka.lu\">"
                    "hello@sitraka.lu</a>, en indiquant votre commune."),
        "list_h": "Les 100 communes",
    },
    "en": {
        "title": "For municipalities: your solar PV data, ready to present",
        "desc": ("One page per municipality, updated every week: connected capacity, installation sizes, "
                 "Klimabonus Gemengen bands, progress and comparison with nearby municipalities."),
        "eyebrow": "For municipalities",
        "h1": "Your solar PV data, <span class=\"sun\">ready to present</span>",
        "paras": [
            "Every municipality has its own page, updated every Monday from Leneda's open data: connected capacity, "
            "number of installations, solar share, watts per inhabitant, installation sizes, and a comparison with "
            "the municipalities of the canton and those of similar size.",
            "Sizes are also shown by <strong>Klimabonus Gemengen</strong> band (30, 200 and 500 kWp, 5 MWp): you see "
            "at a glance what falls under municipal subsidies and what falls under the household Klimabonus.",
            "Leneda replaces its “one row per installation” file every week and keeps no history. Since 14 September "
            "2026, a copy is archived here every week: each municipal page shows the progress since that date.",
            "All figures can be downloaded as CSV, under CC BY 4.0, for your own analyses or a council briefing.",
        ],
        "limits_h": "What these data do not say",
        "limits": ("They describe connected capacity (kW), not energy produced (kWh), and do not distinguish "
                   "municipal installations from private ones. Tracking your own buildings requires your own data."),
        "contact_h": "A question or a need for your municipality?",
        "contact": ("Write to <a href=\"mailto:hello@sitraka.lu?subject=Municipality%3A%20solaire.sitraka.lu\">"
                    "hello@sitraka.lu</a>, mentioning your municipality."),
        "list_h": "All 100 municipalities",
    },
    "de": {
        "title": "Für Gemeinden: Ihre Photovoltaik-Daten, bereit zur Präsentation",
        "desc": ("Eine Seite je Gemeinde, wöchentlich aktualisiert: angeschlossene Leistung, Anlagengrößen, Stufen "
                 "des Klimabonus Gemengen, Entwicklung und Vergleich mit Nachbargemeinden."),
        "eyebrow": "Für Gemeinden",
        "h1": "Ihre Photovoltaik-Daten, <span class=\"sun\">bereit zur Präsentation</span>",
        "paras": [
            "Jede Gemeinde hat ihre eigene Seite, jeden Montag aus den offenen Daten von Leneda aktualisiert: "
            "angeschlossene Leistung, Zahl der Anlagen, Solaranteil, Watt pro Einwohner, Anlagengrößen und ein "
            "Vergleich mit den Gemeinden des Kantons und Gemeinden ähnlicher Größe.",
            "Die Größen werden auch nach den Stufen des <strong>Klimabonus Gemengen</strong> gezeigt (30, 200 und "
            "500 kWp, 5 MWp): Sie sehen auf einen Blick, was unter die Gemeindeförderung fällt und was unter den "
            "Klimabonus für Privathaushalte.",
            "Leneda ersetzt seine Datei „eine Zeile je Anlage“ jede Woche, ohne Verlauf. Seit dem 14. September 2026 "
            "wird hier jede Woche eine Kopie archiviert: Jede Gemeindeseite zeigt die Entwicklung seit diesem Datum.",
            "Alle Zahlen stehen als CSV unter CC BY 4.0 zum Download bereit, für eigene Analysen oder eine Vorlage "
            "im Gemeinderat.",
        ],
        "limits_h": "Was diese Daten nicht sagen",
        "limits": ("Sie beschreiben die angeschlossene Leistung (kW), nicht die erzeugte Energie (kWh), und "
                   "unterscheiden nicht zwischen Gemeinde- und Privatanlagen. Für Ihre eigenen Gebäude braucht es "
                   "Ihre eigenen Daten."),
        "contact_h": "Eine Frage oder ein Anliegen Ihrer Gemeinde?",
        "contact": ("Schreiben Sie an <a href=\"mailto:hello@sitraka.lu?subject=Gemeinde%3A%20solaire.sitraka.lu\">"
                    "hello@sitraka.lu</a> und nennen Sie Ihre Gemeinde."),
        "list_h": "Alle 100 Gemeinden",
    },
    "lb": {
        "title": "Fir Gemengen: Är Photovoltaik-Donnéeën, prett fir ze presentéieren",
        "desc": ("Eng Säit pro Gemeng, all Woch aktualiséiert: ugeschloss Leeschtung, Gréisste vun den "
                 "Installatiounen, Tranche vum Klimabonus Gemengen, Entwécklung a Verglach mat den Nopeschgemengen."),
        "eyebrow": "Fir Gemengen",
        "h1": "Är Photovoltaik-Donnéeën, <span class=\"sun\">prett fir ze presentéieren</span>",
        "paras": [
            "All Gemeng huet hir eege Säit, all Méindeg aus den oppenen Donnéeë vu Leneda aktualiséiert: ugeschloss "
            "Leeschtung, Zuel vun den Installatiounen, Solarundeel, Watt pro Awunner, Gréisste vun den "
            "Installatiounen an e Verglach mat de Gemengen aus dem Kanton a Gemenge vun änlecher Gréisst.",
            "D'Gréisste ginn och no den Tranche vum <strong>Klimabonus Gemengen</strong> gewisen (30, 200 a 500 kWp, "
            "5 MWp): Dir gesitt op ee Bléck, wat ënner d'Gemengenhëllefen fält a wat ënner de Klimabonus fir "
            "Privatleit.",
            "Leneda ersetzt säi Fichier „eng Zeil pro Installatioun“ all Woch, ouni Historique. Zënter dem "
            "14. September 2026 gëtt hei all Woch eng Kopie archivéiert: all Gemengesäit weist d'Entwécklung "
            "zënter deem Datum.",
            "All Zuele kënnen als CSV ënner CC BY 4.0 erofgeluede ginn, fir Är eegen Analysen oder e Punkt am "
            "Gemengerot.",
        ],
        "limits_h": "Wat dës Donnéeën net soen",
        "limits": ("Si beschreiwen d'ugeschloss Leeschtung (kW), net déi produzéiert Energie (kWh), a maachen "
                   "keen Ënnerscheed tëscht Gemengen- a Privatinstallatiounen. Fir Är eege Gebaier braucht et Är "
                   "eegen Donnéeën."),
        "contact_h": "Eng Fro oder e Besoin fir Är Gemeng?",
        "contact": ("Schreift un <a href=\"mailto:hello@sitraka.lu?subject=Gemeng%3A%20solaire.sitraka.lu\">"
                    "hello@sitraka.lu</a> a gitt Är Gemeng un."),
        "list_h": "All 100 Gemengen",
    },
}

EXTRA_CSS = """
  .crumb{font-size:13px;color:var(--ink-3);margin:0 0 14px}.crumb a{color:var(--amber-text)}
  .kpis.k6{grid-template-columns:repeat(3,minmax(0,1fr))}
  table.cmp{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
  table.cmp th,table.cmp td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
  table.cmp th:first-child,table.cmp td:first-child,table.cmp th:nth-child(2),table.cmp td:nth-child(2){text-align:left}
  table.cmp thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);font-weight:600;background:none;position:static;cursor:default}
  table.cmp tr.me td{background:var(--amber-soft);font-weight:600}
  table.cmp a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
  table.cmp a:hover{color:var(--amber-text);border-color:var(--amber)}
  .tw{overflow-x:auto}
  .links{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-top:10px}
  .links a{display:block;padding:12px 14px;border:1px solid var(--line);border-left:3px solid var(--amber);background:var(--card);color:var(--ink);text-decoration:none;font-size:14px;font-weight:600}
  .links a:hover{border-color:var(--amber)}
  .pn{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:28px;font-size:14px}
  .pn a{color:var(--amber-text)}
  .cfoot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);font-size:13px;color:var(--ink-2)}
  .cfoot p{margin:0 0 8px;max-width:90ch}.cfoot a{color:var(--amber-text)}
  #aides table.mini td{text-align:right}
  #aides table.mini td:last-child{text-align:left;font-family:var(--body);white-space:normal;min-width:150px}
  #aides table.mini th{white-space:nowrap}
  .prose a{color:var(--amber-text)}
  .clist div{break-inside:avoid}
  .kbnote2{font-size:13px;color:var(--ink-2);margin:10px 0 0;max-width:90ch}
  .prose p{font-size:15.5px;max-width:70ch;color:var(--ink)}
  .clist{columns:4 190px;column-gap:24px;font-size:14px;margin-top:10px}
  .clist h3{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin:12px 0 4px;break-after:avoid}
  .clist a{display:block;color:var(--ink);text-decoration:none;padding:2px 0}.clist a:hover{color:var(--amber-text)}
  @media(max-width:850px){.kpis.k6{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:440px){.kpis.k6{grid-template-columns:1fr}}
"""


# ──────────────── rendu ───────────────────────────────────────────────────
def _shell(lang, title, desc, canonical, alternates, style, seriesbar, body, jsonld):
    if lang != "en":   # « 45 % » ne se coupe pas avant le signe
        body = body.replace(" %", "\u202f%")
    alt = "".join(f'<link rel="alternate" hreflang="{c}" href="{u}">' for c, u in alternates)
    alt += f'<link rel="alternate" hreflang="x-default" href="{dict(alternates)["en"]}">'
    return (f'<!doctype html>\n<html lang="{lang}">\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
            f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(desc)}">\n'
            f'<link rel="canonical" href="{canonical}">\n<meta property="og:url" content="{canonical}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="Lux-Solaire">\n'
            f'<meta property="og:title" content="{esc(title)}">\n<meta property="og:description" content="{esc(desc)}">\n'
            f'<meta property="og:image" content="https://solaire.sitraka.lu/{ {"fr": "og.png"}.get(lang, f"og.{lang}.png") }">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n{alt}\n'
            f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>\n'
            f"<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
            f"data-cf-beacon='{{\"token\": \"48047aeb049d4a6ba27a197d274297a7\"}}'></script>\n"
            f"<style>{style}{EXTRA_CSS}</style>\n<div class=\"wrap\">\n{seriesbar}\n{body}\n</div>\n"
            f'<script defer src="/ev.js"></script>\n</html>\n')


def _toggle(paths, lang, flags):
    cur = ' class="cur"'
    return "".join(f'<a href="{p}"{cur if c == lang else ""}>{flags[c]}{FLAG_LABEL[c]}</a>'
                   for c, p in paths)


def write_all(root, site, blobs, cdate, thousands, dec1_raw, person, luxembourg, flags):
    """Écrit les 400 pages communales et les 4 pages « Pour les communes » ;
    renvoie les groupes (chemins par langue, dates) pour le sitemap."""
    base = blobs["fr"]
    communes = sorted(base["communes"], key=lambda c: slug(c["c"]))
    n_all = len(communes)
    rank = {k: {c["lau2"]: i + 1 for i, c in enumerate(sorted(base["communes"], key=lambda c: -c[k]))}
            for k in ("wpc", "ipk", "g", "pv")}
    pages = {}
    for lang in LANGS:
        main = (root / HOME[lang].strip("/") / "index.html") if HOME[lang] != "/" else root / "index.html"
        src = main.read_text()
        pages[lang] = (re.search(r"<style>(.*?)</style>", src, re.S).group(1),
                       re.search(r'<div class="seriesbar">.*?</div>', src, re.S).group(0))
    groups = []

    def T(n, lang):   # espace insécable fine : « +6 719 kW » ne se coupe pas en fin de ligne
        return thousands(n, lang).replace(" ", "\u202f")

    def dec1(x, lang):
        return dec1_raw(x, lang).replace(" ", "\u202f")
    for i, c in enumerate(communes):
        s = slug(c["c"])
        alternates = [(l, site + CPATH[l] + s + "/") for l in ORDER]
        groups.append((tuple((l, CPATH[l] + s + "/") for l in ORDER), cdate))
        for lang in LANGS:
            d, L = blobs[lang], S[lang]
            meta, P = d["meta"], d["population"]
            fq = d["series"][0]["label"]
            date = meta["date"]
            mw = dec1(c["pv"] / 1000, lang)
            nn = T(c["n"], lang)
            wpc = T(c["wpc"], lang)
            med = T(P["median_wpc"], lang)
            sg = lambda x: ("+" if x > 0 else "−" if x < 0 else "±") + T(abs(round(x)), lang)  # noqa: E731
            gkw = sg(c["g"])
            gp = ("+" if c["gp"] > 0 else "") + T(round(c["gp"]), lang)
            title = L["title"](c["c"], nn, mw, meta["date_iso"][:4])
            desc = L["desc"](c["c"], c["k"], mw, date, nn, wpc)
            # tailles détaillées (blob traduit pour les libellés de classes)
            rows = [(sz["bin"], n, kw / 1000) for sz, (n, kw) in zip(d["sizes"], base["sizes_c"][str(c["lau2"])])]
            nt = sum(r[1] for r in rows) or 1
            ct = sum(r[2] for r in rows) or 1
            h = (base.get("hist") or {}).get("c", {}).get(str(c["lau2"])) if base.get("hist") else None
            hd = h[2] if h else None
            unit = lambda b: "" if "MW" in b else " kW"  # noqa: E731
            pct = lambda x: (dec1(x, lang) if x < 1 else T(round(x), lang))  # noqa: E731

            def capl(x):
                return f"{T(round(x * 1000), lang)} kW" if 0 < x < 1 else f"{dec1(x, lang)} MW"
            bars = "".join(
                f'<div class="bin">{b}{unit(b)}</div><div class="duo">'
                f'<div class="b cnt{" in" if n / nt * 100 > 70 else ""}" style="width:{max(n / nt * 100, 0.4):.2f}%">'
                f'<i>{pct(n / nt * 100)} % · {T(n, lang)} {L["inst"]}'
                f'{f" <em>({sg(hd[j])})</em>" if hd and hd[j] else ""}</i></div>'
                f'<div class="b cap{" in" if kw / ct * 100 > 70 else ""}" style="width:{max(kw / ct * 100, 0.4):.2f}%">'
                f'<i>{pct(kw / ct * 100)} % · {capl(kw)}</i></div></div>'
                for j, (b, n, kw) in enumerate(rows))
            sn = round(sum(r[1] for r in rows[:SMALL_BINS]) / nt * 100)
            sc = round(sum(r[2] for r in rows[:SMALL_BINS]) / ct * 100)
            kb_rows = "".join(
                f'<tr><th scope="row">{b}{unit(b)}</th><td>{T(n, lang)}</td><td>{capl(kw / 1000)}</td>'
                f'<td>{L["kb_aid"][["0–30", "30–200", "200–500", "0,5–5 MW", "> 5 MW"].index(fb)]}</td></tr>'
                for b, fb, (n, kw) in zip(d["kb"]["bins"], base["kb"]["bins"], base["kb"]["c"][str(c["lau2"])]))
            # comparaison
            me = ' class="me"'
            kb_head = "".join(f'<th scope="col">{x}</th>' for x in L["kb_cols"])

            def cmp_table(lst):
                hd_ = "".join(f"<th scope=\"col\">{x}</th>" for x in L["cmp_cols"])
                body = "".join(
                    f'<tr{me if o["lau2"] == c["lau2"] else ""}>'
                    f'<td><a href="{CPATH[lang]}{slug(o["c"])}/">{o["c"]}</a></td><td>{o["k"]}</td>'
                    f'<td>{dec1(o["pv"] / 1000, lang)}</td><td>{T(o["n"], lang)}</td><td>{T(o["wpc"], lang)}</td>'
                    f'<td>{dec1(o["ipk"], lang)}</td><td>{sg(o["g"])}</td></tr>'
                    for o in sorted(lst, key=lambda o: -o["wpc"]))
                return f'<div class="tw"><table class="cmp"><thead><tr>{hd_}</tr></thead><tbody>{body}</tbody></table></div>'
            same_k = [o for o in base["communes"] if o["k"] == c["k"]]
            similar = sorted((o for o in base["communes"] if o["lau2"] != c["lau2"]),
                             key=lambda o: abs(o["pop"] - c["pop"]))[:6] + [c]
            # KPI
            if h:
                k6 = (L["k_hist"](d["hist"]["date"]),
                      L["k_hist_val"](sg(h[0])), L["k_hist_sub"](("+" if h[1] >= 0 else "−") + dec1(abs(h[1]) / 1000, lang)))
            else:
                k6 = (L["k_pop"], T(c["pop"], lang), L["k_pop_sub"])
            kpis = (
                f'<div class="kpi hero"><div class="lbl">{L["k_pv"]}</div><div class="val">{mw} MW</div>'
                f'<div class="sub">{L["k_pv_sub"](nn)}</div></div>'
                f'<div class="kpi"><div class="lbl">{L["k_share"]}</div><div class="val">{dec1(c["share"], lang)} %</div>'
                f'<div class="sub">{L["k_share_sub"](dec1(c["tot"] / 1000, lang))}</div></div>'
                f'<div class="kpi"><div class="lbl">{L["k_wpc"]}</div><div class="val">{wpc}</div>'
                f'<div class="sub">{L["rank"](rank["wpc"][c["lau2"]])} · {L["med"](med)}</div></div>'
                f'<div class="kpi"><div class="lbl">{L["k_ipk"]}</div><div class="val">{dec1(c["ipk"], lang)}</div>'
                f'<div class="sub">{L["k_ipk_sub"](L["rank"](rank["ipk"][c["lau2"]]), dec1(c["rpk"], lang))}</div></div>'
                f'<div class="kpi"><div class="lbl">{L["k_g"](fq)}</div><div class="val">{gkw} kW</div>'
                f'<div class="sub">{L["rank"](rank["g"][c["lau2"]])} · {gp} %</div></div>'
                f'<div class="kpi"><div class="lbl">{k6[0]}</div><div class="val">{k6[1]}</div>'
                f'<div class="sub">{k6[2]}</div></div>')
            hist_note = f'<p class="kbnote2">{L["hist_note"](d["hist"]["date"])}</p>' if h else ""
            prev_c, next_c = communes[i - 1], communes[(i + 1) % n_all]
            body = (
                f'<p class="crumb"><a href="{HOME[lang]}">{L["crumb_home"]}</a> · '
                f'<a href="{FORPATH[lang]}">{L["all"]}</a></p>'
                f'<header><div class="eyebrow">{L["eyebrow"](c["k"])}</div><h1>{L["h1"](c["c"])}</h1>'
                f'<p class="standfirst">{L["stand"](c["c"], mw, date, nn, wpc, med, gkw, gp, fq)}</p></header>'
                f'<div class="kpis k6">{kpis}</div>'
                f'<section id="tailles"><div class="sec-head"><h2>{L["sizes_h"]}</h2></div>'
                f'<p class="lede">{L["sizes_lede"](c["c"], sn, sc)}</p><div class="card">'
                f'<div class="pkey"><span><span class="sw" style="background:var(--amber);display:inline-block;vertical-align:-1px"></span> {L["k_cnt"]}</span>'
                f'<span><span class="sw" style="background:var(--ink);opacity:.82;display:inline-block;vertical-align:-1px"></span> {L["k_cap"]}</span></div>'
                f'<div class="pair">{bars}</div>{hist_note}</div></section>'
                f'<section id="aides"><div class="sec-head"><h2>{L["kb_h"]}</h2></div><div class="card">'
                f'<div class="tw"><table class="mini"><thead><tr>{kb_head}</tr></thead>'
                f'<tbody>{kb_rows}</tbody></table></div><p class="kbnote2">{L["kb_note"]}</p></div></section>'
                f'<section id="comparaison"><div class="sec-head"><h2>{L["cmp_h"]}</h2></div>'
                f'<p class="lede">{L["cmp_lede"](fq)}</p>'
                f'<h3 class="refs" style="font-size:15px;margin:18px 0 6px">{L["cmp_canton"](c["k"])}</h3>{cmp_table(same_k)}'
                f'<h3 class="refs" style="font-size:15px;margin:22px 0 6px">{L["cmp_size"]}</h3>{cmp_table(similar)}</section>'
                f'<section><div class="sec-head"><h2>{L["links_h"]}</h2></div><div class="links">'
                f'<a href="{HOME[lang]}?commune={s}#paradoxe">{L["l_dash"]}</a>'
                f'<a href="{SIM[lang]}">{L["l_sim"]}</a>'
                f'<a href="{FORPATH[lang]}">{L["l_for"]}</a>'
                f'<a href="/data/csv/solaire_communes_tailles.csv">{L["l_csv"]}</a></div>'
                f'<nav class="pn" aria-label="{L["all"]}"><a href="{CPATH[lang]}{slug(prev_c["c"])}/">← {L["prev"]} : {prev_c["c"]}</a>'
                f'<a href="{CPATH[lang]}{slug(next_c["c"])}/">{L["next"]} : {next_c["c"]} →</a></nav></section>'
                f'<footer class="cfoot"><p>{L["foot"](date)}</p><p>{L["privacy"]}</p>'
                f'<p>{L["by"]} · <a href="https://sitraka.lu">sitraka.lu</a> · '
                f'<a href="https://github.com/Sitraka17/lux-solaire">code source</a></p></footer>')
            canonical = site + CPATH[lang] + s + "/"
            jsonld = {"@context": "https://schema.org", "@type": "WebPage", "@id": canonical, "url": canonical,
                      "name": title, "description": desc, "inLanguage": lang, "dateModified": cdate[lang],
                      "isPartOf": {"@id": site + HOME[lang]}, "author": person,
                      "about": {"@type": "Place", "name": c["c"], "containedInPlace": luxembourg}}
            sb = re.sub(r'(<span class="langtoggle">).*?(</span>)',
                        lambda m: m.group(1) + _toggle([(l, CPATH[l] + s + "/") for l in ORDER], lang, flags) + m.group(2),
                        pages[lang][1], count=1, flags=re.S)
            out = root / CPATH[lang].strip("/") / s / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            html = _shell(lang, title, desc, canonical, alternates, pages[lang][0], sb, body, jsonld)
            if "—" in html:
                raise SystemExit(f"{lang}/{s} : tiret cadratin dans la page communale")
            out.write_text(html)
    # page « Pour les communes »
    for_paths = tuple((l, FORPATH[l]) for l in ORDER)
    for lang in LANGS:
        F, L = FOR[lang], S[lang]
        by_k = {}
        for c in sorted(base["communes"], key=lambda c: slug(c["c"])):
            by_k.setdefault(c["k"], []).append(c)
        clist = "".join(f'<div><h3>{k}</h3>' + "".join(f'<a href="{CPATH[lang]}{slug(c["c"])}/">{c["c"]}</a>' for c in cs)
                        + "</div>" for k, cs in sorted(by_k.items()))
        body = (f'<p class="crumb"><a href="{HOME[lang]}">{L["crumb_home"]}</a></p>'
                f'<header><div class="eyebrow">{F["eyebrow"]}</div><h1>{F["h1"]}</h1></header>'
                f'<section class="prose">{"".join(f"<p>{p}</p>" for p in F["paras"])}'
                f'<h2>{F["limits_h"]}</h2><p>{F["limits"]}</p>'
                f'<h2>{F["contact_h"]}</h2><p>{F["contact"]}</p></section>'
                f'<section id="liste"><div class="sec-head"><h2>{F["list_h"]}</h2></div><div class="clist">{clist}</div></section>'
                f'<footer class="cfoot"><p>{L["foot"](blobs[lang]["meta"]["date"])}</p><p>{L["privacy"]}</p>'
                f'<p>{L["by"]} · <a href="https://sitraka.lu">sitraka.lu</a></p></footer>')
        alternates = [(l, site + FORPATH[l]) for l in ORDER]
        canonical = site + FORPATH[lang]
        jsonld = {"@context": "https://schema.org", "@type": "WebPage", "@id": canonical, "url": canonical,
                  "name": F["title"], "description": F["desc"], "inLanguage": lang, "dateModified": cdate[lang],
                  "isPartOf": {"@id": site + HOME[lang]}, "author": person}
        sb = re.sub(r'(<span class="langtoggle">).*?(</span>)',
                    lambda m: m.group(1) + _toggle(for_paths, lang, flags) + m.group(2), pages[lang][1], count=1, flags=re.S)
        out = root / FORPATH[lang].strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        html = _shell(lang, F["title"], F["desc"], canonical, alternates, pages[lang][0], sb, body, jsonld)
        if "—" in html:
            raise SystemExit(f"{lang} : tiret cadratin dans la page pour les communes")
        out.write_text(html)
    groups.append((for_paths, cdate))
    return groups
