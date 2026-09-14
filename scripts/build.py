#!/usr/bin/env python3
"""Rebuild the Lux-Solaire dashboard from the latest Leneda open data.

Downloads the quarterly + weekly CSVs from data.public.lu, recomputes the
aggregates, and injects them into template.html -> index.html (EN), fr/ and lb/.

Usage:  python3 scripts/build.py
Deps:   pandas, requests (pillow optional, for og.png)

Garde-fous (le build ÉCHOUE plutôt que de publier une prose fausse) :
  - toute clé des dictionnaires i18n doit exister dans template.html ;
  - après traduction, aucune clé traduite ne doit subsister dans la page ;
  - aucun jeton __XXX__ ni tiret cadratin (U+2014) dans les pages produites ;
  - les encadrés dérivés (plus forte hausse, quatre plus grandes centrales)
    sont recalculés et vérifiés contre les données à chaque build.
"""
import hashlib
import io
import json
import math
import os
import re
import statistics
import sys
import unicodedata
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
DATASET_API = "https://data.public.lu/api/1/datasets/la-production-denergie-electrique-au-luxembourg/"

TECHS = ["Biogaz", "Biomasse", "Cogénération", "Eolienne",
         "Installation hydroélectrique", "Installation photovoltaïque"]
SHORT = {"Biogaz": "biogas", "Biomasse": "biomass", "Cogénération": "chp",
         "Eolienne": "wind", "Installation hydroélectrique": "hydro",
         "Installation photovoltaïque": "pv"}
PV = "Installation photovoltaïque"

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]

# ──────────────── repères officiels (constantes à rafraîchir chaque année) ────
# Chaque bloc porte son URL et sa date de publication ; les dates sont rendues
# sur la page. Chiffres relus dans les documents sources le 14/09/2026.
SOURCES = {
    "ilr": {
        # ILR, « Chiffres-clés 2025 : données statistiques nationales, marché de
        # l'électricité » (CC BY 4.0). Sommaire exécutif + tableaux 3.1/3.2.
        "url": "https://www.ilr.lu/wp-content/uploads/statistiques/ilr-stat-30062026-Chiffres-cles-electricite-2025.pdf",
        "year": 2025, "published": "2026",
        "pv_mw": 746, "pv_mw_delta": 197, "pv_mw_pct": 35.8,
        "pv_n": 33304, "pv_n_delta": 10694, "pv_n_pct": 47.3,
        "pv_gwh": 627, "wind_gwh": 467, "prod_gwh": 1826, "cons_gwh": 6529,
        "self_gwh": 444, "self_pct": 7,
    },
    "pnec": {
        # Plan national intégré en matière d'énergie et de climat 2021-2030,
        # mise à jour de juillet 2024, tableau 8 « Puissance installée des
        # installations MW », p. 44 : ligne Photovoltaïque.
        "url": "https://gouvernement.lu/dam-assets/documents/dossier/pnec/2024-pnec-mise-jour.pdf",
        "published": "2024-07", "table": "tableau 8, p. 44",
        "pv_mw": {2021: 277, 2022: 351, 2023: 433, 2024: 533, 2025: 644,
                  2026: 756, 2027: 867, 2028: 989, 2029: 1111, 2030: 1236},
    },
}


def _get(url, timeout=60):
    """Téléchargement brut (bytes). Avec LUX_SOLAIRE_CACHE=1, les réponses sont
    mises en cache dans .cache/ (ignoré par git et par Vercel) pour itérer sur
    le gabarit sans re-télécharger ; le build normal et le cron n'en font rien."""
    if os.environ.get("LUX_SOLAIRE_CACHE") == "1":
        cache = ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        f = cache / hashlib.sha1(url.encode()).hexdigest()
        if f.exists():
            return f.read_bytes()
        content = requests.get(url, timeout=timeout).content
        f.write_bytes(content)
        return content
    return requests.get(url, timeout=timeout).content


def _label_fr(d):
    """Libellé court d'un relevé hebdomadaire : « 14 sept. 2026 ». Règle
    typographique française : mars, mai, juin et août ne s'abrègent pas."""
    m = MONTHS_FR[d.month - 1]
    return f"{d.day} {m if len(m) <= 4 else m[:4] + '.'} {d.year}"


def fetch_resources():
    """Return ({label: dataframe} quarterly commune files + weekly commune file,
    weekly date, weekly not-grouped dataframe). The weekly resource retained is
    the most recent by date in its title (not the last one in list order)."""
    meta = json.loads(_get(DATASET_API, timeout=30))
    quarterly, weekly, ng = {}, [], []
    for r in meta["resources"]:
        title = r["title"]
        m = re.match(r"open-data-power-generation-q(\d)-(\d{4})\.csv", title)
        if m:
            q, y = m.group(1), m.group(2)
            quarterly[f"{y} T{q}"] = r["url"]
            continue
        m2 = re.search(r"weekly-(\d{4})-(\d{2})-(\d{2})-(commune|not-grouped)\.csv$", title)
        if m2:
            d = date(*map(int, m2.groups()[:3]))
            (weekly if m2.group(4) == "commune" else ng).append((d, r["url"]))
    frames = {}
    for label in sorted(quarterly):
        frames[label] = pd.read_csv(io.BytesIO(_get(quarterly[label], timeout=30)))
    if not weekly or not ng:
        sys.exit("no weekly commune / not-grouped file found in dataset")
    wdate, wurl = max(weekly)
    ngdate, ngurl = max(ng)
    if ngdate != wdate:
        print(f"attention : fichier par installation daté du {ngdate}, commune du {wdate}")
    frames[_label_fr(wdate)] = pd.read_csv(io.BytesIO(_get(wurl, timeout=30)))
    ngdf = pd.read_csv(io.BytesIO(_get(ngurl, timeout=60)))
    return frames, wdate, ngdf


RNPP_API = ("https://data.public.lu/api/1/datasets/registre-national-des-personnes-physiques-rnpp-"
            "population-par-commune-population-per-municipality/")


def _norm_name(s):
    """Clé de jointure sur le nom de commune : sans accents, minuscules, alnum."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def fetch_population():
    """Population par commune du Registre national des personnes physiques
    (RNPP, CC0) : fichier CSV le plus récent (date dans le titre, jj-mm-aaaa).
    Le fichier n'a pas de colonne total : population = somme des 4 colonnes
    mineurs/majeurs par sexe. Le COMMUNE_CODE n'est pas le LAU2 : jointure
    sur le nom normalisé. Retourne ({nom normalisé: population}, date)."""
    meta = json.loads(_get(RNPP_API, timeout=30))
    best = None
    for r in meta["resources"]:
        m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{4})-rnrpp-population-commune\.csv$", r["title"])
        if m:
            d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if best is None or d > best[0]:
                best = (d, r["url"])
    if best is None:
        sys.exit("RNPP : aucun fichier CSV de population par commune trouvé")
    df = pd.read_csv(io.BytesIO(_get(best[1], timeout=30)), encoding="latin-1")
    cols = ["FEMMES_MINEURES", "HOMMES_MINEURS", "FEMMES_MAJEURES", "HOMMES_MAJEURS"]
    df["pop"] = df[cols].sum(axis=1)
    return {_norm_name(n): int(p) for n, p in zip(df["COMMUNE_NOM"], df["pop"])}, best[0]


def build(frames, wdate, ng, pop, pop_date):
    labels = list(frames)
    series = []
    for label, df in frames.items():
        row = {"label": label}
        for t in TECHS:
            row[SHORT[t]] = round(pd.to_numeric(df[t + " Performance [kW]"]).sum() / 1000, 2)
        row["pv_count"] = int(pd.to_numeric(df[PV + " Producteur [#]"]).sum())
        series.append(row)

    latest, first = frames[labels[-1]].copy(), frames[labels[0]]
    for t in TECHS:
        latest[t + " Performance [kW]"] = pd.to_numeric(latest[t + " Performance [kW]"])
    latest["total_kw"] = sum(latest[t + " Performance [kW]"] for t in TECHS)
    pv0 = first.set_index("LAU2")[PV + " Performance [kW]"]

    # ---- fichier hebdomadaire par installation : tailles + toitures par commune ----
    ng = ng.copy()
    ng["p"] = pd.to_numeric(ng["Puissance installée [kW]"])
    pv_inst = ng[ng["Type d'installation"] == PV]
    small_by_lau2 = pv_inst[pv_inst["p"] <= 30].groupby("LAU2").size()   # toitures : 30 kW ou moins

    communes, unmatched = [], []
    for _, r in latest.iterrows():
        pv = r[PV + " Performance [kW]"]
        base = float(pv0.get(r["LAU2"], 0))
        n = int(r[PV + " Producteur [#]"])
        p = pop.get(_norm_name(r["Commune"]))
        if p is None:
            unmatched.append(r["Commune"])
            p = 0
        communes.append({
            "c": r["Commune"], "k": r["Canton"], "lau2": int(r["LAU2"]),
            "pv": round(pv, 1),
            "n": n,
            "tot": round(r["total_kw"], 1),
            "share": round(pv / r["total_kw"] * 100, 1) if r["total_kw"] > 0 else 0,
            "g": round(pv - base, 1),
            "gp": round((pv / base - 1) * 100, 1) if base > 0 else None,
            "wind": round(r["Eolienne Performance [kW]"], 1),
            "hydro": round(r["Installation hydroélectrique Performance [kW]"], 1),
            "chp": round(r["Cogénération Performance [kW]"], 1),
            "bio": round(r["Biogaz Performance [kW]"] + r["Biomasse Performance [kW]"], 1),
            # par habitant (RNPP) : W/hab., installations PV et toitures (≤ 30 kW) pour 1 000 hab.
            "pop": p,
            "wpc": round(pv * 1000 / p) if p else None,
            "ipk": round(n / p * 1000, 1) if p else None,
            "rpk": round(int(small_by_lau2.get(int(r["LAU2"]), 0)) / p * 1000, 1) if p else None,
        })
    if unmatched:
        sys.exit(f"RNPP : {len(unmatched)} communes Leneda sans population : {unmatched}")
    communes.sort(key=lambda x: -x["pv"])

    # ---- cantons : agrégés depuis les communes (capacité, installations, population) ----
    cantons = {}
    for c in communes:
        k = cantons.setdefault(c["k"], {"k": c["k"], "pv": 0.0, "n": 0, "pop": 0, "tot": 0.0})
        k["pv"] += c["pv"]; k["n"] += c["n"]; k["pop"] += c["pop"]; k["tot"] += c["tot"]
    cantons = sorted(cantons.values(), key=lambda k: -k["pv"] * 1000 / k["pop"])
    for k in cantons:
        k["pv"], k["tot"] = round(k["pv"], 1), round(k["tot"], 1)
        k["wpc"] = round(k["pv"] * 1000 / k["pop"])
        k["ipk"] = round(k["n"] / k["pop"] * 1000, 1)
        k["share"] = round(k["pv"] / k["tot"] * 100, 1) if k["tot"] else 0
    pop_total = sum(c["pop"] for c in communes)

    # ---- histogramme des tailles ----
    bins = [0, 5, 10, 15, 30, 100, 500, 1000, 5000, 1e9]
    bin_labels = ["0–5", "5–10", "10–15", "15–30", "30–100", "100–500",
                  "0,5–1 MW", "1–5 MW", ">5 MW"]
    cut = pd.cut(pv_inst["p"], bins=bins, labels=bin_labels)   # bornes fermées à droite : « 30 kW ou moins »
    hist = pv_inst.groupby(cut, observed=True).agg(count=("p", "size"), cap=("p", "sum"))
    sizes = [{"bin": str(i), "count": int(r["count"]), "mw": round(r["cap"] / 1000, 1)}
             for i, r in hist.iterrows()]
    # les quatre plus grandes installations PV recensées (encadré dérivé)
    top_records = [{"c": r["Commune"], "kw": round(float(r["p"]), 1)}
                   for _, r in pv_inst.sort_values("p", ascending=False).head(4).iterrows()]

    # ---- rythme sur 12 mois (ancien KPI, conservé dans data.json pour les réutilisateurs) ----
    q_rows = [r for r in series if re.match(r"^\d{4} T\d$", r["label"])]
    if len(q_rows) >= 5:
        growth12 = q_rows[-1]["pv"] - q_rows[-5]["pv"]
    else:
        growth12 = (q_rows[-1]["pv"] - q_rows[0]["pv"]) / max(len(q_rows) - 1, 1) * 4
    growth12 = round(growth12, 1)
    # (l'« année du 1 GW », projection linéaire naïve, a été retirée le 14/09/2026)

    # ---- ajouts nets entre relevés consécutifs (section « rythme ») ----
    additions = [{"from": a["label"], "to": b["label"],
                  "pv_mw": round(b["pv"] - a["pv"], 1), "pv_n": b["pv_count"] - a["pv_count"],
                  "kind": "quarterly" if re.match(r"^\d{4} T\d$", b["label"]) else "weekly"}
                 for a, b in zip(series, series[1:])]
    # ---- depuis la fin de l'année précédente : relevé hebdo vs relevé T4 ----
    base_year = wdate.year - 1
    base = next((r for r in q_rows if r["label"] == f"{base_year} T4"), None) \
        or next((r for r in reversed(q_rows) if int(r["label"][:4]) <= base_year), q_rows[0])
    since = {"base": base["label"], "pv_mw": round(series[-1]["pv"] - base["pv"], 1),
             "pv_n": series[-1]["pv_count"] - base["pv_count"]}
    # relevé Leneda de la même échéance que les chiffres annuels de l'ILR (fin d'année)
    ilr_q = next((r for r in q_rows if r["label"] == f"{SOURCES['ilr']['year']} T4"), None)

    shares = [c["share"] for c in communes]
    pv_kw_total = float(latest[PV + " Performance [kW]"].sum())
    return {
        "series": series,
        "communes": communes,
        "cantons": cantons,
        "sizes": sizes,
        "additions": additions,
        "population": {
            "source": RNPP_API, "date_iso": pop_date.isoformat(),
            "date": f"{pop_date.day}{'er' if pop_date.day == 1 else ''} {MONTHS_FR[pop_date.month - 1]} {pop_date.year}",
            "total": pop_total,
            "wpc": round(pv_kw_total * 1000 / pop_total),
            "ipk": round(series[-1]["pv_count"] / pop_total * 1000, 1),
            "median_wpc": round(statistics.median(c["wpc"] for c in communes)),
        },
        "refs": {"ilr": SOURCES["ilr"], "pnec": SOURCES["pnec"],
                 "leneda_ilr_year_end": {"label": ilr_q["label"], "pv_mw": ilr_q["pv"], "pv_n": ilr_q["pv_count"]} if ilr_q else None},
        "meta": {
            "pv_mw": round(latest[PV + " Performance [kW]"].sum() / 1000, 1),
            "total_mw": round(latest["total_kw"].sum() / 1000, 1),
            "pv_n": int(latest[PV + " Producteur [#]"].sum()),
            "growth12_mw": growth12,
            "since_year_end": since,
            "date": f"{wdate.day}{'er' if wdate.day == 1 else ''} {MONTHS_FR[wdate.month - 1]} {wdate.year}",
            "date_iso": wdate.isoformat(),
            "median_share": round(statistics.median(shares), 1),
            "full_pv_communes": sum(1 for s in shares if s >= 100),
            "top_records": top_records,
        },
    }


SITE = "https://solaire.sitraka.lu"

# ──────────────── i18n (EN par défaut, FR sur /fr, LB sur /lb) ─────────────
# Deux dictionnaires par langue cible : i18n_en.json / i18n_lb.json (texte
# statique du HTML) et i18n_js.json / i18n_lb_js.json (chaînes construites en
# JS). Le HTML traduit s'obtient par remplacement « plus longue clé d'abord » ;
# les libellés d'affichage des DONNÉES (mois, trimestres et, pour l'anglais
# seulement, la virgule décimale) sont traduits séparément.
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
_FR2EN_MONTH = {fr: MONTHS_EN[i] for i, fr in enumerate(MONTHS_FR)}
_MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS_FR) + r")\b")
# abréviations produites par _label_fr : MONTHS_FR[m-1][:4] + "." pour les mois
# de plus de 4 lettres ; mars, mai, juin et août restent entiers (gérés par _MONTH_RE)
_ABBR = {(MONTHS_FR[i][:4] + "."): MONTHS_EN[i][:3] for i in range(12) if len(MONTHS_FR[i]) > 4}

# Lëtzebuergesch : mêmes mécanismes, mais les conventions numériques FRANÇAISES
# sont conservées (virgule décimale, espace des milliers, locale fr-FR).
MONTHS_LB = ["Januar", "Februar", "Mäerz", "Abrëll", "Mee", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]
_FR2LB_MONTH = {fr: MONTHS_LB[i] for i, fr in enumerate(MONTHS_FR)}
_ABBR_LB_SHORT = ["Jan.", "Feb.", "Mäe.", "Abr.", "Mee", "Jun.", "Jul.",
                  "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]
_ABBR_LB = {(MONTHS_FR[i][:4] + "."): _ABBR_LB_SHORT[i] for i in range(12) if len(MONTHS_FR[i]) > 4}
# date-jour luxembourgeoise : ordinal avec point : « 6 Juli » → « 6. Juli »
# (« 1er juillet » FR → « 1er Juli » → « 1. Juli ») ; s'applique après la
# substitution des mois, sur noms complets et abréviations.
_LB_ORD_RE = re.compile(
    r"\b(\d{1,2})(?:er)?\s(?=(?:" +
    "|".join(sorted(map(re.escape, set(MONTHS_LB) | set(_ABBR_LB_SHORT)),
                    key=len, reverse=True)) + r"))")


def _load_i18n(static_name, js_name):
    d = json.loads((ROOT / "scripts" / static_name).read_text())
    js = json.loads((ROOT / "scripts" / js_name).read_text())
    dup = set(d) & set(js)
    if dup:
        sys.exit(f"{static_name}/{js_name} : clés en double {sorted(dup)}")
    d.update(js)
    pairs = sorted(d.items(), key=lambda kv: -len(kv[0]))   # plus longue d'abord
    return d, pairs


I18N, I18N_PAIRS = _load_i18n("i18n_en.json", "i18n_js.json")
I18N_LB, I18N_LB_PAIRS = _load_i18n("i18n_lb.json", "i18n_lb_js.json")


def check_dicts(tpl):
    """Garde d'intégrité i18n, AVANT toute édition du gabarit : chaque clé des
    quatre dictionnaires doit exister dans template.html (une clé morte = une
    phrase qui reste silencieusement en français), et EN/LB doivent couvrir
    exactement le même jeu de clés."""
    problems = []
    for name, dct in (("EN", I18N), ("LB", I18N_LB)):
        dead = [k for k in dct if k not in tpl]
        if dead:
            problems.append(f"clés {name} absentes du gabarit ({len(dead)}) :\n  " +
                            "\n  ".join(repr(k[:90]) for k in dead))
    only_en, only_lb = set(I18N) - set(I18N_LB), set(I18N_LB) - set(I18N)
    if only_en or only_lb:
        problems.append(f"parité EN/LB : {len(only_en)} clés EN sans LB, {len(only_lb)} clés LB sans EN :\n  "
                        + "\n  ".join(repr(k[:90]) for k in sorted(only_en | only_lb)))
    if problems:
        sys.exit("i18n : " + "\n".join(problems))


def _tr_str(s):
    """Traduit un libellé-donnée d'affichage : trimestre FR (T→Q), abréviations
    et noms de mois, virgule décimale française → point. Inoffensif sur les noms
    propres (communes, cantons : ni chiffres, ni mois) → laissés intacts."""
    s = re.sub(r"(\d{4}) T(\d)", r"\1 Q\2", s)               # « 2025 T1 » → « 2025 Q1 »
    for fr, en in _ABBR.items():                             # « juil. » → « Jul »
        s = s.replace(fr, en)
    s = _MONTH_RE.sub(lambda m: _FR2EN_MONTH[m.group(1)], s)  # « juillet » → « July »
    s = re.sub(r"(?<=\d),(?=\d)", ".", s)                    # « 0,5 » → « 0.5 »
    return s


def _tr_str_lb(s):
    """Variante luxembourgeoise : trimestre T→Q, abréviations et noms de mois,
    puis ordinal du jour (« 6 Juli » → « 6. Juli »). Les formats numériques
    français (virgule décimale, espace des milliers) sont CONSERVÉS."""
    s = re.sub(r"(\d{4}) T(\d)", r"\1 Q\2", s)               # « 2025 T1 » → « 2025 Q1 »
    for fr, lb in _ABBR_LB.items():                          # « juil. » → « Jul. »
        s = s.replace(fr, lb)
    s = _MONTH_RE.sub(lambda m: _FR2LB_MONTH[m.group(1)], s)  # « juillet » → « Juli »
    s = _LB_ORD_RE.sub(r"\1. ", s)                           # « 6 Juli » → « 6. Juli »
    return s


def translate_data(obj, tr=_tr_str):
    if isinstance(obj, dict):
        return {k: translate_data(v, tr) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_data(v, tr) for v in obj]
    if isinstance(obj, str):
        return tr(obj)
    return obj


def to_en(html):
    """HTML anglais : dictionnaire (plus longue clé d'abord), puis bascule des
    littéraux JS couplés à la langue (locale des nombres, virgule décimale)."""
    for fr, en in I18N_PAIRS:
        if fr in html:
            html = html.replace(fr, en)
    return (html.replace("'fr-FR'", "'en-US'")
                .replace(".replace('.',',')", ""))


def to_lb(html):
    """HTML luxembourgeois : dictionnaire seul (plus longue clé d'abord). Les
    littéraux JS liés aux nombres (locale fr-FR, virgule décimale) restent
    intacts : le Lëtzebuergesch garde les conventions numériques françaises."""
    for fr, lb in I18N_LB_PAIRS:
        if fr in html:
            html = html.replace(fr, lb)
    return html


LANG_PATHS = (("en", "/"), ("fr", "/fr"), ("lb", "/lb"))


def _jsround(x):
    """Arrondi de Math.round côté JS (moitié vers +∞) : la prose et les KPI
    calculés dans le navigateur ne peuvent pas diverger d'une unité."""
    return math.floor(x + 0.5)


def _thousands(n, lang):
    """Séparateur de milliers de toLocaleString : virgule en anglais, espace
    en FR/LB."""
    s = format(int(n), ",")
    return s if lang == "en" else s.replace(",", " ")


def _dec1(x, lang):
    """Un chiffre après la virgule, arrondi comme toLocaleString (moitié vers le
    haut sur la représentation décimale courte) ; point en anglais, virgule
    en FR/LB ; milliers séparés comme _thousands."""
    q = Decimal(repr(float(x))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    whole, frac = str(abs(q)).split(".")
    sign = "-" if q < 0 else ""
    return sign + _thousands(int(whole), lang) + ("." if lang == "en" else ",") + frac


def _signed1(x, lang):
    return ("+" if x > 0 else "") + _dec1(x, lang)


def _q_label(label):
    """« 2025 T1 » (donnée) → « T1 2025 » (prose) ; idem « 2025 Q1 » → « Q1 2025 »."""
    return re.sub(r"^(\d{4}) ([TQ]\d)$", r"\2 \1", label)


def prose_numbers(d, lang):
    """Chiffres cités dans la prose de template.html, dérivés des mêmes données
    et arrondis comme les KPI équivalents rendus en JS (#k-growth, barre « Top 10
    croissance PV »). Substitués APRÈS to_en/to_lb : les jetons traversent les
    dictionnaires i18n, dont les clés et les valeurs les contiennent. `d` est
    le blob DÉJÀ traduit de la langue cible (libellés de relevés, date)."""
    s = d["series"]
    first, last = s[0], s[-1]
    keys = ("pv", "wind", "hydro", "chp", "biomass", "biogas")
    tot_first, tot_last = sum(first[k] for k in keys), sum(last[k] for k in keys)
    top = max(d["communes"], key=lambda c: c["g"])
    small = [x for x in d["sizes"] if "MW" not in x["bin"] and x["bin"] != "30–100" and x["bin"] != "100–500"]
    big = [x for x in d["sizes"] if "MW" in x["bin"]]
    n_all, mw_all = sum(x["count"] for x in d["sizes"]), sum(x["mw"] for x in d["sizes"])
    q_labels = [r["label"] for r in s if re.match(r"^\d{4} [TQ]\d$", r["label"])]
    return {
        "__DATE__": d["meta"]["date"],
        "__YEAR__": d["meta"]["date_iso"][:4],
        "__PVMW__": _dec1(d["meta"]["pv_mw"], lang),
        "__PVN__": _thousands(d["meta"]["pv_n"], lang),
        "__PVSHARE__": _dec1(last["pv"] / tot_last * 100, lang),
        "__TOTMW__": _thousands(_jsround(tot_last), lang),
        # standfirst : croissance de la capacité PV depuis le premier relevé
        "__PVGROWTHPCT__": str(_jsround((last["pv"] / first["pv"] - 1) * 100)),
        # sous-titre du KPI « Installations PV » : croissance du nombre d'installations
        "__NGROWTHPCT__": str(_jsround((last["pv_count"] / first["pv_count"] - 1) * 100)),
        # premier et dernier relevés trimestriels publiés (« T1 2025 » / « Q1 2025 »)
        "__FIRSTQ__": _q_label(q_labels[0]),
        "__LASTQ__": _q_label(q_labels[-1]),
        "__NREADINGS__": str(len(s)),
        # trajectoire : MW nets ajoutés toutes filières, part du PV, autres filières
        "__GROWTHTOTAL__": str(_jsround(tot_last - tot_first)),
        "__PVGROWTHSHARE__": str(_jsround((last["pv"] - first["pv"]) / (tot_last - tot_first) * 100)),
        "__WINDDELTA__": _signed1(last["wind"] - first["wind"], lang),
        "__CHPDELTA__": _signed1(last["chp"] - first["chp"], lang),
        "__RESTDELTA__": _signed1(sum(last[k] - first[k] for k in ("hydro", "biomass", "biogas")), lang),
        # encadrés « trois signaux » : tout est dérivé, aucun nom de commune en dur
        "__FULLPVCOUNT__": str(d["meta"]["full_pv_communes"]),
        "__MEDSHARE__": _dec1(d["meta"]["median_share"], lang),
        "__TOPGROWTHKW__": _thousands(_jsround(top["g"]), lang),
        "__TOPGROWTHCOMMUNE__": top["c"],
        "__TOPGROWTHPCT__": str(_jsround(top["gp"])),
        "__TOP4NAMES__": ", ".join(r["c"] for r in d["meta"]["top_records"]),
        # « paradoxe résidentiel » : installations comptées une à une dans le
        # fichier not-grouped, c.-à-d. l'effectif de l'histogramme des tailles
        "__NGCOUNT__": _thousands(n_all, lang),
        "__SMALLSHARE_N__": str(_jsround(sum(x["count"] for x in small) / n_all * 100)),
        "__SMALLSHARE_CAP__": str(_jsround(sum(x["mw"] for x in small) / mw_all * 100)),
        "__BIGN__": str(sum(x["count"] for x in big)),
        "__BIGMW__": _thousands(_jsround(sum(x["mw"] for x in big)), lang),
        **official_numbers(d, lang),
        **population_numbers(d, lang),
    }


def population_numbers(d, lang):
    """Jetons de la section « par habitant » (RNPP)."""
    P = d["population"]
    top = max(d["communes"], key=lambda c: c["wpc"])
    low = min(d["communes"], key=lambda c: c["wpc"])
    return {
        "__POPDATE__": P["date"],
        "__POPTOTAL__": _thousands(P["total"], lang),
        "__NATWPC__": _thousands(P["wpc"], lang),
        "__NATIPK__": _dec1(P["ipk"], lang),
        "__MEDWPC__": _thousands(P["median_wpc"], lang),
        "__TOPWPC_COMMUNE__": top["c"],
        "__TOPWPC__": _thousands(top["wpc"], lang),
        "__TOPWPC_MW__": _dec1(top["pv"] / 1000, lang),
        "__TOPWPC_N__": _thousands(top["n"], lang),
        "__TOPWPC_RPK__": _dec1(top["rpk"], lang),
        "__LOWWPC_COMMUNE__": low["c"],
        "__LOWWPC__": _thousands(low["wpc"], lang),
        "__LOWWPC_IPK__": _dec1(low["ipk"], lang),
    }


def official_numbers(d, lang):
    """Jetons de la section « rythme » et de l'encadré « repères officiels » :
    KPI « depuis fin N-1 », chiffres ILR et trajectoire PNEC (constantes
    datées de SOURCES), relevé Leneda de même échéance, ratios calculés."""
    ilr, pnec = d["refs"]["ilr"], d["refs"]["pnec"]
    since = d["meta"]["since_year_end"]
    q4 = d["refs"]["leneda_ilr_year_end"] or {"label": "", "pv_mw": 0, "pv_n": 0}
    years = sorted(int(y) for y in pnec["pv_mw"])
    shown = [y for y in years if y >= ilr["year"]]
    return {
        "__BASEYEAR__": since["base"][:4],
        "__BASEQ__": _q_label(since["base"]),
        "__SINCE_MW__": _dec1(since["pv_mw"], lang),
        "__SINCE_N__": _thousands(since["pv_n"], lang),
        "__ILR_URL__": ilr["url"],
        "__ILR_YEAR__": str(ilr["year"]),
        "__ILR_PUB__": ilr["published"],
        "__ILR_PVMW__": str(ilr["pv_mw"]),
        "__ILR_PVDELTA__": str(ilr["pv_mw_delta"]),
        "__ILR_PVPCT__": _dec1(ilr["pv_mw_pct"], lang),
        "__ILR_N__": _thousands(ilr["pv_n"], lang),
        "__ILR_NDELTA__": _thousands(ilr["pv_n_delta"], lang),
        "__ILR_NPCT__": _dec1(ilr["pv_n_pct"], lang),
        "__ILR_PVGWH__": str(ilr["pv_gwh"]),
        "__ILR_WINDGWH__": str(ilr["wind_gwh"]),
        "__ILR_PRODGWH__": _thousands(ilr["prod_gwh"], lang),
        "__ILR_CONSGWH__": _thousands(ilr["cons_gwh"], lang),
        "__ILR_SELFGWH__": str(ilr["self_gwh"]),
        "__ILR_SELFPCT__": str(ilr["self_pct"]),
        # ratios calculés ici (étiquetés comme tels sur la page)
        "__PVPRODSHARE__": _dec1(ilr["pv_gwh"] / ilr["prod_gwh"] * 100, lang),
        "__PVCONSSHARE__": _dec1(ilr["pv_gwh"] / ilr["cons_gwh"] * 100, lang),
        "__LENEDA_YEQ__": _q_label(q4["label"]),
        "__LENEDA_YEMW__": _dec1(q4["pv_mw"], lang),
        "__LENEDA_YEN__": _thousands(q4["pv_n"], lang),
        "__PNEC_URL__": pnec["url"],
        "__PNEC2030__": _thousands(pnec["pv_mw"][max(years)], lang),
        "__PNEC_LASTYEAR__": str(max(years)),
        "__PNEC_HEAD__": "".join(f'<th scope="col">{y}</th>' for y in shown),
        "__PNEC_ROW__": "".join(f"<td>{_thousands(pnec['pv_mw'][y], lang)}</td>" for y in shown),
    }


def check_claims(data):
    """Les encadrés dérivés restent vrais par construction ; on vérifie quand même
    que la forme du texte (« 4 × ≈5 MW », « plafonnent juste sous les 5 MW »)
    correspond encore aux données, sinon le build s'arrête."""
    top4 = data["meta"]["top_records"]
    if len(top4) != 4 or not all(4500 <= r["kw"] <= 5000 for r in top4):
        sys.exit(f"encadré « 4 × ≈5 MW » : les quatre plus grandes installations ne sont plus toutes "
                 f"entre 4,5 et 5 MW : {top4}. Adapter template.html avant de publier.")
    small = [x for x in data["sizes"] if x["bin"] in ("0–5", "5–10", "10–15", "15–30")]
    if len(small) != 4:
        sys.exit("histogramme des tailles : les quatre classes ≤ 30 kW attendues manquent")
    top = max(data["communes"], key=lambda c: c["g"])
    assert top["g"] == max(c["g"] for c in data["communes"])


def write_seo():
    """robots.txt + sitemap.xml (les trois langues : /, /fr et /lb)."""
    today = date.today().isoformat()
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in ("/", "/fr", "/lb"):
        sm.append(f"<url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod>"
                  f"<changefreq>monthly</changefreq></url>")
    sm.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sm))


OG_FILES = {"fr": "og.png", "en": "og.en.png", "lb": "og.lb.png"}
OG_LOCALE = {"fr": "fr_FR", "en": "en_US", "lb": "lb_LU"}
_OG_TEXT = {
    "fr": ("LUX-SOLAIRE · PHOTOVOLTAÏQUE · OPEN DATA", "Le photovoltaïque luxembourgeois,", "commune par commune",
           "de puissance PV raccordée", "installations photovoltaïques · capacité installée, pas énergie",
           "solaire.sitraka.lu · Leneda / data.public.lu (CC0) · FR · EN · LU"),
    "en": ("LUX-SOLAIRE · SOLAR PV · OPEN DATA", "Solar PV in Luxembourg,", "municipality by municipality",
           "of PV capacity connected", "PV installations · installed capacity, not energy",
           "solaire.sitraka.lu · Leneda / data.public.lu (CC0) · EN · FR · LU"),
    "lb": ("LUX-SOLAIRE · PHOTOVOLTAIK · OPEN DATA", "D'Photovoltaik zu Lëtzebuerg,", "Gemeng fir Gemeng",
           "PV-Leeschtung um Netz", "PV-Installatiounen · installéiert Kapazitéit, net Energie",
           "solaire.sitraka.lu · Leneda / data.public.lu (CC0) · LU · FR · EN"),
}
# macOS en local ; DejaVu sur le runner Linux de la GitHub Action (même repli qu'index-lu)
_FONT_SANS = ("/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans.ttf")
_FONT_SERIF = ("/System/Library/Fonts/Supplemental/Georgia.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
               "DejaVuSerif.ttf") + _FONT_SANS


def _font(candidates, size):
    from PIL import ImageFont
    for f in candidates:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    raise OSError(f"aucune police trouvée parmi {candidates}")


def make_og(data, lang):
    """og:image 1200x630 par langue : capacité PV vivante, libellés traduits.
    Best-effort : un échec est signalé sur stderr mais ne casse pas le build."""
    try:
        from PIL import Image, ImageDraw
        eyebrow, l1, l2, mw_label, n_label, foot = _OG_TEXT[lang]
        serif = _font(_FONT_SERIF, 64)
        big, mid, small = _font(_FONT_SANS, 120), _font(_FONT_SANS, 40), _font(_FONT_SANS, 30)
        img = Image.new("RGB", (1200, 630), "#F4F5F1"); dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, 1200, 12], fill="#C77F00")
        dr.text((80, 66), eyebrow, font=small, fill="#8A5600")
        def fit(txt, font, max_w=1040):
            while dr.textlength(txt, font=font) > max_w and font.size > 30:
                font = font.font_variant(size=font.size - 2)
            return font
        s = fit(l1, serif)
        dr.text((80, 136), l1, font=s, fill="#1D2734")
        dr.text((80, 136 + s.size + 18), l2, font=fit(l2, serif), fill="#C77F00")
        mw = _dec1(data["meta"]["pv_mw"], lang)
        dr.text((80, 330), mw + " MW", font=big, fill="#C77F00")
        w = dr.textlength(mw + " MW", font=big)
        dr.text((80 + w + 34, 400), mw_label, font=mid, fill="#5A6472")
        sub = _thousands(data["meta"]["pv_n"], lang) + " " + n_label
        dr.text((80, 480), sub, font=fit(sub, mid), fill="#5A6472")
        dr.text((80, 556), foot, font=small, fill="#6B7380")
        img.save(ROOT / OG_FILES[lang])
        return True
    except Exception as e:  # noqa: BLE001
        print(f"attention : {OG_FILES[lang]} non régénéré ({e.__class__.__name__}: {e})", file=sys.stderr)
        return False


_TOKEN_RE = re.compile(r"__[A-Z0-9_]+__")


def check_output(html, lang, dct):
    """Après rendu : aucun jeton oublié, aucun tiret cadratin, aucune clé
    traduite encore présente (les clés dont la traduction est identique, comme
    « Canton », sont ignorées). Comparaison PAR CLÉ, pas sur le texte rendu."""
    left = sorted(set(_TOKEN_RE.findall(html)))
    if left:
        sys.exit(f"{lang} : jetons non substitués {left}")
    if "—" in html:
        i = html.index("—")
        sys.exit(f"{lang} : tiret cadratin (U+2014) dans la page rendue, vers : {html[max(0, i-60):i+40]!r}")
    if dct:
        leaks = [k for k, v in dct.items() if v != k and k in html]
        if leaks:
            sys.exit(f"{lang} : {len(leaks)} clés non traduites subsistent :\n  " +
                     "\n  ".join(repr(k[:90]) for k in leaks))


def render_all(data):
    """Écrit les JSON dérivés (EN, LB) et les trois pages depuis le blob FR."""
    # endpoint public : la source reste en FR ; variantes EN + LB pour réutilisation
    data_en = translate_data(data)
    (ROOT / "data" / "data.en.json").write_text(json.dumps(data_en, ensure_ascii=False))
    data_lb = translate_data(data, _tr_str_lb)
    (ROOT / "data" / "data.lb.json").write_text(json.dumps(data_lb, ensure_ascii=False))
    write_seo()
    for lang in ("fr", "en", "lb"):
        make_og(data, lang)
    tpl = (ROOT / "template.html").read_text()
    check_dicts(tpl)
    if "—" in tpl:
        sys.exit("template.html contient un tiret cadratin (U+2014)")

    def render(d, lang):
        blob = json.dumps(d, ensure_ascii=False)
        canonical = SITE + dict(LANG_PATHS)[lang]
        F_GB = ('<svg width="15" height="11" viewBox="0 0 60 44">'
                '<rect width="60" height="44" fill="#012169"/>'
                '<path d="M0 0 60 44M60 0 0 44" stroke="#fff" stroke-width="9"/>'
                '<path d="M0 0 60 44M60 0 0 44" stroke="#C8102E" stroke-width="4"/>'
                '<path d="M30 0V44M0 22H60" stroke="#fff" stroke-width="15"/>'
                '<path d="M30 0V44M0 22H60" stroke="#C8102E" stroke-width="8"/></svg>')
        F_FR = ('<svg width="15" height="11" viewBox="0 0 60 44">'
                '<rect width="20" height="44" fill="#0055A4"/>'
                '<rect x="20" width="20" height="44" fill="#fff"/>'
                '<rect x="40" width="20" height="44" fill="#EF4135"/></svg>')
        F_LU = ('<svg width="15" height="11" viewBox="0 0 60 44">'
                '<rect width="60" height="15" fill="#EF3340"/>'
                '<rect y="15" width="60" height="14" fill="#fff"/>'
                '<rect y="29" width="60" height="15" fill="#00A2E1"/></svg>')
        _FLAG = {"en": F_GB, "fr": F_FR, "lb": F_LU}
        toggle = "".join(
            '<a href="{}"{}>{}{}</a>'.format(
                path, ' class="cur"' if code == lang else '', _FLAG[code],
                {"lb": "LU"}.get(code, code.upper()))
            for code, path in LANG_PATHS)
        og_locale = f'<meta property="og:locale" content="{OG_LOCALE[lang]}">' + "".join(
            f'<meta property="og:locale:alternate" content="{OG_LOCALE[c]}">'
            for c, _ in LANG_PATHS if c != lang)
        html = (tpl.replace("/*__DATA__*/", blob)
                   .replace("__ISODATE__", date.today().isoformat())
                   .replace("__LANG__", lang)
                   .replace("__CANONICAL__", canonical)
                   .replace("__OGIMAGE__", OG_FILES[lang])
                   .replace("<!--OGLOCALE-->", og_locale)
                   .replace("<!--LANGTOGGLE-->", toggle))
        dct = None
        if lang == "en":
            html, dct = to_en(html), I18N
        elif lang == "lb":
            html, dct = to_lb(html), I18N_LB
        # jetons de prose (dont __DATE__) : APRÈS traduction, pour que les clés
        # des dictionnaires puissent les contenir
        for token, value in prose_numbers(d, lang).items():
            html = html.replace(token, value)
        check_output(html, lang, dct)
        return html

    (ROOT / "index.html").write_text(render(data_en, "en"))    # EN par défaut
    for lang, d in (("fr", data), ("lb", data_lb)):
        (ROOT / lang).mkdir(exist_ok=True)
        (ROOT / lang / "index.html").write_text(render(d, lang))
    print(f"index.html (EN) + fr/index.html + lb/index.html rebuilt : "
          f"PV {data['meta']['pv_mw']} MW au {data['meta']['date']} / "
          f"as of {data_en['meta']['date']} / Stand {data_lb['meta']['date']}")


def main():
    frames, wdate, ng = fetch_resources()
    pop, pop_date = fetch_population()
    data = build(frames, wdate, ng, pop, pop_date)
    check_claims(data)
    (ROOT / "data" / "data.json").write_text(json.dumps(data, ensure_ascii=False))
    render_all(data)


if __name__ == "__main__":
    main()
