"""Grandes installations : lignes de plus de 100 kW apparues ou disparues, d'un relevé archivé au suivant.

Source : les copies hebdomadaires du fichier Leneda « une ligne par installation »
(archive/leneda-not-grouped-AAAA-MM-JJ.csv.gz, depuis le 14/09/2026). Une ligne =
LAU1, Commune, LAU2, Canton, Type d'installation, Puissance installée [kW]. Pas
d'identifiant, pas de date de mise en service, pas d'exploitant : on ne peut PAS
suivre une installation d'un relevé à l'autre. Méthode retenue (dite sur les pages) :
comparaison en MULTI-ENSEMBLE, commune par commune et filière par filière, des lignes
de plus de 100 kW (seuil exclu) de deux relevés archivés consécutifs. Une ligne
« apparue » peut être une installation nouvelle, agrandie au-delà de 100 kW, corrigée
ou rattachée à une autre commune. Deux remarques, factuelles, sont posées :
  - « m » : même filière ET même puissance disparues dans une AUTRE commune au même
    relevé (appariement un pour un) : changement de commune possible ;
  - « r » : une ligne de plus de 100 kW de même filière a disparu (ou est apparue)
    dans la MÊME commune au même relevé : agrandissement ou correction possible.
On n'affirme jamais qu'une installation « a augmenté » : le fichier ne le permet pas.

Textes par langue DANS ce module (comme communes.py), rendus par build.prerender
(tableau de bord, marqueur <!--PRE_BIGNEW-->) et communes.write_all (pages communales).
"""
import html as html_mod
from collections import Counter

import pandas as pd

BIG_KW = 100   # « plus de 100 kW » : strictement supérieur, 100 kW exactement exclu
DASH_MAX = 20    # lignes apparues listées sur le tableau de bord (liste complète : CSV)
TYPE_COL, KW_COL = "Type d'installation", "Puissance installée [kW]"

# noms des filières : mêmes libellés que le mix du tableau de bord (name:'…' de
# i18n_js / i18n_de_js / i18n_lb_js ; égalité vérifiée par tests/test_grandes.py)
TYPE_NAMES = {
    "fr": {"Installation photovoltaïque": "Photovoltaïque", "Eolienne": "Éolien", "Biomasse": "Biomasse",
           "Cogénération": "Cogénération", "Installation hydroélectrique": "Hydroélectrique", "Biogaz": "Biogaz"},
    "en": {"Installation photovoltaïque": "Solar PV", "Eolienne": "Wind", "Biomasse": "Biomass",
           "Cogénération": "Cogeneration", "Installation hydroélectrique": "Hydro", "Biogaz": "Biogas"},
    "de": {"Installation photovoltaïque": "Photovoltaik", "Eolienne": "Windkraft", "Biomasse": "Biomasse",
           "Cogénération": "KWK", "Installation hydroélectrique": "Wasserkraft", "Biogaz": "Biogas"},
    "lb": {"Installation photovoltaïque": "Photovoltaik", "Eolienne": "Wandenergie", "Biomasse": "Biomass",
           "Cogénération": "Cogeneratioun", "Installation hydroélectrique": "Waasserkraaft", "Biogaz": "Biogas"},
    "pt": {"Installation photovoltaïque": "Fotovoltaica", "Eolienne": "Eólica", "Biomasse": "Biomassa",
           "Cogénération": "Cogeração", "Installation hydroélectrique": "Hídrica", "Biogaz": "Biogás"},
}
TYPE_CODE = {"Installation photovoltaïque": "pv", "Eolienne": "wind", "Biomasse": "biomass",
             "Cogénération": "chp", "Installation hydroélectrique": "hydro", "Biogaz": "biogas"}


# ──────────────── détection ───────────────────────────────────────────────
def _big(df, threshold):
    p = pd.to_numeric(df[KW_COL])
    return df[p > threshold].assign(_kw=p[p > threshold].round(3))


def _key(r):
    return (int(r["LAU2"]), r[TYPE_COL], float(r["_kw"]))


def diff_big(old, new, threshold=BIG_KW):
    """Lignes de plus de `threshold` kW apparues (e=+1) et disparues (e=-1) entre deux
    copies du fichier par installation, en multi-ensemble sur (LAU2, filière, kW) :
    deux lignes identiques qui deviennent trois = une ligne apparue. Remarques m / r :
    voir le docstring du module. Renvoie une liste de dicts triée (e décroissant, kW
    décroissant, LAU2)."""
    ob, nb = _big(old, threshold), _big(new, threshold)
    names = {}
    for df in (ob, nb):
        for _, r in df.iterrows():
            names[int(r["LAU2"])] = (str(r["Commune"]), str(r["Canton"]) if "Canton" in df.columns else "")
    co = Counter(_key(r) for _, r in ob.iterrows())
    cn = Counter(_key(r) for _, r in nb.iterrows())
    up, down = cn - co, co - cn
    ev = [{"l": k[0], "t": k[1], "kw": k[2], "e": e, "m": None, "r": 0}
          for e, cnt in ((1, up), (-1, down)) for k in sorted(cnt) for _ in range(cnt[k])]
    # « m » : même filière et même puissance, apparue ici et disparue dans une autre commune
    gone = [x for x in ev if x["e"] == -1]
    for a in (x for x in ev if x["e"] == 1):
        g = next((g for g in gone if g["m"] is None and g["t"] == a["t"] and g["kw"] == a["kw"] and g["l"] != a["l"]), None)
        if g is not None:
            a["m"], g["m"] = g["l"], a["l"]
    # « r » : une ligne de même filière disparue ET une apparue dans la même commune
    sides = {}
    for x in ev:
        if x["m"] is None:
            sides.setdefault((x["l"], x["t"]), set()).add(x["e"])
    for x in ev:
        if x["m"] is None and sides[(x["l"], x["t"])] == {1, -1}:
            x["r"] = 1
    for x in ev:
        x["c"], x["k"] = names[x["l"]]
        if x["m"] is not None:
            x["mc"] = names[x["m"]][0]
    ev.sort(key=lambda x: (-x["e"], -x["kw"], x["l"]))
    return ev


def count_big(df, threshold=BIG_KW):
    """{LAU2: nombre de lignes de plus de `threshold` kW}, toutes filières."""
    b = _big(df, threshold)
    return {int(k): int(v) for k, v in b.groupby("LAU2").size().items()}


def detect(snaps, label, threshold=BIG_KW):
    """`snaps` = [(date, DataFrame)] des copies archivées, dans n'importe quel ordre ;
    `label(date)` = libellé court (« 2 nov. 2026 »). Compare chaque copie à la
    précédente. Renvoie le bloc `bigs` de data.json (None s'il y a moins de deux copies)."""
    snaps = sorted(snaps, key=lambda s: s[0])
    if len(snaps) < 2:
        return None
    ev = []
    for i in range(1, len(snaps)):
        for x in diff_big(snaps[i - 1][1], snaps[i][1], threshold):
            ev.append({"p": i, **x})
    ev.sort(key=lambda x: (-x["p"], -x["e"], -x["kw"], x["l"]))
    first, last = count_big(snaps[0][1], threshold), count_big(snaps[-1][1], threshold)
    return {"kw": threshold,
            "snaps": [{"iso": d.isoformat(), "l": label(d)} for d, _ in snaps],
            "ev": ev,
            "n": {str(k): [last.get(k, 0), first.get(k, 0)] for k in sorted(set(first) | set(last))},
            "nat": [sum(last.values()), sum(first.values())]}


# ──────────────── textes ──────────────────────────────────────────────────
def _plural(n, one, many):
    return one if n in (0, 1) else many


S = {
    "fr": {
        "h": "Grandes installations : lignes apparues",
        "note": "plus de 100 kW, d'un relevé archivé au suivant",
        "dash_lede": lambda n, n0, first, last, a, d, k, al: (
            f"Au relevé du {last}, le fichier Leneda par installation compte <strong>{_int(n, 'fr')} "
            f"{_plural(n, 'installation', 'installations')} de plus de 100 kW</strong>, "
            f"toutes filières ({_int(n0, 'fr')} au {first}). Du {first} au {last}, sur {k} relevés archivés "
            f"comparés chacun au précédent, <strong>{a} "
            f"{_plural(a, 'ligne de plus de 100 kW est apparue', 'lignes de plus de 100 kW sont apparues')}</strong> "
            f"et {d} {_plural(d, 'a disparu', 'ont disparu')}"
            + (f" ({al} des lignes apparues au dernier relevé, celui du {last})" if k > 2 else "") + "."),
        "latest": "Dernières lignes apparues",
        "cols": ("Relevé", "Commune", "Filière", "Puissance (kW)"),
        "ccols": ("Relevé", "Mouvement", "Filière", "Puissance (kW)"),
        "more": lambda n: f"{n} lignes apparues au total ; liste complète, lignes disparues comprises, dans le CSV.",
        "none_dash": lambda first, last: f"Aucune ligne de plus de 100 kW n'est apparue entre le {first} et le {last}.",
        "up": "apparue", "down": "disparue",
        "r_up": "une ligne de plus de 100 kW de même filière a disparu dans la commune au même relevé : agrandissement ou correction possible",
        "r_down": "une ligne de plus de 100 kW de même filière est apparue dans la commune au même relevé",
        "m_up": lambda c: f"même filière et même puissance disparues à {c} au même relevé : changement de commune possible",
        "m_down": lambda c: f"même filière et même puissance apparues à {c} au même relevé",
        "c_lede": lambda c, n, n0, first, last: (
            f"À {c}, le fichier Leneda par installation compte <strong>{n} "
            f"{_plural(n, 'installation', 'installations')} de plus de 100 kW</strong> au relevé du {last}, "
            f"toutes filières ({n0} au {first})."),
        "c_some": "Lignes de plus de 100 kW apparues ou disparues entre deux relevés archivés :",
        "c_none": lambda first, last: (f"Aucune ligne de plus de 100 kW n'est apparue ni n'a disparu dans la commune "
                                       f"entre le {first} et le {last}."),
        "method": lambda lst: (
            "<strong>Méthode.</strong> Leneda publie chaque semaine un fichier d'une ligne par installation : commune, "
            "filière et puissance installée, sans identifiant, sans date de mise en service ni exploitant. Il remplace ce "
            "fichier sans garder d'historique ; lux-solaire en archive une copie à chaque relevé. Faute d'identifiant, on "
            "ne peut pas suivre une installation d'un relevé à l'autre : on compare, commune par commune et filière par "
            "filière, les lignes de plus de 100 kW (100 kW exactement exclus) de deux copies consécutives. Une ligne "
            "apparue peut être une installation nouvelle, mais aussi une installation agrandie au-delà de 100 kW, une "
            "valeur corrigée ou une ligne rattachée à une autre commune ; le fichier ne permet pas de trancher. "
            f"Copies comparées : {lst}."),
        "gap": lambda days: f"{days} jours après la précédente",
        "csv": "Lignes apparues et disparues (CSV)", "nat": "Liste nationale",
        "list_aria": "Lignes de plus de 100 kW apparues",
    },
    "en": {
        "h": "Large installations: rows that appeared",
        "note": "over 100 kW, from one archived reading to the next",
        "dash_lede": lambda n, n0, first, last, a, d, k, al: (
            f"As of the {last} reading, Leneda's per-installation file lists <strong>{_int(n, 'en')} "
            f"{'installation' if n == 1 else 'installations'} over 100 kW</strong>, all "
            f"technologies ({_int(n0, 'en')} on {first}). From {first} to {last}, across {k} archived readings "
            f"each compared with the previous one, <strong>{a} "
            f"{'row' if a == 1 else 'rows'} over 100 kW appeared</strong> and {d} disappeared"
            + (f" ({al} of the rows that appeared came in the latest reading, {last})" if k > 2 else "") + "."),
        "latest": "Latest rows to appear",
        "cols": ("Reading", "Municipality", "Technology", "Capacity (kW)"),
        "ccols": ("Reading", "Change", "Technology", "Capacity (kW)"),
        "more": lambda n: f"{n} rows appeared in total; the full list, including rows that disappeared, is in the CSV.",
        "none_dash": lambda first, last: f"No row over 100 kW appeared between {first} and {last}.",
        "up": "appeared", "down": "disappeared",
        "r_up": "a row over 100 kW of the same technology disappeared in this municipality in the same reading: possibly an extension or a correction",
        "r_down": "a row over 100 kW of the same technology appeared in this municipality in the same reading",
        "m_up": lambda c: f"same technology and same capacity disappeared in {c} in the same reading: possibly a change of municipality",
        "m_down": lambda c: f"same technology and same capacity appeared in {c} in the same reading",
        "c_lede": lambda c, n, n0, first, last: (
            f"In {c}, Leneda's per-installation file lists <strong>{n} "
            f"{'installation' if n == 1 else 'installations'} over 100 kW</strong> as of "
            f"the {last} reading, all technologies ({n0} on {first})."),
        "c_some": "Rows over 100 kW that appeared or disappeared between two archived readings:",
        "c_none": lambda first, last: (f"No row over 100 kW appeared or disappeared in this municipality between "
                                       f"{first} and {last}."),
        "method": lambda lst: (
            "<strong>Method.</strong> Every week Leneda publishes a file with one row per installation: municipality, "
            "technology and installed capacity, with no identifier, no commissioning date and no operator. It replaces "
            "this file without keeping any history; lux-solaire archives a copy at each reading. Without an identifier, "
            "an installation cannot be followed from one reading to the next: rows over 100 kW (exactly 100 kW "
            "excluded) of two consecutive copies are compared municipality by municipality and technology by "
            "technology. A row that appears may be a new installation, but also an installation extended beyond "
            "100 kW, a corrected value or a row assigned to another municipality; the file does not say which. "
            f"Copies compared: {lst}."),
        "gap": lambda days: f"{days} days after the previous one",
        "csv": "Rows that appeared and disappeared (CSV)", "nat": "National list",
        "list_aria": "Rows over 100 kW that appeared",
    },
    "de": {
        "h": "Großanlagen: hinzugekommene Zeilen",
        "note": "über 100 kW, von einer archivierten Erhebung zur nächsten",
        "dash_lede": lambda n, n0, first, last, a, d, k, al: (
            f"In der Erhebung vom {last} verzeichnet die Leneda-Datei je Anlage <strong>{_int(n, 'de')} "
            f"{'Anlage' if n == 1 else 'Anlagen'} über 100 kW</strong>, alle Technologien ({_int(n0, 'de')} am {first}). "
            f"Vom {first} bis zum {last}, über {k} archivierte Erhebungen, jeweils mit der vorigen verglichen, "
            f"{'ist' if a == 1 else 'sind'} <strong>{a} "
            f"{'Zeile' if a == 1 else 'Zeilen'} über 100 kW hinzugekommen</strong> und {d} weggefallen"
            + (f" (davon {al} hinzugekommen in der letzten Erhebung vom {last})" if k > 2 else "") + "."),
        "latest": "Zuletzt hinzugekommene Zeilen",
        "cols": ("Erhebung", "Gemeinde", "Technologie", "Leistung (kW)"),
        "ccols": ("Erhebung", "Änderung", "Technologie", "Leistung (kW)"),
        "more": lambda n: f"Insgesamt {n} hinzugekommene Zeilen; die vollständige Liste, weggefallene Zeilen inbegriffen, steht in der CSV-Datei.",
        "none_dash": lambda first, last: f"Zwischen dem {first} und dem {last} ist keine Zeile über 100 kW hinzugekommen.",
        "up": "hinzugekommen", "down": "weggefallen",
        "r_up": "in derselben Erhebung ist in der Gemeinde eine Zeile über 100 kW derselben Technologie weggefallen: Erweiterung oder Korrektur möglich",
        "r_down": "in derselben Erhebung ist in der Gemeinde eine Zeile über 100 kW derselben Technologie hinzugekommen",
        "m_up": lambda c: f"gleiche Technologie und gleiche Leistung in derselben Erhebung in {c} weggefallen: Wechsel der Gemeinde möglich",
        "m_down": lambda c: f"gleiche Technologie und gleiche Leistung in derselben Erhebung in {c} hinzugekommen",
        "c_lede": lambda c, n, n0, first, last: (
            f"In {c} verzeichnet die Leneda-Datei je Anlage <strong>{n} "
            f"{'Anlage' if n == 1 else 'Anlagen'} über 100 kW</strong> (Erhebung vom {last}), alle Technologien "
            f"({n0} am {first})."),
        "c_some": "Zeilen über 100 kW, die zwischen zwei archivierten Erhebungen hinzugekommen oder weggefallen sind:",
        "c_none": lambda first, last: (f"Zwischen dem {first} und dem {last} ist in der Gemeinde keine Zeile über "
                                       f"100 kW hinzugekommen oder weggefallen."),
        "method": lambda lst: (
            "<strong>Methode.</strong> Leneda veröffentlicht jede Woche eine Datei mit einer Zeile je Anlage: Gemeinde, "
            "Technologie und installierte Leistung, ohne Kennung, ohne Datum der Inbetriebnahme und ohne Betreiber. Die "
            "Datei wird ersetzt, ohne Verlauf; lux-solaire archiviert bei jeder Erhebung eine Kopie. Ohne Kennung lässt "
            "sich eine Anlage nicht von einer Erhebung zur nächsten verfolgen: Verglichen werden, Gemeinde für Gemeinde "
            "und Technologie für Technologie, die Zeilen über 100 kW (genau 100 kW ausgenommen) zweier aufeinander "
            "folgender Kopien. Eine hinzugekommene Zeile kann eine neue Anlage sein, aber auch eine über 100 kW hinaus "
            "erweiterte Anlage, ein korrigierter Wert oder eine Zeile, die einer anderen Gemeinde zugeordnet wurde; die "
            f"Datei lässt das offen. Verglichene Kopien: {lst}."),
        "gap": lambda days: f"{days} Tage nach der vorigen",
        "csv": "Hinzugekommene und weggefallene Zeilen (CSV)", "nat": "Landesweite Liste",
        "list_aria": "Hinzugekommene Zeilen über 100 kW",
    },
    "lb": {
        "h": "Grouss Installatiounen: dobäikomm Zeilen",
        "note": "iwwer 100 kW, vun engem archivéierte Relevé op deen nächsten",
        "dash_lede": lambda n, n0, first, last, a, d, k, al: (
            f"Am Relevé vum {last} zielt de Leneda-Fichier pro Installatioun <strong>{_int(n, 'lb')} "
            f"{'Installatioun' if n == 1 else 'Installatiounen'} iwwer 100 kW</strong>, all Filièren "
            f"({_int(n0, 'lb')} den {first}). Vum {first} bis den {last}, iwwer {k} archivéiert Relevéen, all mat "
            f"deem virdrun verglach, {'ass' if a == 1 else 'sinn'} <strong>{a} "
            f"{'Zeil' if a == 1 else 'Zeilen'} iwwer 100 kW dobäikomm</strong> an {d} ewechgefall"
            + (f" (dovun {al} am leschte Relevé vum {last})" if k > 2 else "") + "."),
        "latest": "Lescht nei Zeilen",
        "cols": ("Relevé", "Gemeng", "Filière", "Leeschtung (kW)"),
        "ccols": ("Relevé", "Ännerung", "Filière", "Leeschtung (kW)"),
        "more": lambda n: f"Am Ganzen {n} nei Zeilen; déi komplett Lëscht, mat den ewechgefallenen Zeilen, steet am CSV.",
        "none_dash": lambda first, last: f"Tëscht dem {first} an dem {last} ass keng Zeil iwwer 100 kW dobäikomm.",
        "up": "dobäikomm", "down": "ewechgefall",
        "r_up": "am selwechte Relevé ass an der Gemeng eng Zeil iwwer 100 kW vun der selwechter Filière ewechgefall: Erweiderung oder Korrektur méiglech",
        "r_down": "am selwechte Relevé ass an der Gemeng eng Zeil iwwer 100 kW vun der selwechter Filière dobäikomm",
        "m_up": lambda c: f"selwecht Filière a selwecht Leeschtung am selwechte Relevé zu {c} ewechgefall: Wiessel vun der Gemeng méiglech",
        "m_down": lambda c: f"selwecht Filière a selwecht Leeschtung am selwechte Relevé zu {c} dobäikomm",
        "c_lede": lambda c, n, n0, first, last: (
            f"Zu {c} zielt de Leneda-Fichier pro Installatioun <strong>{n} "
            f"{'Installatioun' if n == 1 else 'Installatiounen'} iwwer 100 kW</strong> (Relevé vum {last}), all "
            f"Filièren ({n0} den {first})."),
        "c_some": "Zeilen iwwer 100 kW, déi tëscht zwee archivéierte Relevéen dobäikomm oder ewechgefall sinn:",
        "c_none": lambda first, last: (f"Tëscht dem {first} an dem {last} ass an der Gemeng keng Zeil iwwer 100 kW "
                                       f"dobäikomm oder ewechgefall."),
        "method": lambda lst: (
            "<strong>Method.</strong> Leneda publizéiert all Woch e Fichier mat enger Zeil pro Installatioun: Gemeng, "
            "Filière an installéiert Leeschtung, ouni Identifiant, ouni Datum vun der Inbetriebnam an ouni Bedreiwer. "
            "De Fichier gëtt ersat, ouni Historique; lux-solaire archivéiert bei all Relevé eng Kopie. Ouni Identifiant "
            "kann een eng Installatioun net vun engem Relevé op deen nächste verfollegen: Verglach ginn, Gemeng fir "
            "Gemeng a Filière fir Filière, d'Zeilen iwwer 100 kW (genee 100 kW ausgeschloss) vun zwou Kopien no "
            "openeen. Eng nei Zeil kann eng nei Installatioun sinn, mä och eng iwwer 100 kW erweidert Installatioun, "
            "e korrigéierte Wäert oder eng Zeil, déi enger anerer Gemeng zougeuerdnet gouf; de Fichier seet net wat. "
            f"Verglach Kopien: {lst}."),
        "gap": lambda days: f"{days} Deeg no der viregter",
        "csv": "Nei an ewechgefall Zeilen (CSV)", "nat": "Nationall Lëscht",
        "list_aria": "Nei Zeilen iwwer 100 kW",
    },
    "pt": {
        "h": "Grandes instalações: linhas surgidas",
        "note": "acima de 100 kW, de um levantamento arquivado para o seguinte",
        "dash_lede": lambda n, n0, first, last, a, d, k, al: (
            f"No levantamento de {last}, o ficheiro da Leneda por instalação conta <strong>{_int(n, 'pt')} "
            f"{'instalação' if n == 1 else 'instalações'} acima de 100 kW</strong>, todas as tecnologias "
            f"({_int(n0, 'pt')} em {first}). De {first} a {last}, em {k} levantamentos arquivados, cada um "
            f"comparado com o anterior, <strong>{a} "
            f"{'linha acima de 100 kW surgiu' if a == 1 else 'linhas acima de 100 kW surgiram'}</strong> e {d} "
            f"{'desapareceu' if d == 1 else 'desapareceram'}"
            + (f" ({al} das linhas surgidas no último levantamento, o de {last})" if k > 2 else "") + "."),
        "latest": "Últimas linhas surgidas",
        "cols": ("Levantamento", "Município", "Tecnologia", "Potência (kW)"),
        "ccols": ("Levantamento", "Movimento", "Tecnologia", "Potência (kW)"),
        "more": lambda n: f"{n} linhas surgidas no total; a lista completa, incluindo as linhas desaparecidas, está no CSV.",
        "none_dash": lambda first, last: f"Nenhuma linha acima de 100 kW surgiu entre {first} e {last}.",
        "up": "surgida", "down": "desaparecida",
        "r_up": "uma linha acima de 100 kW da mesma tecnologia desapareceu no município no mesmo levantamento: ampliação ou correção possível",
        "r_down": "uma linha acima de 100 kW da mesma tecnologia surgiu no município no mesmo levantamento",
        "m_up": lambda c: f"mesma tecnologia e mesma potência desaparecidas em {c} no mesmo levantamento: mudança de município possível",
        "m_down": lambda c: f"mesma tecnologia e mesma potência surgidas em {c} no mesmo levantamento",
        "c_lede": lambda c, n, n0, first, last: (
            f"Em {c}, o ficheiro da Leneda por instalação conta <strong>{n} "
            f"{'instalação' if n == 1 else 'instalações'} acima de 100 kW</strong> no levantamento de {last}, "
            f"todas as tecnologias ({n0} em {first})."),
        "c_some": "Linhas acima de 100 kW surgidas ou desaparecidas entre dois levantamentos arquivados:",
        "c_none": lambda first, last: (f"Nenhuma linha acima de 100 kW surgiu nem desapareceu no município "
                                       f"entre {first} e {last}."),
        "method": lambda lst: (
            "<strong>Método.</strong> A Leneda publica todas as semanas um ficheiro com uma linha por instalação: "
            "município, tecnologia e potência instalada, sem identificador, sem data de entrada em serviço e sem "
            "operador. Substitui esse ficheiro sem guardar histórico; o lux-solaire arquiva uma cópia em cada "
            "levantamento. Sem identificador, não é possível seguir uma instalação de um levantamento para o outro: "
            "comparam-se, município a município e tecnologia a tecnologia, as linhas acima de 100 kW (100 kW "
            "exatamente excluídos) de duas cópias consecutivas. Uma linha surgida pode ser uma instalação nova, mas "
            "também uma instalação ampliada para lá de 100 kW, um valor corrigido ou uma linha atribuída a outro "
            f"município; o ficheiro não permite decidir. Cópias comparadas: {lst}."),
        "gap": lambda days: f"{days} dias depois da anterior",
        "csv": "Linhas surgidas e desaparecidas (CSV)", "nat": "Lista nacional",
        "list_aria": "Linhas acima de 100 kW surgidas",
    },
}
CSV_PATH = "/data/csv/solaire_grandes_installations.csv"
DASH_ANCHOR = "grandes-installations"


# ──────────────── mise en forme ───────────────────────────────────────────
def _int(n, lang):
    s = format(int(n), ",")
    return s if lang == "en" else s.replace(",", " ")


def fmt_kw(x, lang):
    """Puissance telle que publiée (au plus 2 décimales, zéros finaux retirés) :
    « 4 623,84 », « 12 600 », « 120,1 » ; point et virgule des milliers en anglais."""
    q = f"{float(x):.2f}".rstrip("0").rstrip(".")
    whole, _, frac = q.partition(".")
    out = _int(int(whole), lang)
    return out + (("." if lang == "en" else ",") + frac if frac else "")


def _esc(s):
    return html_mod.escape(str(s), quote=True)


def _remark(x, lang):
    L = S[lang]
    if x.get("m") is not None:
        return (L["m_up"] if x["e"] == 1 else L["m_down"])(_esc(x["mc"]))
    if x.get("r"):
        return L["r_up"] if x["e"] == 1 else L["r_down"]
    return ""


def _copies(b, lang):
    from datetime import date
    out = []
    for i, s in enumerate(b["snaps"]):
        txt = s["l"]
        if i:
            days = (date.fromisoformat(s["iso"]) - date.fromisoformat(b["snaps"][i - 1]["iso"])).days
            if days > 8:
                txt += f" ({S[lang]['gap'](days)})"
        out.append(txt)
    return ", ".join(out)


def _rel(b, x):
    return b["snaps"][x["p"]]["l"]


def dashboard_section(b, lang, cpath, slug):
    """Contenu de <section id="grandes-installations"> du tableau de bord (blob `b` traduit)."""
    L = S[lang]
    head = (f'<div class="sec-head"><h2>{L["h"]}</h2><span class="sec-note">{L["note"]}</span></div>')
    if not b:
        return head
    first, last = b["snaps"][0]["l"], b["snaps"][-1]["l"]
    ups = [x for x in b["ev"] if x["e"] == 1]
    downs = [x for x in b["ev"] if x["e"] == -1]
    k = len(b["snaps"])
    lede = L["dash_lede"](b["nat"][0], b["nat"][1], first, last, len(ups), len(downs), k,
                          sum(1 for x in ups if x["p"] == k - 1))
    if ups:
        rows = "".join(
            f'<tr><td>{_rel(b, x)}</td><td><a href="{cpath}{slug(x["c"])}/#{DASH_ANCHOR}">{_esc(x["c"])}</a>'
            + (f'<small>{_remark(x, lang)}</small>' if _remark(x, lang) else "")
            + f'</td><td>{TYPE_NAMES[lang].get(x["t"], _esc(x["t"]))}</td><td>{fmt_kw(x["kw"], lang)}</td></tr>'
            for x in ups[:DASH_MAX])
        th = "".join(f'<th scope="col">{c}</th>' for c in L["cols"])
        more = f'<p class="bignote">{L["more"](len(ups))}</p>' if len(ups) > DASH_MAX or downs else ""
        body = (f'<h3 class="bigh">{L["latest"]}</h3>'
                f'<div class="tblscroll" role="region" tabindex="0" aria-label="{L["list_aria"]}">'
                f'<table class="bigtab" aria-label="{L["list_aria"]}"><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div>{more}')
    else:
        body = f'<p class="bignone">{L["none_dash"](first, last)}</p>'
    return (f'{head}<p class="lede">{lede}</p><div class="card">{body}'
            f'<p class="kbnote">{L["method"](_copies(b, lang))} <a href="{CSV_PATH}" download>{L["csv"]}</a></p></div>')


def commune_section(b, lang, lau2, cname_html, home):
    """<section id="grandes-installations"> d'une page communale (blob `b` traduit)."""
    L = S[lang]
    head = f'<div class="sec-head"><h2>{L["h"]}</h2><span class="sec-note">{L["note"]}</span></div>'
    if not b:
        return f'<section id="{DASH_ANCHOR}">{head}</section>'
    first, last = b["snaps"][0]["l"], b["snaps"][-1]["l"]
    n, n0 = b["n"].get(str(lau2), [0, 0])
    lede = L["c_lede"](cname_html, n, n0, first, last)
    mine = [x for x in b["ev"] if x["l"] == lau2]
    if mine:
        th = "".join(f'<th scope="col">{c}</th>' for c in L["ccols"])
        rows = "".join(
            f'<tr><td>{_rel(b, x)}</td><td>{L["up"] if x["e"] == 1 else L["down"]}'
            + (f'<small>{_remark(x, lang)}</small>' if _remark(x, lang) else "")
            + f'</td><td>{TYPE_NAMES[lang].get(x["t"], _esc(x["t"]))}</td><td>{fmt_kw(x["kw"], lang)}</td></tr>'
            for x in mine)
        body = (f'<p class="bigh2" id="bigtab-h">{L["c_some"]}</p><div class="tblscroll" role="region" tabindex="0" '
                f'aria-labelledby="bigtab-h"><table class="bigtab"><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div>')
    else:
        body = f'<p class="bignone">{L["c_none"](first, last)}</p>'
    return (f'<section id="{DASH_ANCHOR}">{head}<p class="lede">{lede}</p><div class="card">{body}'
            f'<p class="kbnote2">{L["method"](_copies(b, lang))}</p>'
            f'<p class="kbnote2"><a href="{home}#{DASH_ANCHOR}">{L["nat"]}</a> · '
            f'<a href="{CSV_PATH}" download>{L["csv"]}</a></p></div></section>')


def csv_table(b, source):
    """Table d'export (format de build.exports) : une ligne par ligne apparue ou disparue."""
    rows = []
    for x in (b or {}).get("ev", []):
        rows.append([b["snaps"][x["p"]]["iso"], b["snaps"][x["p"] - 1]["iso"],
                     "appeared" if x["e"] == 1 else "disappeared", x["l"], x["c"], x["k"],
                     TYPE_CODE.get(x["t"], x["t"]), x["t"], x["kw"], b["kw"],
                     "same_value_other_municipality" if x.get("m") is not None
                     else "same_technology_changed_in_municipality" if x.get("r") else "",
                     x.get("mc") or ""])
    return {"slug": "solaire_grandes_installations", "source": source,
            "headers": ["reading_date", "previous_reading_date", "change", "lau2", "commune", "canton",
                        "technology", "technology_leneda", "capacity_kw", "threshold_kw_excl", "note",
                        "other_commune"],
            "rows": rows}
