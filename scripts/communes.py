"""Pages par commune (une par commune du relevé, 100 en 2026, × 5 langues) et page « Pour les communes ».

Appelé par build.render_all APRÈS l'écriture des tableaux de bord : la feuille
de style et la barre de série sont reprises des pages déjà rendues, pour que
les pages communales restent identiques au reste du site. Les textes sont ici
(configuration par langue), pas dans les dictionnaires des gabarits.
"""
import html as html_mod
import json
import re
import unicodedata
import urllib.parse

import baremes   # scripts/baremes.json : taux et plafonds du Klimabonus Gemengen (source unique)
import grandes   # nouvelles grandes installations (> 100 kW) : détection et textes
import ossature  # bandeau, sélecteur de langue, fil d'Ariane et colophon communs à tous les types de pages

CPATH = {"en": "/municipality/", "fr": "/fr/commune/", "de": "/de/gemeinde/", "lb": "/lb/gemeng/",
         "pt": "/pt/municipio/"}
FORPATH = {"en": "/for-municipalities/", "fr": "/fr/pour-les-communes/", "de": "/de/fuer-gemeinden/",
           "lb": "/lb/fir-gemengen/", "pt": "/pt/para-os-municipios/"}
HOME = {"en": "/", "fr": "/fr/", "de": "/de/", "lb": "/lb/", "pt": "/pt/"}
SIM = {"en": "/simulator/", "fr": "/fr/simulateur/", "de": "/de/rechner/", "lb": "/lb/rechner/",
       "pt": "/pt/simulador/"}
LANGS = ("en", "fr", "de", "lb", "pt")
ORDER = ("en", "fr", "de", "lb", "pt")
FLAG_LABEL = ossature.CODE   # codes du sélecteur de langue (« LB » = code de langue ISO 639-1)
# attribut lang de <html> (pages communales ET gabarits, importé par build.py) : portugais du
# Portugal (césure, lecteurs d'écran) ; hreflang, og:locale et JSON-LD gardent « pt »
HTML_LANG = {"pt": "pt-PT"}
SRC_LENEDA = "https://data.public.lu/fr/datasets/la-production-denergie-electrique-au-luxembourg/"
SRC_RNPP = ("https://data.public.lu/fr/datasets/registre-national-des-personnes-physiques-rnpp-"
            "population-par-commune-population-per-municipality/")
SRC_KBG = baremes.B["klimabonus_gemengen"]["source"]   # guide pratique Klimabonus Gemengen
SRC_LABEL = {"fr": ("Sources", "population", "habitants au"), "en": ("Sources", "population", "inhabitants as of"),
             "de": ("Quellen", "Bevölkerung", "Einwohner, Stand"), "lb": ("Quellen", "Populatioun", "Awunner, Stand"),
             "pt": ("Fontes", "população de", "habitantes em")}
SKIP = {"fr": "Aller au contenu", "en": "Skip to content", "de": "Zum Inhalt springen",
        "lb": "Op den Inhalt sprangen", "pt": "Ir para o conteúdo"}   # lien d'évitement (mêmes libellés que les dictionnaires des gabarits)
SMALL_BINS = 4   # classes détaillées de 30 kW ou moins (0-5, 5-10, 10-15, 15-30)
# Appel à l'action vers la page de contact de sitraka.lu (mêmes textes et style .contact-cta
# que les gabarits ; le paramètre from= fixe l'objet du courriel côté sitraka.lu)
_CONTACT_TXT = {"fr": ("https://sitraka.lu/fr/contact/?from=solaire", "Vous voulez ça pour votre commune\u00a0? Parlons-en"),
                "en": ("https://sitraka.lu/contact/?from=solaire", "Want this for your commune? Let's talk"),
                "de": ("https://sitraka.lu/de/contact/?from=solaire", "Wollen Sie das für Ihre Gemeinde? Sprechen wir"),
                "lb": ("https://sitraka.lu/contact/?from=solaire", "Wëllt Dir dat fir Är Gemeng? Schwätze mer driwwer"),
                # pas de page de contact en portugais sur sitraka.lu : page française, signalée
                "pt": ("https://sitraka.lu/fr/contact/?from=solaire", "Quer isto para o seu município? Vamos falar (em francês)")}
CONTACT = {l: f'<p class="contact-cta"><a href="{u}">{s} <span aria-hidden="true">→</span></a></p>'
           for l, (u, s) in _CONTACT_TXT.items()}

# Klimabonus Gemengen : colonne « Aide » et note des pages, générées depuis baremes.json
_KBG = baremes.gemengen()
_KBG_YEAR, _OMB = _KBG["bareme"], _KBG["ombriere"]

# ──────────────── lot 2 du cahier des charges (9/11/2026) : légendes numérotées, sources, page d'offre ────
FIG_LABEL = {"fr": "Figure", "en": "Figure", "de": "Abbildung", "lb": "Figur", "pt": "Figura"}
TAB_LABEL = {"fr": "Tableau", "en": "Table", "de": "Tabelle", "lb": "Tabell", "pt": "Tabela"}
_SF = "Sitraka Forler"
L2 = {
    "fr": {
        "rankcol": "N°",
        "fig1": lambda c: f"Part des installations et part de la puissance par classe de taille, à {c}.",
        "src_inst": lambda d: f"Source : Leneda (data.public.lu), fichier hebdomadaire par installation du {d} ; traitement : {_SF}.",
        "t_kb": lambda c: f"Installations de {c} selon les tranches du Klimabonus Gemengen, et aide prévue pour une centrale communale.",
        "src_kb": lambda d: (f"Sources : Leneda (data.public.lu), fichier par installation du {d} ; guide pratique du "
                             f"Klimabonus Gemengen, barème {_KBG_YEAR} ; traitement : {_SF}."),
        "src_cmp": lambda d, pd: f"Sources : Leneda (data.public.lu), relevé du {d} ; population RNPP au {pd} ; traitement : {_SF}.",
        "simq": lambda c: f"Est-ce rentable sur votre toit à {c} ?", "sim_word": "Simulateur",
    },
    "en": {
        "rankcol": "No.",
        "fig1": lambda c: f"Share of installations and share of capacity by size class, in {c}.",
        "src_inst": lambda d: f"Source: Leneda (data.public.lu), weekly per-installation file of {d}; processing: {_SF}.",
        "t_kb": lambda c: f"Installations in {c} by Klimabonus Gemengen band, and the subsidy available for a municipal plant.",
        "src_kb": lambda d: (f"Sources: Leneda (data.public.lu), per-installation file of {d}; Klimabonus Gemengen "
                             f"practical guide, {_KBG_YEAR} scale; processing: {_SF}."),
        "src_cmp": lambda d, pd: f"Sources: Leneda (data.public.lu), reading of {d}; RNPP population as of {pd}; processing: {_SF}.",
        "simq": lambda c: f"Is solar worth it on your roof in {c}?", "sim_word": "Calculator",
    },
    "de": {
        "rankcol": "Nr.",
        "fig1": lambda c: f"Anteil der Anlagen und Anteil der Leistung nach Größenklasse, in {c}.",
        "src_inst": lambda d: f"Quelle: Leneda (data.public.lu), wöchentliche Datei je Anlage vom {d}; Auswertung: {_SF}.",
        "t_kb": lambda c: f"Anlagen in {c} nach Stufen des Klimabonus Gemengen und Förderung für eine Gemeindeanlage.",
        "src_kb": lambda d: (f"Quellen: Leneda (data.public.lu), Datei je Anlage vom {d}; Praxisleitfaden Klimabonus "
                             f"Gemengen, Stand {_KBG_YEAR}; Auswertung: {_SF}."),
        "src_cmp": lambda d, pd: f"Quellen: Leneda (data.public.lu), Erhebung vom {d}; Bevölkerung RNPP, Stand {pd}; Auswertung: {_SF}.",
        "simq": lambda c: f"Lohnt sich Solar auf Ihrem Dach in {c}?", "sim_word": "Rechner",
    },
    "lb": {
        "rankcol": "Nr.",
        "fig1": lambda c: f"Undeel vun den Installatiounen an Undeel vun der Leeschtung no Gréisstklass, zu {c}.",
        "src_inst": lambda d: f"Quell: Leneda (data.public.lu), wëchentleche Fichier pro Installatioun vum {d}; Auswäertung: {_SF}.",
        "t_kb": lambda c: f"Installatiounen zu {c} no den Tranche vum Klimabonus Gemengen, an d'Hëllef fir eng Gemengenanlag.",
        "src_kb": lambda d: (f"Quellen: Leneda (data.public.lu), Fichier pro Installatioun vum {d}; praktesche Guide vum "
                             f"Klimabonus Gemengen, Bareem {_KBG_YEAR}; Auswäertung: {_SF}."),
        "src_cmp": lambda d, pd: f"Quellen: Leneda (data.public.lu), Relevé vum {d}; Populatioun RNPP, Stand {pd}; Auswäertung: {_SF}.",
        "simq": lambda c: f"Rentéiert Solar op Ärem Daach zu {c}?", "sim_word": "Rechner",
    },
    "pt": {
        "rankcol": "N.º",
        "fig1": lambda c: f"Parte das instalações e parte da potência por classe de potência, em {c}.",
        "src_inst": lambda d: f"Fonte: Leneda (data.public.lu), ficheiro semanal por instalação de {d}; tratamento: {_SF}.",
        "t_kb": lambda c: f"Instalações em {c} segundo os escalões do Klimabonus Gemengen, e ajuda prevista para uma central municipal.",
        "src_kb": lambda d: (f"Fontes: Leneda (data.public.lu), ficheiro por instalação de {d}; guia prático do Klimabonus "
                             f"Gemengen, tabela de {_KBG_YEAR}; tratamento: {_SF}."),
        "src_cmp": lambda d, pd: f"Fontes: Leneda (data.public.lu), levantamento de {d}; população RNPP em {pd}; tratamento: {_SF}.",
        "simq": lambda c: f"O solar compensa no seu telhado em {c}?", "sim_word": "Simulador",
    },
}

# Page « Pour les communes », structurée en page d'offre (L2.15) : AUCUN prix, jamais « conseiller en
# énergie » ni « audit », aucun délai ni engagement ; contrôlé par check_offer() à chaque build.
_REPO = "https://github.com/Sitraka17/lux-solaire"
DEMO_COMMUNE = "differdange"   # exemple de données publiques, pas une référence client
_CT = {"fr": "https://sitraka.lu/fr/contact/?from=solaire-communes", "en": "https://sitraka.lu/contact/?from=solaire-communes",
       "de": "https://sitraka.lu/de/contact/?from=solaire-communes", "lb": "https://sitraka.lu/contact/?from=solaire-communes",
       "pt": "https://sitraka.lu/fr/contact/?from=solaire-communes"}
FOR2 = {
    "fr": {
        "s1": "1. Démonstration",
        "f1cap": lambda c: f"Extrait réel de la page publique de {c}, prise comme exemple : les indicateurs clés, avec les mêmes chiffres que la page.",
        "open": "Ouvrir la page complète",
        "f2h": "Simulateur citoyen",
        "f2lead": "Trois outils pour un habitant, calculés dans le navigateur :",
        "tools": (("Production", "ce que produirait une installation sur son toit (profil PVGIS)"),
                  ("Rentabilité", "Klimabonus ou rémunération garantie de l'injection, retour sur investissement"),
                  ("Chauffage", "pompe à chaleur et panneaux comparés au chauffage actuel")),
        "f2link": lambda k: f"Ouvrir le simulateur préréglé sur le canton {de_k(k)}",
        "f2cap": "Le simulateur citoyen, préréglé sur le canton.",
        "src_sim": f"Sources : PVGIS (Commission européenne), guichet.lu, ILR ; détail et dates de consultation dans la méthode du simulateur.",
        "s2": "2. Ce que la commune peut obtenir",
        "t1cap": "Composantes, contenu et sources des données.",
        "t1cols": ("Composante", "Contenu", "Source des données", "Mise à jour"),
        "t1rows": (("Page communale publique",
                    "Puissance raccordée, installations, tailles, tranches du Klimabonus Gemengen, comparaison avec le canton et les communes de taille comparable",
                    "Leneda et RNPP, données ouvertes sous licence CC0", "Chaque semaine"),
                   ("Simulateur citoyen aux couleurs de la commune, avec ses aides locales",
                    "Production, rentabilité et chauffage pour un logement, avec les aides de l'État et celles de la commune",
                    "PVGIS, guichet.lu, ILR ; aides locales indiquées par la commune", "À chaque révision des aides"),
                   ("Bilan énergétique du patrimoine communal",
                    "Consommation et production des bâtiments communaux, d'une année sur l'autre",
                    "Données de la commune : factures et relevés de compteurs", "Chaque année")),
        "s3": "3. Méthode et confiance",
        "trust": ("Données publiques : Leneda (production d'énergie électrique) et RNPP (population), sous licence CC0 ; données dérivées sous licence CC BY 4.0.",
                  f"Code public : <a href=\"{_REPO}\">dépôt du site sur GitHub</a>.",
                  "Aucun cookie ni traceur : mesure d'audience sans cookie.",
                  "Aucun compte ni donnée personnelle demandés : les calculs du simulateur se font dans le navigateur.",
                  "Cinq langues : français, anglais, allemand, luxembourgeois et portugais."),
        "s4": "4. Contact",
        "btn": "Écrire pour une démonstration",
        "s5": "5. ",
    },
    "en": {
        "s1": "1. Demonstration",
        "f1cap": lambda c: f"A real excerpt from the public page of {c}, taken as an example: the key indicators, with the same figures as the page.",
        "open": "Open the full page",
        "f2h": "Citizen calculator",
        "f2lead": "Three tools for residents, computed in the browser:",
        "tools": (("Production", "what an installation on their roof would produce (PVGIS profile)"),
                  ("Return", "Klimabonus or guaranteed feed-in payment, payback period"),
                  ("Heating", "heat pump and panels compared with the current heating")),
        "f2link": lambda k: f"Open the calculator preset to the canton of {k}",
        "f2cap": "The citizen calculator, preset to the canton.",
        "src_sim": "Sources: PVGIS (European Commission), guichet.lu, ILR; details and access dates in the calculator's method.",
        "s2": "2. What a municipality can get",
        "t1cap": "Components, content and data sources.",
        "t1cols": ("Component", "Content", "Data source", "Update"),
        "t1rows": (("Public municipal page",
                    "Connected capacity, installations, sizes, Klimabonus Gemengen bands, comparison with the canton and with municipalities of similar size",
                    "Leneda and RNPP, open data under CC0", "Every week"),
                   ("Citizen calculator in the municipality's colours, with its local subsidies",
                    "Production, return and heating for a home, with State subsidies and the municipality's own",
                    "PVGIS, guichet.lu, ILR; local subsidies provided by the municipality", "Whenever subsidies are revised"),
                   ("Energy report on the municipality's buildings",
                    "Consumption and production of municipal buildings, year on year",
                    "The municipality's own data: bills and meter readings", "Every year")),
        "s3": "3. Method and trust",
        "trust": ("Public data: Leneda (electricity generation) and RNPP (population), under CC0; derived data under CC BY 4.0.",
                  f"Public code: <a href=\"{_REPO}\">the site's repository on GitHub</a>.",
                  "No cookies or trackers: cookie-free audience measurement.",
                  "No account or personal data requested: the calculator runs in the browser.",
                  "Five languages: French, English, German, Luxembourgish and Portuguese."),
        "s4": "4. Contact",
        "btn": "Write to request a demonstration",
        "s5": "5. ",
    },
    "de": {
        "s1": "1. Demonstration",
        "f1cap": lambda c: f"Echter Auszug aus der öffentlichen Seite von {c}, als Beispiel: die Kennzahlen, mit denselben Werten wie auf der Seite.",
        "open": "Ganze Seite öffnen",
        "f2h": "Rechner für Bürgerinnen und Bürger",
        "f2lead": "Drei Werkzeuge für Einwohner, im Browser berechnet:",
        "tools": (("Ertrag", "was eine Anlage auf dem eigenen Dach erzeugen würde (PVGIS-Profil)"),
                  ("Rentabilität", "Klimabonus oder garantierte Einspeisevergütung, Amortisation"),
                  ("Heizung", "Wärmepumpe und Paneele im Vergleich zur bestehenden Heizung")),
        "f2link": lambda k: f"Rechner öffnen, voreingestellt auf den Kanton {k}",
        "f2cap": "Der Rechner für Bürgerinnen und Bürger, auf den Kanton voreingestellt.",
        "src_sim": "Quellen: PVGIS (Europäische Kommission), guichet.lu, ILR; Einzelheiten und Abrufdaten in der Methode des Rechners.",
        "s2": "2. Was die Gemeinde erhalten kann",
        "t1cap": "Bestandteile, Inhalt und Datenquellen.",
        "t1cols": ("Bestandteil", "Inhalt", "Datenquelle", "Aktualisierung"),
        "t1rows": (("Öffentliche Gemeindeseite",
                    "Angeschlossene Leistung, Anlagen, Größen, Stufen des Klimabonus Gemengen, Vergleich mit dem Kanton und mit Gemeinden ähnlicher Größe",
                    "Leneda und RNPP, offene Daten unter CC0", "Jede Woche"),
                   ("Rechner in den Farben der Gemeinde, mit ihren lokalen Förderungen",
                    "Ertrag, Rentabilität und Heizung für eine Wohnung, mit den staatlichen Förderungen und denen der Gemeinde",
                    "PVGIS, guichet.lu, ILR; lokale Förderungen von der Gemeinde angegeben", "Bei jeder Änderung der Förderungen"),
                   ("Energiebilanz der Gemeindegebäude",
                    "Verbrauch und Erzeugung der Gemeindegebäude, von Jahr zu Jahr",
                    "Daten der Gemeinde: Rechnungen und Zählerstände", "Jedes Jahr")),
        "s3": "3. Methode und Vertrauen",
        "trust": ("Öffentliche Daten: Leneda (Stromerzeugung) und RNPP (Bevölkerung), unter CC0; abgeleitete Daten unter CC BY 4.0.",
                  f"Offener Code: <a href=\"{_REPO}\">Repository der Website auf GitHub</a>.",
                  "Keine Cookies, keine Tracker: Reichweitenmessung ohne Cookies.",
                  "Kein Konto, keine persönlichen Daten verlangt: Der Rechner rechnet im Browser.",
                  "Fünf Sprachen: Französisch, Englisch, Deutsch, Luxemburgisch und Portugiesisch."),
        "s4": "4. Kontakt",
        "btn": "Für eine Demonstration schreiben",
        "s5": "5. ",
    },
    "lb": {
        "s1": "1. Demonstratioun",
        "f1cap": lambda c: f"Richtegen Auszuch aus der ëffentlecher Säit vu(n) {c}, als Beispill: d'Schlësselzuelen, mat deene selwechten Zuele wéi op der Säit.",
        "open": "Ganz Säit opmaachen",
        "f2h": "Rechner fir d'Bierger",
        "f2lead": "Dräi Tools fir d'Awunner, am Browser gerechent:",
        "tools": (("Produktioun", "wat eng Installatioun op hirem Daach produzéiere géif (PVGIS-Profil)"),
                  ("Rentabilitéit", "Klimabonus oder garantéiert Vergütung fir d'Aspeisung, Amortisatioun"),
                  ("Heizung", "Wäermepompel a Panneauen am Verglach mat der aktueller Heizung")),
        "f2link": lambda k: f"De Rechner opmaachen, op de Kanton {k} agestallt",
        "f2cap": "De Rechner fir d'Bierger, op de Kanton agestallt.",
        "src_sim": "Quellen: PVGIS (Europäesch Kommissioun), guichet.lu, ILR; Detailer an Datumer vun der Consultatioun an der Method vum Rechner.",
        "s2": "2. Wat d'Gemeng kréie kann",
        "t1cap": "Bestanddeeler, Inhalt an Donnéequellen.",
        "t1cols": ("Bestanddeel", "Inhalt", "Donnéequell", "Aktualiséierung"),
        "t1rows": (("Ëffentlech Gemengesäit",
                    "Ugeschloss Leeschtung, Installatiounen, Gréissten, Tranche vum Klimabonus Gemengen, Verglach mam Kanton a mat Gemenge vun änlecher Gréisst",
                    "Leneda an RNPP, oppen Donnéeën ënner CC0", "All Woch"),
                   ("Rechner an de Faarwe vun der Gemeng, mat hire lokalen Hëllefen",
                    "Produktioun, Rentabilitéit an Heizung fir eng Wunneng, mat de Staatshëllefen an deene vun der Gemeng",
                    "PVGIS, guichet.lu, ILR; lokal Hëllefen vun der Gemeng uginn", "Bei all Ännerung vun den Hëllefen"),
                   ("Energiebilan vun de Gemengegebaier",
                    "Verbrauch a Produktioun vun de Gemengegebaier, vun engem Joer op dat anert",
                    "Donnéeë vun der Gemeng: Rechnungen a Compteursstänn", "All Joer")),
        "s3": "3. Method a Vertrauen",
        "trust": ("Ëffentlech Donnéeën: Leneda (Stroumproduktioun) an RNPP (Populatioun), ënner CC0; ofgeleet Donnéeën ënner CC BY 4.0.",
                  f"Ëffentleche Code: <a href=\"{_REPO}\">Repository vum Site op GitHub</a>.",
                  "Keng Cookien, keng Tracker: Moossung ouni Cookien.",
                  "Kee Kont a keng perséinlech Donnéeë gefrot: de Rechner rechent am Browser.",
                  "Fënnef Sproochen: Franséisch, Englesch, Däitsch, Lëtzebuergesch a Portugisesch."),
        "s4": "4. Kontakt",
        "btn": "Fir eng Demonstratioun schreiwen",
        "s5": "5. ",
    },
    "pt": {
        "s1": "1. Demonstração",
        "f1cap": lambda c: f"Excerto real da página pública de {c}, tomada como exemplo: os indicadores principais, com os mesmos números da página.",
        "open": "Abrir a página completa",
        "f2h": "Simulador para os cidadãos",
        "f2lead": "Três ferramentas para os habitantes, calculadas no navegador:",
        "tools": (("Produção", "o que produziria uma instalação no seu telhado (perfil PVGIS)"),
                  ("Rentabilidade", "Klimabonus ou remuneração garantida da injeção, retorno do investimento"),
                  ("Aquecimento", "bomba de calor e painéis comparados com o aquecimento atual")),
        "f2link": lambda k: f"Abrir o simulador predefinido para o cantão de {k}",
        "f2cap": "O simulador para os cidadãos, predefinido para o cantão.",
        "src_sim": "Fontes: PVGIS (Comissão Europeia), guichet.lu, ILR; pormenores e datas de consulta no método do simulador.",
        "s2": "2. O que o município pode obter",
        "t1cap": "Componentes, conteúdo e fontes dos dados.",
        "t1cols": ("Componente", "Conteúdo", "Fonte dos dados", "Atualização"),
        "t1rows": (("Página municipal pública",
                    "Potência ligada à rede, instalações, dimensões, escalões do Klimabonus Gemengen, comparação com o cantão e com municípios de dimensão comparável",
                    "Leneda e RNPP, dados abertos sob CC0", "Todas as semanas"),
                   ("Simulador com as cores do município, com as suas ajudas locais",
                    "Produção, rentabilidade e aquecimento para uma habitação, com as ajudas do Estado e as do município",
                    "PVGIS, guichet.lu, ILR; ajudas locais indicadas pelo município", "Sempre que as ajudas são revistas"),
                   ("Balanço energético do património municipal",
                    "Consumo e produção dos edifícios municipais, de um ano para o outro",
                    "Dados do município: faturas e leituras de contadores", "Todos os anos")),
        "s3": "3. Método e confiança",
        "trust": ("Dados públicos: Leneda (produção de energia elétrica) e RNPP (população), sob CC0; dados derivados sob CC BY 4.0.",
                  f"Código público: <a href=\"{_REPO}\">repositório do site no GitHub</a>.",
                  "Sem cookies nem rastreadores: medição de audiência sem cookies.",
                  "Sem conta nem dados pessoais pedidos: os cálculos do simulador são feitos no navegador.",
                  "Cinco línguas: francês, inglês, alemão, luxemburguês e português."),
        "s4": "4. Contacto",
        "btn": "Escrever para pedir uma demonstração (em francês)",
        "s5": "5. ",
    },
}
# mots interdits sur la page d'offre (aucun prix, aucun « audit », jamais « conseiller en énergie »)
OFFER_FORBIDDEN = {
    "fr": ("€", "prix", "tarif", "devis", "conseiller en énergie", "audit"),
    "en": ("€", "price", "pricing", "quote", "energy advisor", "energy consultant", "audit"),
    "de": ("€", "preis", "tarif", "angebot", "kostenvoranschlag", "energieberater", "audit"),
    "lb": ("€", "präis", "tarif", "devis", "energieberoder", "energieberater", "audit"),
    "pt": ("€", "preço", "tarifário", "orçamento", "consultor de energia", "auditoria"),
}


def check_offer(html, lang):
    """Échoue (SystemExit) si la page « Pour les communes » cite un prix, un devis, un audit ou un
    « conseiller en énergie », dans le contenu principal (<main>)."""
    main = html[html.index("<main"):html.index("</main>")]
    text = re.sub(r"<[^>]+>", " ", main).lower()
    hits = [w for w in OFFER_FORBIDDEN[lang] if w in text]
    if hits:
        raise SystemExit(f"{lang} : mots interdits sur la page « pour les communes » : {hits}")


def _n(x, lang):
    s = format(int(x), ",")
    return s if lang == "en" else s.replace(",", "\u202f" if lang == "pt" else " ")


_KB_FMT = {
    "fr": lambda t, first: f"{t['taux']} % ({'plafond ' if first else ''}{_n(t['plafond'], 'fr')} €/kWc)",
    "en": lambda t, first: f"{t['taux']}% ({'cap ' if first else ''}€{_n(t['plafond'], 'en')}/kWp)",
    "de": lambda t, first: f"{t['taux']} % ({'max. ' if first else ''}{_n(t['plafond'], 'de')} €/kWp)",
    "lb": lambda t, first: f"{t['taux']} % ({'Plafong ' if first else ''}{_n(t['plafond'], 'lb')} €/kWp)",
    "pt": lambda t, first: f"{t['taux']} % ({'máx. ' if first else ''}{_n(t['plafond'], 'pt')} €/kWp)",
}


def _kb_aid(lang, below, above):
    """(sous la 1re tranche, une cellule par tranche du barème, au-delà de la dernière)."""
    return (below, *[_KB_FMT[lang](t, i == 0) for i, t in enumerate(_KBG["tranches"])], above)


def de_k(k):
    """« de » élidé devant voyelle : canton d'Esch, canton d'Echternach, canton de Wiltz."""
    return ("d'" if (unicodedata.normalize("NFD", k)[:1] or "x").lower() in "aeiouy" else "de ") + k


def slug(name):
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def esc(s):
    return html_mod.escape(str(s), quote=True)


# ──────────────── textes ──────────────────────────────────────────────────
def _q_pt(label):
    """Relevé trimestriel dans la prose portugaise : « 2025 T1 » (libellé-donnée) → « T1 2025 »,
    comme __FIRSTQ__ du tableau de bord ; un autre libellé (relevé hebdomadaire) est rendu tel quel."""
    return re.sub(r"^(\d{4}) T(\d)$", r"T\2 \1", label)


def _ord(r, lang):
    if lang == "fr":
        return "1er" if r == 1 else f"{r}e"
    if lang == "pt":
        return f"{r}.º"
    if lang == "en":
        suf = "th" if 10 <= r % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(r % 10, "th")
        return f"{r}{suf}"
    return f"{r}."


S = {
    "fr": {
        "rank": lambda r, n: f"{_ord(r, 'fr')} sur {n}",
        "title": lambda c, n, mw, y: f"Photovoltaïque à {c} : {n} installations, {mw} MW ({y})",
        "desc": lambda c, k, mw, date, n, wpc: (f"{c} (canton {de_k(k)}) : {mw} MW de photovoltaïque raccordés au {date}, "
                                                f"{n} installations, {wpc} W par habitant. Tailles des installations, "
                                                f"tranches du Klimabonus Gemengen et comparaison avec les communes voisines."),
        "eyebrow": lambda k: f"Commune · canton {de_k(k)}",
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
        "kb_aid": _kb_aid("fr", "pas d'aide communale (Klimabonus des particuliers : logements seulement)", "au cas par cas"),
        "kb_note": (f"Barème {_KBG_YEAR} du Klimabonus Gemengen (guide pratique, révisé chaque année) ; une ombrière de "
                    f"parking est aidée à {_OMB['taux']} % ({_n(_OMB['plafond'], 'fr')} €/kWc). Les données Leneda ne disent pas si une installation "
                    "appartient à la commune ou à un particulier."),
        "cmp_h": "Comparaison", "cmp_canton": lambda k: f"Communes du canton {de_k(k)}",
        "cmp_size": "Communes de taille comparable",
        "cmp_cols": ("Commune", "Canton", "PV (MW)", "Install.", "W/hab.", "Inst./1 000 hab.", "Ajouts (kW)"),
        "cmp_lede": lambda fq: f"Classées par W par habitant. « Ajouts » : puissance ajoutée depuis le relevé {fq}.",
        "links_h": "Aller plus loin",
        "l_dash": "Graphique interactif de la commune", "l_sim": "Simulateur : est-ce rentable sur votre toit ?",
        "l_for": "Pour les communes : ce que montre cette page", "l_csv": "Tailles des installations, {N} communes (CSV)",
        "prev": "Commune précédente", "next": "Commune suivante", "all": "Toutes les communes",
        "foot": lambda date: (
            f"Données : jeu « La production d'énergie électrique au Luxembourg » publié par Leneda sur "
            f"data.public.lu (CC0), relevé du {date} ; population : RNPP (CC0). Chiffres de puissance raccordée "
            f"(kW), pas d'énergie produite. Données dérivées sous licence CC BY 4.0."),
        "privacy": ("Mesure d'audience sans cookie : Cloudflare Web Analytics et des compteurs de clics anonymes "
                    "(aucune adresse IP ni identifiant enregistrés)."),
        "crumb_home": "Le photovoltaïque au Luxembourg",
    },
    "en": {
        "rank": lambda r, n: f"{_ord(r, 'en')} of {n}",
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
        "kb_aid": _kb_aid("en", "no municipal aid (household Klimabonus: housing only)", "case by case"),
        "kb_note": (f"{_KBG_YEAR} Klimabonus Gemengen scale (practical guide, revised every year); a car-park canopy gets "
                    f"{_OMB['taux']}% (€{_n(_OMB['plafond'], 'en')}/kWp). The Leneda data do not say whether an installation is municipal or private."),
        "cmp_h": "Comparison", "cmp_canton": lambda k: f"Municipalities in the canton of {k}",
        "cmp_size": "Municipalities of similar size",
        "cmp_cols": ("Municipality", "Canton", "PV (MW)", "Inst.", "W/inh.", "Inst./1,000 inh.", "Added (kW)"),
        "cmp_lede": lambda fq: f"Ranked by W per inhabitant. “Added”: capacity added since the {fq} reading.",
        "links_h": "Go further",
        "l_dash": "Interactive chart for this municipality", "l_sim": "Calculator: is solar worth it on your roof?",
        "l_for": "For municipalities: what this page shows", "l_csv": "Installation sizes, all {N} municipalities (CSV)",
        "prev": "Previous municipality", "next": "Next municipality", "all": "All municipalities",
        "foot": lambda date: (
            f"Data: “La production d'énergie électrique au Luxembourg” published by Leneda on data.public.lu (CC0), "
            f"reading of {date}; population: RNPP (CC0). Connected capacity (kW), not energy produced. Derived "
            f"data under CC BY 4.0."),
        "privacy": ("Cookie-free audience measurement: Cloudflare Web Analytics and anonymous click counters "
                    "(no IP address or identifier stored)."),
        "crumb_home": "Solar PV in Luxembourg",
    },
    "de": {
        "rank": lambda r, n: f"Platz {r} von {n}",
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
        "kb_aid": _kb_aid("de", "keine Gemeindeförderung (Klimabonus für Privathaushalte: nur Wohnungen)", "im Einzelfall"),
        "kb_note": (f"Klimabonus Gemengen, Stand {_KBG_YEAR} (Praxisleitfaden, jährlich angepasst); eine "
                    f"Parkplatzüberdachung wird mit {_OMB['taux']} % gefördert ({_n(_OMB['plafond'], 'de')} €/kWp). Die Leneda-Daten sagen nicht, ob "
                    "eine Anlage der Gemeinde oder Privatleuten gehört."),
        "cmp_h": "Vergleich", "cmp_canton": lambda k: f"Gemeinden im Kanton {k}",
        "cmp_size": "Gemeinden ähnlicher Größe",
        "cmp_cols": ("Gemeinde", "Kanton", "PV (MW)", "Anl.", "W/Einw.", "Anl./1 000 Einw.", "Zubau (kW)"),
        "cmp_lede": lambda fq: f"Sortiert nach W pro Einwohner. „Zubau“: seit der Erhebung {fq} hinzugekommene Leistung.",
        "links_h": "Weiter",
        "l_dash": "Interaktive Grafik der Gemeinde", "l_sim": "Rechner: lohnt sich Solar auf Ihrem Dach?",
        "l_for": "Für Gemeinden: was diese Seite zeigt", "l_csv": "Anlagengrößen, alle {N} Gemeinden (CSV)",
        "prev": "Vorherige Gemeinde", "next": "Nächste Gemeinde", "all": "Alle Gemeinden",
        "foot": lambda date: (
            f"Daten: „La production d'énergie électrique au Luxembourg“, veröffentlicht von Leneda auf "
            f"data.public.lu (CC0), Erhebung vom {date}; Bevölkerung: RNPP (CC0). Angeschlossene Leistung (kW), "
            f"nicht erzeugte Energie. Abgeleitete Daten unter CC BY 4.0."),
        "privacy": ("Reichweitenmessung ohne Cookies: Cloudflare Web Analytics und anonyme Klickzähler "
                    "(keine IP-Adresse, keine Kennung gespeichert)."),
        "crumb_home": "Photovoltaik in Luxemburg",
    },
    "lb": {
        "rank": lambda r, n: f"Plaz {r} vun {n}",
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
        "kb_aid": _kb_aid("lb", "keng Gemengenhëllef (Klimabonus fir Privatleit: just Wunnengen)", "vu Fall zu Fall"),
        "kb_note": (f"Bareem {_KBG_YEAR} vum Klimabonus Gemengen (praktesche Guide, all Joer iwwerschafft); e "
                    f"Parkplazendaach kritt {_OMB['taux']} % ({_n(_OMB['plafond'], 'lb')} €/kWp). D'Leneda-Donnéeë soen net, ob eng Installatioun der "
                    "Gemeng oder engem Privatmann gehéiert."),
        "cmp_h": "Verglach", "cmp_canton": lambda k: f"Gemengen am Kanton {k}",
        "cmp_size": "Gemenge vun änlecher Gréisst",
        "cmp_cols": ("Gemeng", "Kanton", "PV (MW)", "Inst.", "W/Aw.", "Inst./1 000 Aw.", "Zouwuess (kW)"),
        "cmp_lede": lambda fq: f"Sortéiert no W pro Awunner. „Zouwuess“: Leeschtung derbäi zënter dem Relevé {fq}.",
        "links_h": "Weider",
        "l_dash": "Interaktiv Grafik vun der Gemeng", "l_sim": "Rechner: rentéiert Solar op Ärem Daach?",
        "l_for": "Fir Gemengen: wat dës Säit weist", "l_csv": "Gréisste vun den Installatiounen, {N} Gemengen (CSV)",
        "prev": "Gemeng virdrun", "next": "Nächst Gemeng", "all": "All Gemengen",
        "foot": lambda date: (
            f"Donnéeën: „La production d'énergie électrique au Luxembourg“, publizéiert vu Leneda op "
            f"data.public.lu (CC0), Relevé vum {date}; Populatioun: RNPP (CC0). Ugeschloss Leeschtung (kW), "
            f"net produzéiert Energie. Ofgeleet Donnéeën ënner CC BY 4.0."),
        "privacy": ("Moossung ouni Cookien: Cloudflare Web Analytics an anonym Klickzieler "
                    "(keng IP-Adress, keen Identifiant gespäichert)."),
        "crumb_home": "Photovoltaik zu Lëtzebuerg",
    },
    "pt": {
        "rank": lambda r, n: f"{_ord(r, 'pt')} de {n}",
        "title": lambda c, n, mw, y: f"Energia fotovoltaica em {c}: {n} instalações, {mw} MW ({y})",
        "desc": lambda c, k, mw, date, n, wpc: (f"{c} (cantão de {k}): {mw} MW de fotovoltaico ligados à rede em {date}, "
                                                f"{n} instalações, {wpc} W por habitante. Dimensões das instalações, "
                                                f"escalões do Klimabonus Gemengen e comparação com os municípios vizinhos."),
        "eyebrow": lambda k: f"Município · cantão de {k}",
        "h1": lambda c: f"A energia fotovoltaica em <span class=\"sun\">{c}</span>",
        "stand": lambda c, mw, date, n, wpc, med, gkw, gp, fq: (
            f"<strong>{mw} MW</strong> de fotovoltaico ligados à rede em {date}, repartidos por <strong>{n} "
            f"instalações</strong>, ou seja, {wpc} W por habitante (mediana dos municípios: {med} W). Desde o "
            f"levantamento do {_q_pt(fq)}: <strong>{gkw} kW</strong> ({gp} %)."),
        "k_pv": "Potência fotovoltaica", "k_pv_sub": lambda n: f"{n} instalações",
        "k_share": "Parte do fotovoltaico", "k_share_sub": lambda t: f"da potência descentralizada ({t} MW, todas as tecnologias)",
        "k_wpc": "W por habitante", "k_ipk": "Instalações / 1\u202f000 hab.",
        "k_ipk_sub": lambda rk, r: f"{rk} · telhados de 30 kW ou menos: {r} / 1\u202f000",
        "k_g": lambda fq: f"Acréscimos desde o {_q_pt(fq)}", "k_hist": lambda d: f"Desde {d}",
        "k_hist_val": lambda dn: f"{dn} inst.", "k_hist_sub": lambda dmw: f"{dmw} MW · acompanhamento semanal",
        "k_pop": "População", "k_pop_sub": "habitantes (RNPP)",
        "med": lambda m: f"mediana {m}",
        "sizes_h": "Dimensões das instalações",
        "sizes_lede": lambda c, sn, sc: (f"Em {c}, <strong>{sn} % das instalações têm 30 kW ou menos</strong> "
                                         f"(sobretudo telhados), para <strong>{sc} % da potência</strong>."),
        "k_cnt": "parte das instalações", "k_cap": "parte da potência", "inst": "inst.",
        "hist_note": lambda d: f"Entre parênteses: variação líquida desde {d}.",
        "kb_h": "Segundo os escalões das ajudas aos municípios",
        "kb_cols": ("Escalão", "Instalações", "Potência", "Ajuda para uma central municipal"),
        "kb_aid": _kb_aid("pt", "sem ajuda municipal (Klimabonus dos particulares: só habitações)", "caso a caso"),
        "kb_note": (f"Tabela de {_KBG_YEAR} do Klimabonus Gemengen (guia prático, revisto todos os anos); uma cobertura "
                    f"de parque de estacionamento recebe {_OMB['taux']} % ({_n(_OMB['plafond'], 'pt')} €/kWp). Os dados da "
                    "Leneda não dizem se uma instalação pertence ao município ou a um particular."),
        "cmp_h": "Comparação", "cmp_canton": lambda k: f"Municípios do cantão de {k}",
        "cmp_size": "Municípios de dimensão comparável",
        "cmp_cols": ("Município", "Cantão", "PV (MW)", "Inst.", "W/hab.", "Inst./1\u202f000 hab.", "Acréscimos (kW)"),
        "cmp_lede": lambda fq: (f"Ordenados por W por habitante. «Acréscimos»: potência acrescentada desde o "
                                f"levantamento do {_q_pt(fq)}."),
        "links_h": "Saber mais",
        "l_dash": "Gráfico interativo do município", "l_sim": "Simulador: o solar compensa no seu telhado?",
        "l_for": "Para os municípios: o que esta página mostra", "l_csv": "Dimensões das instalações, {N} municípios (CSV)",
        "prev": "Município anterior", "next": "Município seguinte", "all": "Todos os municípios",
        "foot": lambda date: (
            f"Dados: conjunto de dados sobre a produção de energia elétrica no Luxemburgo, publicado pela Leneda no "
            f"portal data.public.lu (CC0), levantamento de {date}; população: RNPP (CC0). Números de potência ligada "
            f"à rede (kW), não de energia produzida. Dados derivados sob a licença CC BY 4.0."),
        "privacy": ("Medição de audiência sem cookies: Cloudflare Web Analytics e contadores de cliques anónimos "
                    "(nenhum endereço IP nem identificador registado)."),
        "crumb_home": "A energia fotovoltaica no Luxemburgo",
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
        "list_h": "Les {N} communes",
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
        "list_h": "All {N} municipalities",
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
        "list_h": "Alle {N} Gemeinden",
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
        "list_h": "All {N} Gemengen",
    },
    "pt": {
        "title": "Para os municípios: os seus dados fotovoltaicos, prontos a apresentar",
        "desc": ("Uma página por município, atualizada todas as semanas: potência ligada à rede, dimensões das "
                 "instalações, escalões do Klimabonus Gemengen, evolução e comparação com os municípios vizinhos."),
        "eyebrow": "Para os municípios",
        "h1": "Os seus dados fotovoltaicos, <span class=\"sun\">prontos a apresentar</span>",
        "paras": [
            "Cada município tem a sua página, atualizada todas as segundas-feiras a partir dos dados abertos da Leneda: "
            "potência ligada à rede, número de instalações, parte do solar, watts por habitante, dimensões das "
            "instalações e comparação com os municípios do cantão e com os municípios de dimensão comparável.",
            "As dimensões são também apresentadas segundo os escalões do <strong>Klimabonus Gemengen</strong> (30, 200 e "
            "500 kWp, 5 MWp): vê-se num relance o que cabe nas ajudas aos municípios e o que cabe no Klimabonus dos "
            "particulares.",
            "A Leneda substitui todas as semanas o seu ficheiro «uma linha por instalação», sem guardar histórico. "
            "Desde 14 de setembro de 2026, é arquivada aqui uma cópia todas as semanas: cada página municipal mostra "
            "a evolução desde essa data.",
            "Todos os números podem ser descarregados em CSV, sob a licença CC BY 4.0, para as suas próprias análises "
            "ou para uma apresentação no conselho municipal.",
        ],
        "limits_h": "O que estes dados não dizem",
        "limits": ("Descrevem a potência ligada à rede (kW), não a energia produzida (kWh), e não distinguem as "
                   "instalações municipais das instalações privadas. O acompanhamento dos seus próprios edifícios exige "
                   "os seus próprios dados."),
        "contact_h": "Uma pergunta, uma necessidade para o seu município?",
        "contact": ("Escreva para <a href=\"mailto:hello@sitraka.lu?subject=Munic%C3%ADpio%3A%20solaire.sitraka.lu\">"
                    "hello@sitraka.lu</a>, indicando o seu município."),
        "list_h": "Os {N} municípios",
    },
}

EXTRA_CSS = """
  .kpis.k6{grid-template-columns:repeat(3,minmax(0,1fr))}
  table.cmp{border-collapse:collapse;width:100%;font-size:13.5px;font-variant-numeric:tabular-nums}
  table.cmp th,table.cmp td{padding:7px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
  table.cmp th:nth-child(2),table.cmp td:nth-child(2),table.cmp .col-canton{text-align:left}
  table.cmp thead th{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);font-weight:600;background:none;position:static;cursor:default}
  table.cmp tr.me td{background:var(--amber-soft);font-weight:600}
  table.cmp a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
  table.cmp a:hover{color:var(--amber-text);border-color:var(--amber)}
  .tw{overflow-x:auto}
  /* lot 2 : tableaux de comparaison (rang, commune collante, W/hab. en 2e colonne de données) */
  table.cmp tbody th{text-align:left;font-weight:500;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
  table.cmp tr.me th{background:var(--amber-soft);font-weight:650}
  table.cmp .rk{font-family:var(--mono);font-size:12px;color:var(--ink-3);text-align:right;width:28px;min-width:28px;padding-left:4px;padding-right:8px}
  table.cmp .rk,table.cmp tbody th,table.cmp thead th:nth-child(2){position:sticky;background:var(--paper);z-index:1}
  table.cmp .rk{left:0}
  table.cmp tbody th,table.cmp thead th:nth-child(2){left:40px;text-align:left}
  @media(max-width:767px){table.cmp tbody th,table.cmp thead th:nth-child(2){box-shadow:inset -1px 0 0 var(--line)}}
  table.cmp tr.me .rk,table.cmp tr.me th{background:var(--amber-soft)}
  table.cmp th.wpc,table.cmp td.wpc{font-weight:650;color:var(--ink)}
  @media(max-width:519px){table.cmp.in-canton .col-canton{display:none}}
  .simlink{margin:14px 0 0;font:600 14.5px var(--body)}
  .simlink a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--accent);text-decoration-thickness:2px;text-underline-offset:4px}
  .simlink a:hover{color:var(--amber-text)}
  .simlink span{color:var(--amber-text);white-space:nowrap}
  #comparaison .tblscroll+.tblscroll{margin-top:22px}
  #comparaison caption{font-size:14px;color:var(--ink)}
  details.note{margin-top:12px;font-size:13px}
  details.note summary{font:600 13px var(--body);color:var(--amber-text)}
  details.note .kbnote2{margin-top:4px}
  /* marque blanche (L2.16) : UNE variable d'accent pour les filets et les soulignements ; le texte garde --amber-text (AA) */
  :root{--accent:var(--amber)}
  .eyebrow::before{background:var(--accent)}
  .links a,.contact-cta a{border-left-color:var(--accent)}
  .links a:hover,table.cmp a:hover,table.bigtab a:hover{border-color:var(--accent)}
  .masthead{border-top-color:var(--accent)}
  .crumbs a:hover,.series a:hover{text-decoration-color:var(--accent)}
  /* page « Pour les communes » (page d'offre) */
  .offer section{margin-top:48px}
  .offer h2{margin:0 0 14px}
  .demo-grid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:24px 28px;align-items:start}
  .demo{border:1px solid var(--line);border-top:3px solid var(--accent);background:var(--card);padding:16px 18px 18px}
  .demo-h{margin:0;font:600 10.5px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--ink-3)}
  .demo-name{margin:4px 0 12px;font:700 22px/1.2 var(--display)}
  .demo-name .sun{color:var(--amber-h1)}
  .demo .kpis{margin-top:0}
  .demo .kpi{padding:14px 14px 12px}
  .demo .kpi .val{font-size:26px}
  .demo-open{margin:12px 0 0;font:600 14px var(--body)}
  .demo-open a,.offer .prose a,.trust a{color:var(--amber-text)}
  .tools{list-style:none;margin:6px 0 12px;padding:0;counter-reset:t}
  .tools li{counter-increment:t;display:grid;grid-template-columns:22px 1fr;padding:8px 0;border-top:1px solid var(--line);font-size:14px;color:var(--ink-2)}
  .tools li::before{content:counter(t) ".";font:600 12px/1.6 var(--mono);color:var(--ink-3)}
  .tools b{color:var(--ink);font-weight:650}
  .demo p.lead{margin:0;font-size:14px;color:var(--ink)}
  table.offer-t{width:100%;font-size:14px}
  table.offer-t th,table.offer-t td{padding:9px 12px 9px 0;text-align:left;vertical-align:top;white-space:normal;border-bottom:1px solid var(--line)}
  table.offer-t thead th{font:600 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-3);background:none;position:static;cursor:default;border-bottom:1px solid var(--ink)}
  table.offer-t tbody th{font-weight:650;width:24%}
  table.offer-t td{font-family:var(--body);font-size:14px;color:var(--ink)}
  table.offer-t td:nth-child(3){color:var(--ink-2);font-size:13px}
  table.offer-t td:last-child{font-family:var(--mono);font-size:12.5px;color:var(--ink-2);width:15%}
  table.offer-t tbody tr:last-child th,table.offer-t tbody tr:last-child td{border-bottom:0}
  .cols3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px 28px;margin-top:24px}
  .cols3 p{margin:0;padding-top:10px;border-top:1px solid var(--ink);font-size:14.5px;color:var(--ink)}
  .trust{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:20px 40px;align-items:start}
  .trust ul{margin:0;padding-left:18px;font-size:15px}
  .trust li{margin:0 0 8px}
  .trust h3{margin:0 0 6px;font:600 16px var(--display)}
  .trust p{margin:0;font-size:15px}
  .offer-cta{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px 28px;align-items:center;padding:16px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}
  .offer-cta p{margin:0}
  .offer-cta .q{font:600 17px var(--display)}
  .offer-cta .alt{font-size:13.5px;color:var(--ink-2)}
  .offer-cta .alt a{color:var(--amber-text)}
  .offer-cta .cta-row{margin:0;grid-column:2;grid-row:1/3}
  @media(max-width:767px){
    .demo-grid,.cols3,.trust{grid-template-columns:minmax(0,1fr)}
    .offer-cta{grid-template-columns:minmax(0,1fr)}
    .offer-cta .cta-row{grid-column:1;grid-row:auto}
    table.offer-t thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
    table.offer-t tr{display:block;padding:10px 0;border-bottom:1px solid var(--line)}
    table.offer-t tbody tr:last-child{border-bottom:0}
    table.offer-t tbody th,table.offer-t td{display:block;width:auto!important;border:0;padding:2px 0}
    table.offer-t tbody th{font-size:15px;padding-bottom:4px}
    table.offer-t td::before{content:attr(data-l) " ";font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink-3)}
  }
  @media print{
    @page{size:A4;margin:14mm}
    .commune-page .simlink,.commune-page .contact-cta,.commune-page .pn,.commune-page #liens,.commune-page #aides,
    .commune-page #grandes-installations,.commune-page .crumbs,.commune-page .co-b,.commune-page .co-series,
    .commune-page details.note{display:none}
    .commune-page table,.commune-page figure,.commune-page .kpis,.commune-page .tblscroll{break-inside:avoid}
    .commune-page .tblscroll{overflow:visible}
    .commune-page{zoom:.68;padding:0}
    .commune-page section{margin-top:14px}
    .commune-page,.commune-page *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .commune-page .kpis.k6{grid-template-columns:repeat(3,minmax(0,1fr))!important}
    .commune-page .kpi.hero,.commune-page .kpi:last-child{grid-column:auto!important}
    .commune-page h1{font-size:30px}
    .commune-page .sec-head,.commune-page .lede{break-after:avoid}
    .commune-page #comparaison{break-before:page}
    .commune-page .colophon{margin-top:16px}
  }
  .links{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin-top:10px}
  .links a{display:block;padding:12px 14px;border:1px solid var(--line);border-left:3px solid var(--amber);background:var(--card);color:var(--ink);text-decoration:none;font-size:14px;font-weight:600}
  .links a:hover{border-color:var(--amber)}
  .pn{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:28px;font-size:14px}
  .pn a{color:var(--amber-text)}
  #aides table.mini td{text-align:right}
  #aides table.mini td.aid{text-align:left;font-family:var(--body);white-space:normal;min-width:150px}
  #aides table.mini{width:100%}
  #aides table.mini th{white-space:nowrap}
  @media(max-width:767px){#aides table.mini thead th{white-space:normal;vertical-align:bottom}}
  .prose a{color:var(--amber-text)}
  .clist div{break-inside:avoid}
  .kbnote2{font-size:13px;color:var(--ink-2);margin:10px 0 0;max-width:90ch}
  .kbnote2 a,.prose a{color:var(--amber-text)}
  .prose p{font-size:15.5px;max-width:70ch;color:var(--ink)}
  .contact-cta+.prose{margin-top:28px}
  .clist{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px 24px;font-size:14px;margin-top:10px}
  .clist h3{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);margin:0 0 4px;padding-bottom:4px;border-bottom:1px solid var(--line)}
  .clist a{display:flex;align-items:center;min-height:28px;color:var(--ink);text-decoration:none;padding:0}.clist a:hover{color:var(--amber-text);text-decoration:underline;text-decoration-color:var(--accent)}
  @media(max-width:767px){.clist{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:850px){.kpis.k6{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""


# ──────────────── rendu ───────────────────────────────────────────────────
def _shell(lang, title, desc, canonical, alternates, style, masthead, body, jsonld, page_class=""):
    if lang != "en":   # « 45 % » ne se coupe pas avant le signe
        body = body.replace(" %", "\u202f%")
    i = body.rindex('<footer class="colophon"')        # le colophon reste hors de <main>
    main, foot = body[:i], body[i:]
    alt = "".join(f'<link rel="alternate" hreflang="{c}" href="{u}">' for c, u in alternates)
    alt += f'<link rel="alternate" hreflang="x-default" href="{dict(alternates)["en"]}">'
    return (f'<!doctype html>\n<html lang="{HTML_LANG.get(lang, lang)}">\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml">\n'
            f'<title>{esc(title)}</title>\n<meta name="description" content="{esc(desc)}">\n'
            f'<link rel="canonical" href="{canonical}">\n<meta property="og:url" content="{canonical}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="Lux-Solaire">\n'
            f'<meta property="og:title" content="{esc(title)}">\n<meta property="og:description" content="{esc(desc)}">\n'
            f'<meta property="og:image" content="https://solaire.sitraka.lu/{ {"fr": "og.png"}.get(lang, f"og.{lang}.png") }">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n{alt}\n'
            f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False).replace("<", chr(92) + "u003c")}</script>\n'
            f"<script defer src=\"https://static.cloudflareinsights.com/beacon.min.js\" "
            f"data-cf-beacon='{{\"token\": \"48047aeb049d4a6ba27a197d274297a7\"}}'></script>\n"
            f"<style>{style}{EXTRA_CSS}</style>\n<a class=\"skip\" href=\"#contenu\">{SKIP[lang]}</a>\n"
            f"<div class=\"wrap {page_class}\">\n{masthead}\n<main id=\"contenu\" tabindex=\"-1\">\n{main}\n</main>\n{foot}\n</div>\n"
            f'<script defer src="/ev.js"></script>\n</html>\n')


def _colophon(h, common, paras):
    """Colophon commun : titre et bloc commun repris du tableau de bord rendu (donc traduits), colonne
    « données et licences » propre à la page."""
    return (f'<footer class="colophon" aria-labelledby="colophon-h">{h}<div class="co-a">'
            + "".join(f"<p>{p}</p>" for p in paras) + f'</div>{common}</footer>')


def write_all(root, site, blobs, cdate, thousands, dec1_raw, person, luxembourg, flags, jsround=round):
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
                       re.search(r"<!--MASTHEAD-->.*?<!--/MASTHEAD-->", src, re.S).group(0),
                       re.search(r'<h2 id="colophon-h">.*?</h2>', src, re.S).group(0),
                       re.search(r"<!--COLOPHON_COMMON-->.*?<!--/COLOPHON_COMMON-->", src, re.S).group(0))

    def masthead(lang, paths):   # bandeau du tableau de bord rendu, sélecteur pointant vers CETTE page
        return re.sub(r'<ul class="langs".*?</ul>', lambda m: ossature.lang_nav(paths, lang, flags),
                      pages[lang][1], count=1, flags=re.S)
    groups = []
    demo = {}   # (langue, slug) → (canton, commune, KPI) : extrait réel repris par « Pour les communes »

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
            sg = lambda x: ("+" if x > 0 else "−" if x < 0 else "±") + T(abs(jsround(x)), lang)  # noqa: E731
            gkw = sg(c["g"])
            gp = ("+" if c["gp"] > 0 else "") + T(jsround(c["gp"]), lang) if c["gp"] is not None else "n.d."
            cn, kn = esc(c["c"]), esc(c["k"])   # noms insérés dans le HTML : échappés (title/desc le sont dans _shell)
            title = L["title"](c["c"], nn, mw, meta["date_iso"][:4])
            desc = L["desc"](c["c"], c["k"], mw, date, nn, wpc)
            # tailles détaillées (blob traduit pour les libellés de classes)
            rows = [(sz["bin"], n, kw / 1000) for sz, (n, kw) in zip(d["sizes"], base["sizes_c"][str(c["lau2"])])]
            nt = sum(r[1] for r in rows) or 1
            ct = sum(r[2] for r in rows) or 1
            h = (base.get("hist") or {}).get("c", {}).get(str(c["lau2"])) if base.get("hist") else None
            hd = h[2] if h else None
            unit = lambda b: "" if "MW" in b else " kW"  # noqa: E731
            pct = lambda x: (dec1(x, lang) if x < 1 else T(jsround(x), lang))  # noqa: E731

            def capl(x):
                return f"{T(jsround(x * 1000), lang)} kW" if 0 < x < 1 else f"{dec1(x, lang)} MW"
            bars = "".join(
                f'<div class="bin">{b}{unit(b)}</div><div class="duo">'
                f'<div class="b cnt{" in" if n / nt * 100 > 70 else ""}" style="width:{max(n / nt * 100, 0.4):.2f}%">'
                f'<i>{pct(n / nt * 100)} % · {T(n, lang)} {L["inst"]}'
                f'{f" <em>({sg(hd[j])})</em>" if hd and hd[j] else ""}</i></div>'
                f'<div class="b cap{" in" if kw / ct * 100 > 70 else ""}" style="width:{max(kw / ct * 100, 0.4):.2f}%">'
                f'<i>{pct(kw / ct * 100)} % · {capl(kw)}</i></div></div>'
                for j, (b, n, kw) in enumerate(rows))
            sn = jsround(sum(r[1] for r in rows[:SMALL_BINS]) / nt * 100)
            sc = jsround(sum(r[2] for r in rows[:SMALL_BINS]) / ct * 100)
            kb_rows = "".join(
                f'<tr><th scope="row">{b}{unit(b)}</th><td class="aid">{L["kb_aid"][baremes.kb_labels().index(fb)]}</td>'
                f'<td>{T(n, lang)}</td><td>{capl(kw / 1000)}</td></tr>'
                for b, fb, (n, kw) in zip(d["kb"]["bins"], base["kb"]["bins"], base["kb"]["c"][str(c["lau2"])]))
            # comparaison
            me = ' class="me"'
            kc = L["kb_cols"]   # Tranche, Installations, Puissance, Aide : l'aide passe en 2e colonne (L2.11)
            kb_head = "".join(f'<th scope="col">{x}</th>' for x in (kc[0], kc[3], kc[1], kc[2]))
            TL = TAB_LABEL[lang]

            def cmp_table(lst, num, cap, cls):
                # N°, Commune, W/hab. (critère de tri), puis les autres colonnes, Canton en dernier (L2.9)
                cc = L["cmp_cols"]   # Commune, Canton, PV (MW), Install., W/hab., Inst./1 000 hab., Ajouts (kW)
                hd_ = (f'<th scope="col" class="rk">{L2[lang]["rankcol"]}</th><th scope="col">{cc[0]}</th>'
                       f'<th scope="col" class="wpc">{cc[4]}</th><th scope="col">{cc[2]}</th><th scope="col">{cc[3]}</th>'
                       f'<th scope="col">{cc[5]}</th><th scope="col">{cc[6]}</th><th scope="col" class="col-canton">{cc[1]}</th>')
                body = "".join(
                    f'<tr{me if o["lau2"] == c["lau2"] else ""}><td class="rk">{r}</td>'
                    f'<th scope="row"><a href="{CPATH[lang]}{slug(o["c"])}/">{esc(o["c"])}</a></th>'
                    f'<td class="wpc">{T(o["wpc"], lang)}</td><td>{dec1(o["pv"] / 1000, lang)}</td><td>{T(o["n"], lang)}</td>'
                    f'<td>{dec1(o["ipk"], lang)}</td><td>{sg(o["g"])}</td><td class="col-canton">{esc(o["k"])}</td></tr>'
                    for r, o in enumerate(sorted(lst, key=lambda o: -o["wpc"]), 1))
                cid = f"cmp-{num}"
                return (f'<div class="tblscroll on-paper" role="region" tabindex="0" aria-labelledby="{cid}">'
                        f'<table class="cmp booktabs {cls}"><caption id="{cid}"><span class="capin"><b>{TL} {num}.</b> {cap}</span></caption>'
                        f'<thead><tr>{hd_}</tr></thead><tbody>{body}</tbody></table></div>')
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
                f'<div class="sub">{L["rank"](rank["wpc"][c["lau2"]], n_all)} · {L["med"](med)}</div></div>'
                f'<div class="kpi"><div class="lbl">{L["k_ipk"]}</div><div class="val">{dec1(c["ipk"], lang)}</div>'
                f'<div class="sub">{L["k_ipk_sub"](L["rank"](rank["ipk"][c["lau2"]], n_all), dec1(c["rpk"], lang))}</div></div>'
                f'<div class="kpi"><div class="lbl">{L["k_g"](fq)}</div><div class="val">{gkw} kW</div>'
                f'<div class="sub">{L["rank"](rank["g"][c["lau2"]], n_all)} · {gp} %</div></div>'
                f'<div class="kpi"><div class="lbl">{k6[0]}</div><div class="val">{k6[1]}</div>'
                f'<div class="sub">{k6[2]}</div></div>')
            hist_note = f'<p class="kbnote2">{L["hist_note"](d["hist"]["date"])}</p>' if h else ""
            prev_c, next_c = communes[i - 1], communes[(i + 1) % n_all]
            colon = ":" if lang == "pt" else " :"   # portugais : pas d'espace avant les deux-points
            X, FL = L2[lang], FIG_LABEL[lang]
            demo[(lang, s)] = (kn, cn, kpis)
            simq = (f'<p class="simlink"><a href="{SIM[lang]}?canton={urllib.parse.quote(c["k"])}">{X["simq"](cn)} '
                    f'<span>{X["sim_word"]} <span aria-hidden="true">→</span></span></a></p>')
            # ordre : figure 1 (tailles), tableau 1 (tranches), tableaux 2 et 3 (comparaisons), puis le
            # tableau 4 des grandes installations, présent sur une partie des communes seulement : les
            # numéros 1 à 3 sont ainsi les mêmes sur toutes les pages
            body = (
                f'<header>{ossature.crumbs([(L["crumb_home"], HOME[lang]), (L["all"], FORPATH[lang]), (cn, None)], lang)}'
                f'<div class="eyebrow">{L["eyebrow"](kn)}</div><h1>{L["h1"](cn)}</h1>'
                f'<p class="standfirst">{L["stand"](cn, mw, date, nn, wpc, med, gkw, gp, fq)}</p></header>'
                f'<div class="kpis k6">{kpis}</div>{simq}{CONTACT[lang]}'
                f'<section id="tailles"><div class="sec-head"><h2>{L["sizes_h"]}</h2></div>'
                f'<p class="lede">{L["sizes_lede"](cn, sn, sc)}</p><figure class="card">'
                f'<div class="pkey"><span><span class="sw" style="background:var(--amber);display:inline-block;vertical-align:-1px"></span> {L["k_cnt"]}</span>'
                f'<span><span class="sw" style="background:var(--ink);opacity:.82;display:inline-block;vertical-align:-1px"></span> {L["k_cap"]}</span></div>'
                f'<div class="pair">{bars}</div>{hist_note}'
                f'<figcaption><b>{FL} 1.</b> {X["fig1"](cn)}</figcaption><p class="src">{X["src_inst"](date)}</p></figure></section>'
                f'<section id="aides"><div class="sec-head"><h2>{L["kb_h"]}</h2></div><div class="card">'
                f'<div class="tblscroll" role="region" tabindex="0" aria-labelledby="kb-cap"><table class="mini booktabs">'
                f'<caption id="kb-cap"><span class="capin"><b>{TL} 1.</b> {X["t_kb"](cn)}</span></caption>'
                f'<thead><tr>{kb_head}</tr></thead>'
                f'<tbody>{kb_rows}</tbody></table></div><p class="kbnote2">{L["kb_note"]}</p>'
                f'<p class="src">{X["src_kb"](date)}</p></div></section>'
                f'<section id="comparaison"><div class="sec-head"><h2>{L["cmp_h"]}</h2></div>'
                f'<p class="lede">{L["cmp_lede"](fq)}</p>'
                f'{cmp_table(same_k, 2, L["cmp_canton"](kn), "in-canton")}'
                f'{cmp_table(similar, 3, L["cmp_size"], "similar")}'
                f'<p class="src">{X["src_cmp"](date, P["date"])}</p></section>'
                + grandes.commune_section(d.get("bigs"), lang, c["lau2"], cn, HOME[lang], caption=f"<b>{TL} 4.</b>") +
                f'<section id="liens"><div class="sec-head"><h2>{L["links_h"]}</h2></div><div class="links">'
                f'<a href="{HOME[lang]}?commune={s}#paradoxe">{L["l_dash"]}</a>'
                f'<a href="{SIM[lang]}?canton={urllib.parse.quote(c["k"])}">{L["l_sim"]}</a>'
                f'<a href="{FORPATH[lang]}">{L["l_for"]}</a>'
                f'<a href="/data/csv/solaire_communes_tailles.csv">{L["l_csv"].replace("{N}", str(n_all))}</a></div>'
                f'<nav class="pn" aria-label="{L["all"]}"><a href="{CPATH[lang]}{slug(prev_c["c"])}/">← {L["prev"]}{colon} {esc(prev_c["c"])}</a>'
                f'<a href="{CPATH[lang]}{slug(next_c["c"])}/">{L["next"]}{colon} {esc(next_c["c"])} →</a></nav></section>'
                + _colophon(pages[lang][2], pages[lang][3], [
                    L["foot"](date),
                    f'{SRC_LABEL[lang][0]}{" :" if lang == "fr" else ":"} <a href="{SRC_LENEDA}">Leneda (data.public.lu)</a> · '
                    f'<a href="{SRC_RNPP}">RNPP</a> ({SRC_LABEL[lang][1]} {cn}{" :" if lang == "fr" else ":"} {T(c["pop"], lang)} '
                    f'{SRC_LABEL[lang][2]} {P["date"]}) · <a href="{SRC_KBG}">Klimabonus Gemengen</a>',
                    L["privacy"]]))
            canonical = site + CPATH[lang] + s + "/"
            jsonld = {"@context": "https://schema.org", "@type": "WebPage", "@id": canonical, "url": canonical,
                      "name": title, "description": desc, "inLanguage": lang, "dateModified": cdate[lang],
                      "isPartOf": {"@id": site + HOME[lang]}, "author": person,
                      "about": {"@type": "Place", "name": c["c"], "containedInPlace": luxembourg}}
            sb = masthead(lang, [(l, CPATH[l] + s + "/") for l in ORDER])
            out = root / CPATH[lang].strip("/") / s / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            html = _shell(lang, title, desc, canonical, alternates, pages[lang][0], sb, body, jsonld, "commune-page")
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
        clist = "".join(f'<div><h3>{esc(k)}</h3>' + "".join(f'<a href="{CPATH[lang]}{slug(c["c"])}/">{esc(c["c"])}</a>' for c in cs)
                        + "</div>" for k, cs in sorted(by_k.items()))
        # page d'offre (L2.15) : en-tête commun (fil d'Ariane, surtitre, H1, chapô = 1er paragraphe, appel),
        # puis 1. démonstration, 2. composantes, 3. méthode et confiance, 4. contact, 5. index des communes.
        # Les textes existants (paras, limits, contact) sont seulement redistribués.
        X, FL, TL = FOR2[lang], FIG_LABEL[lang], TAB_LABEL[lang]
        dk, dn, dkpis = demo[(lang, DEMO_COMMUNE)]
        dc = next(c for c in base["communes"] if slug(c["c"]) == DEMO_COMMUNE)
        ddate = blobs[lang]["meta"]["date"]
        cta = (f'<p class="cta-row"><a class="cta" href="{_CT[lang]}">{X["btn"]} <span aria-hidden="true">→</span></a></p>')
        th1 = "".join(f'<th scope="col">{x}</th>' for x in X["t1cols"])
        colon = ":" if lang != "fr" else " :"
        tr1 = "".join(f'<tr><th scope="row">{r[0]}</th>' + "".join(f'<td data-l="{esc(h)}{colon}">{x}</td>' for h, x in zip(X["t1cols"][1:], r[1:]))
                      + "</tr>" for r in X["t1rows"])
        tools = "".join(f"<li><span><b>{a}</b> : {b}</span></li>" if lang == "fr" else f"<li><span><b>{a}</b>: {b}</span></li>"
                        for a, b in X["tools"])
        body = (f'<header>{ossature.crumbs([(L["crumb_home"], HOME[lang]), (F["eyebrow"], None)], lang)}'
                f'<div class="eyebrow">{F["eyebrow"]}</div><h1>{F["h1"]}</h1>'
                f'<p class="standfirst">{F["paras"][0]}</p>{cta}</header>'
                f'<div class="offer">'
                f'<section id="demonstration"><h2>{X["s1"]}</h2><div class="demo-grid">'
                f'<figure><div class="demo"><p class="demo-h">{L["eyebrow"](dk)}</p><p class="demo-name">{L["h1"](dn)}</p>'
                f'<div class="kpis k6">{dkpis}</div>'
                f'<p class="demo-open"><a href="{CPATH[lang]}{DEMO_COMMUNE}/">{X["open"]} <span aria-hidden="true">→</span></a></p></div>'
                f'<figcaption><b>{FL} 1.</b> {X["f1cap"](dn)}</figcaption>'
                f'<p class="src">{L2[lang]["src_cmp"](ddate, blobs[lang]["population"]["date"])}</p></figure>'
                f'<figure><div class="demo"><p class="demo-h">{X["f2h"]}</p>'
                f'<p class="lead">{X["f2lead"]}</p><ol class="tools">{tools}</ol>'
                f'<p class="demo-open"><a href="{SIM[lang]}?canton={urllib.parse.quote(dc["k"])}">{X["f2link"](esc(dc["k"]))} '
                f'<span aria-hidden="true">→</span></a></p></div>'
                f'<figcaption><b>{FL} 2.</b> {X["f2cap"]}</figcaption><p class="src">{X["src_sim"]}</p></figure>'
                f'</div></section>'
                f'<section id="composantes"><h2>{X["s2"]}</h2>'
                f'<div class="tblscroll on-paper" role="region" tabindex="0" aria-labelledby="offer-cap"><table class="offer-t booktabs">'
                f'<caption id="offer-cap"><span class="capin"><b>{TL} 1.</b> {X["t1cap"]}</span></caption>'
                f'<thead><tr>{th1}</tr></thead><tbody>{tr1}</tbody></table></div>'
                f'<div class="cols3 prose">{"".join(f"<p>{p}</p>" for p in F["paras"][1:])}</div></section>'
                f'<section id="confiance"><h2>{X["s3"]}</h2><div class="trust">'
                f'<ul>{"".join(f"<li>{t}</li>" for t in X["trust"])}</ul>'
                f'<div><h3>{F["limits_h"]}</h3><p>{F["limits"]}</p></div></div></section>'
                f'<section id="contact"><h2>{X["s4"]}</h2><div class="offer-cta">'
                f'<p class="q">{F["contact_h"]}</p><p class="alt">{F["contact"]}</p>{cta}</div></section>'
                f'</div>'
                f'<section id="liste"><div class="sec-head"><h2>{X["s5"]}{F["list_h"].replace("{N}", str(n_all))}</h2></div><div class="clist">{clist}</div></section>'
                + _colophon(pages[lang][2], pages[lang][3], [L["foot"](blobs[lang]["meta"]["date"]), L["privacy"]]))
        alternates = [(l, site + FORPATH[l]) for l in ORDER]
        canonical = site + FORPATH[lang]
        jsonld = {"@context": "https://schema.org", "@type": "WebPage", "@id": canonical, "url": canonical,
                  "name": F["title"], "description": F["desc"], "inLanguage": lang, "dateModified": cdate[lang],
                  "isPartOf": {"@id": site + HOME[lang]}, "author": person}
        sb = masthead(lang, for_paths)
        out = root / FORPATH[lang].strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        html = _shell(lang, F["title"], F["desc"], canonical, alternates, pages[lang][0], sb, body, jsonld)
        if "—" in html:
            raise SystemExit(f"{lang} : tiret cadratin dans la page pour les communes")
        check_offer(html, lang)
        out.write_text(html)
    groups.append((for_paths, cdate))
    return groups
