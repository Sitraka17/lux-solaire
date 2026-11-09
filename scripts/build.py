#!/usr/bin/env python3
"""Rebuild the Lux-Solaire dashboard from the latest Leneda open data.

Downloads the quarterly + weekly CSVs from data.public.lu, recomputes the
aggregates, and injects them into template.html -> index.html (EN), fr/, de/, lb/
and pt/ (plus the calculator, the municipal pages and « Pour les communes »).

Usage:  python3 scripts/build.py
Deps:   pandas, requests (pillow optional, for og.png)

Garde-fous (le build ÉCHOUE plutôt que de publier une prose fausse) :
  - toute clé des dictionnaires i18n doit exister dans template.html ;
  - après traduction, aucune clé traduite ne doit subsister dans la page ;
  - aucun jeton __XXX__ ni tiret cadratin (U+2014) dans les pages produites ;
  - les encadrés dérivés (plus forte hausse, quatre plus grandes centrales)
    sont recalculés et vérifiés contre les données à chaque build ;
  - le relevé hebdomadaire le plus récent a au plus 10 jours, et les fichiers
    « commune » et « not-grouped » ont au plus 7 jours d'écart (check_freshness).
"""
import csv
import hashlib
import html as html_mod
import io
import json
import math
import os
import re
import statistics
import subprocess
import sys
import unicodedata
import urllib.parse
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
import requests

import baremes   # scripts/baremes.json : source UNIQUE des barèmes (aides, tarifs)
import grandes   # nouvelles grandes installations (> 100 kW) d'une copie archivée à la suivante
import ossature  # bandeau, sélecteur de langue, colophon et styles communs à tous les types de pages

ROOT = Path(__file__).resolve().parent.parent
DATASET_API = "https://data.public.lu/api/1/datasets/la-production-denergie-electrique-au-luxembourg/"
DATASET_URL = "https://data.public.lu/fr/datasets/la-production-denergie-electrique-au-luxembourg/"
RNPP_URL = ("https://data.public.lu/fr/datasets/registre-national-des-personnes-physiques-rnpp-"
            "population-par-commune-population-per-municipality/")
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"   # données dérivées (la source Leneda est CC0)
KIT_VERSION = "2026-10-23"   # à incrémenter quand le pipeline de rendu change (exports, JSON-LD)

# classes de taille de l'histogramme (bornes fermées à droite : « 30 kW ou moins »)
BIN_EDGES = [0, 5, 10, 15, 30, 100, 500, 1000, 5000, None]
# tranches du « Klimabonus Gemengen » (aides aux communes, barème révisé chaque année),
# lues dans scripts/baremes.json : [0, 30, 200, 500, 5000, None] et « 0–30 » … « > 5 MW »
KB_EDGES = baremes.kb_edges()
KB_LABELS = baremes.kb_labels()
KBG_YEAR = baremes.gemengen()["bareme"]
ARCHIVE = ROOT / "archive"   # copies hebdomadaires du fichier par installation (Leneda n'en garde qu'une)
# comparaison avec la plus ancienne copie archivée (14/09/2026) : les textes publics
# disent « depuis le 14 septembre 2026 », la référence ne doit donc jamais glisser
BIN_LABELS = ["0–5", "5–10", "10–15", "15–30", "30–100", "100–500",
              "0,5–1 MW", "1–5 MW", ">5 MW"]

TECHS = ["Biogaz", "Biomasse", "Cogénération", "Eolienne",
         "Installation hydroélectrique", "Installation photovoltaïque"]
SHORT = {"Biogaz": "biogas", "Biomasse": "biomass", "Cogénération": "chp",
         "Eolienne": "wind", "Installation hydroélectrique": "hydro",
         "Installation photovoltaïque": "pv"}
PV = "Installation photovoltaïque"

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]
# abréviations usuelles (Imprimerie nationale) : « nov. », pas « nove. » ; mars, mai, juin et août entiers
MONTHS_FR_ABBR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]

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
        content = _fetch(url, timeout)
        f.write_bytes(content)
        return content
    return _fetch(url, timeout)


def _fetch(url, timeout):
    """GET avec 3 essais (délai croissant) ; échoue clairement sur un code HTTP
    d'erreur au lieu de lire une page d'erreur comme un CSV."""
    import time
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            if attempt == 2:
                sys.exit(f"téléchargement impossible ({e}) : {url}")
            time.sleep(5 * (attempt + 1))


# ──────────────── contrôle du format Leneda ───────────────────────────────────
N_COMMUNES = 100   # communes des fichiers Leneda (2026) ; les textes disent « 100 communes »
COMMUNE_COLS = ["LAU2", "Commune", "Canton"] + [t + " Performance [kW]" for t in TECHS] + [PV + " Producteur [#]"]
NG_COLS = ["LAU2", "Commune", "Type d'installation", "Puissance installée [kW]"]


def check_leneda(frames, ng):
    """Échoue avec un message clair si le format des fichiers Leneda a changé :
    colonnes attendues (fichiers par commune et fichier par installation), types
    d'installation connus, nombre de communes (100 dans le relevé le plus récent,
    95 à 105 dans les relevés trimestriels plus anciens)."""
    problems = []
    labels = list(frames)
    for label, df in frames.items():
        miss = [c for c in COMMUNE_COLS if c not in df.columns]
        if miss:
            problems.append(f"fichier par commune « {label} » : colonnes absentes {miss} "
                            f"(colonnes reçues : {list(df.columns)})")
            continue
        n = df["LAU2"].nunique()
        if label == labels[-1] and (n != N_COMMUNES or len(df) != N_COMMUNES):
            problems.append(f"relevé le plus récent « {label} » : {len(df)} lignes et {n} codes LAU2 au lieu de "
                            f"{N_COMMUNES} (fusion de communes ? adapter N_COMMUNES et les textes « 100 communes »)")
        elif not 95 <= n <= 105:
            problems.append(f"fichier par commune « {label} » : {n} communes (attendu : environ {N_COMMUNES})")
        bad = [c for c in COMMUNE_COLS[3:] if pd.to_numeric(df[c], errors="coerce").isna().any()]
        if bad:
            problems.append(f"fichier par commune « {label} » : valeurs non numériques dans {bad}")
    miss = [c for c in NG_COLS if c not in ng.columns]
    if miss:
        problems.append(f"fichier par installation : colonnes absentes {miss} (colonnes reçues : {list(ng.columns)})")
    else:
        types = set(ng["Type d'installation"].dropna().unique())
        if PV not in types:
            problems.append(f"fichier par installation : aucun type « {PV} » (types reçus : {sorted(types)})")
        unknown = types - set(TECHS)
        if unknown:
            problems.append(f"fichier par installation : types d'installation inconnus {sorted(unknown)} "
                            f"(attendus : {TECHS})")
        if pd.to_numeric(ng["Puissance installée [kW]"], errors="coerce").isna().any():
            problems.append("fichier par installation : puissances non numériques")
        n = ng["LAU2"].nunique()
        if not 95 <= n <= N_COMMUNES:
            problems.append(f"fichier par installation : {n} communes (attendu : au plus {N_COMMUNES}, environ {N_COMMUNES})")
    if problems:
        sys.exit("format Leneda inattendu, build arrêté :\n  " + "\n  ".join(problems))


def _label_fr(d):
    """Libellé court d'un relevé hebdomadaire : « 14 sept. 2026 », « 9 nov. 2026 ». Abréviations
    usuelles (MONTHS_FR_ABBR) ; mars, mai, juin et août ne s'abrègent pas."""
    return f"{d.day} {MONTHS_FR_ABBR[d.month - 1]} {d.year}"


MAX_AGE_DAYS = 10      # relevé hebdomadaire plus vieux : build en échec (Leneda n'a pas publié)
MAX_GAP_DAYS = 7       # écart toléré entre les fichiers « commune » et « not-grouped » du relevé


def check_freshness(wdate, ngdate, today=None):
    """Garde-fou de fraîcheur, avant tout téléchargement lourd : le build ÉCHOUE (exit 1)
    si le relevé hebdomadaire le plus récent a plus de MAX_AGE_DAYS jours (Leneda a cessé
    de publier ou a renommé ses fichiers : le site afficherait des données périmées sans
    le dire), ou si les fichiers par commune et par installation divergent de plus de
    MAX_GAP_DAYS jours (les vues croisées mélangeraient deux relevés). L'échec du
    workflow du lundi déclenche l'e-mail d'alerte de GitHub (CONTEXT.md, « Alertes »).
    LUX_SOLAIRE_ALLOW_STALE=1 ramène le contrôle d'âge à un avertissement (build à
    blanc sur un .cache/ ancien, travail local) ; jamais dans le workflow."""
    today = today or date.today()
    age = (today - wdate).days
    gap = abs((ngdate - wdate).days)
    problems = []
    if age > MAX_AGE_DAYS:
        msg = (f"relevé hebdomadaire Leneda périmé : le plus récent est daté du {wdate.isoformat()}, "
               f"soit {age} jours (maximum {MAX_AGE_DAYS}). Vérifier le jeu de données sur data.public.lu "
               f"(publication suspendue ou fichiers renommés ?)")
        if os.environ.get("LUX_SOLAIRE_ALLOW_STALE") == "1":
            print("attention (LUX_SOLAIRE_ALLOW_STALE=1) : " + msg, file=sys.stderr)
        else:
            problems.append(msg)
    if gap > MAX_GAP_DAYS:
        problems.append(f"fichiers hebdomadaires désynchronisés : « commune » du {wdate.isoformat()}, "
                        f"« not-grouped » du {ngdate.isoformat()}, soit {gap} jours d'écart "
                        f"(maximum {MAX_GAP_DAYS})")
    elif gap:
        print(f"attention : fichier par installation daté du {ngdate}, commune du {wdate} ({gap} j d'écart)")
    if problems:
        sys.exit("fraîcheur des données Leneda, build arrêté :\n  " + "\n  ".join(problems))
    return age, gap


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
    check_freshness(wdate, ngdate)
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


def archive_snapshot(ng, wdate):
    """Garde une copie datée du fichier par installation : Leneda le remplace
    chaque semaine, sans historique public."""
    ARCHIVE.mkdir(exist_ok=True)
    out = ARCHIVE / f"leneda-not-grouped-{wdate.isoformat()}.csv.gz"
    if not out.exists():
        ng.to_csv(out, index=False, compression={"method": "gzip", "mtime": 0})


def load_baseline(wdate):
    """Plus ancienne copie archivée antérieure au relevé courant (ou None)."""
    cands = []
    for f in ARCHIVE.glob("leneda-not-grouped-*.csv.gz"):
        d = date.fromisoformat(f.name[len("leneda-not-grouped-"):][:10])
        if 0 < (wdate - d).days:
            cands.append((d, f))
    if not cands:
        return None, None
    d, f = min(cands)
    return d, pd.read_csv(f)


def load_archives(wdate):
    """Toutes les copies archivées jusqu'au relevé courant compris, triées par date :
    [(date, DataFrame)] (détection des nouvelles grandes installations, grandes.py)."""
    out = []
    for f in ARCHIVE.glob("leneda-not-grouped-*.csv.gz"):
        d = date.fromisoformat(f.name[len("leneda-not-grouped-"):][:10])
        if d <= wdate:
            out.append((d, pd.read_csv(f)))
    return sorted(out, key=lambda x: x[0])


def _pv_rows(ng):
    out = ng[ng["Type d'installation"] == PV].copy()
    out["p"] = pd.to_numeric(out["Puissance installée [kW]"])
    return out


def _grid(inst, edges, labels):
    """(national, {LAU2: ...}) : [[installations, kW], ...] par classe, dans l'ordre de `labels`."""
    cut = pd.cut(inst["p"], bins=[e if e is not None else 1e9 for e in edges], labels=labels, include_lowest=True)
    nat = inst.groupby(cut, observed=False)["p"].agg(["size", "sum"])
    g = inst.groupby([inst["LAU2"], cut], observed=False)["p"].agg(["size", "sum"])
    per = {int(k): [[int(g.loc[(k, l), "size"]), float(g.loc[(k, l), "sum"])] for l in labels]
           for k in set(g.index.get_level_values(0))}
    return [[int(nat.loc[l, "size"]), float(nat.loc[l, "sum"])] for l in labels], per


def build(frames, wdate, ng, pop, pop_date, baseline=(None, None), snaps=None):
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
    bins = [e if e is not None else 1e9 for e in BIN_EDGES]
    cut = pd.cut(pv_inst["p"], bins=bins, labels=BIN_LABELS, include_lowest=True)   # bornes fermées à droite : « 30 kW ou moins »
    hist = pv_inst.groupby(cut, observed=True).agg(count=("p", "size"), cap=("p", "sum"))
    sizes = [{"bin": str(i), "count": int(r["count"]), "mw": round(r["cap"] / 1000, 1)}
             for i, r in hist.iterrows()]
    # même histogramme commune par commune (clé LAU2), aligné sur les classes de `sizes`
    by_c = pv_inst.groupby([pv_inst["LAU2"], cut], observed=False)["p"].agg(["size", "sum"])
    sizes_c = {}
    for c in communes:
        sub = by_c.loc[c["lau2"]] if c["lau2"] in by_c.index.get_level_values(0) else None
        sizes_c[str(c["lau2"])] = [[int(sub.loc[s["bin"], "size"]) if sub is not None else 0,
                                    round(float(sub.loc[s["bin"], "sum"]), 1) if sub is not None else 0.0]
                                   for s in sizes]
    # tranches des aides communales (on écarte une tranche vide à l'échelle nationale)
    kb_nat, kb_per = _grid(pv_inst, KB_EDGES, KB_LABELS)
    keep = [i for i, (n, _) in enumerate(kb_nat) if n]
    zero = [[0, 0.0]] * len(KB_LABELS)
    kb = {"bins": [KB_LABELS[i] for i in keep],
          "nat": [[kb_nat[i][0], round(kb_nat[i][1], 1)] for i in keep],
          "c": {str(c["lau2"]): [[kb_per.get(c["lau2"], zero)[i][0], round(kb_per.get(c["lau2"], zero)[i][1], 1)]
                                 for i in keep] for c in communes}}
    # évolution depuis la copie archivée de référence (nombre net d'installations par classe)
    hist = None
    bdate, bng = baseline
    if bng is not None:
        b_inst = _pv_rows(bng)
        det_idx = [BIN_LABELS.index(s["bin"]) for s in sizes]
        now_d, per_d = _grid(pv_inst, BIN_EDGES, BIN_LABELS)
        was_d, wper_d = _grid(b_inst, BIN_EDGES, BIN_LABELS)
        was_k, wper_k = _grid(b_inst, KB_EDGES, KB_LABELS)
        zd = [[0, 0.0]] * len(BIN_LABELS)

        def delta(now_det, was_det, now_kb, was_kb):
            return [sum(x[0] for x in now_det) - sum(x[0] for x in was_det),
                    round(sum(x[1] for x in now_det) - sum(x[1] for x in was_det), 1),
                    [now_det[i][0] - was_det[i][0] for i in det_idx],
                    [now_kb[i][0] - was_kb[i][0] for i in keep]]
        hist = {"date_iso": bdate.isoformat(),
                "date": f"{bdate.day}{'er' if bdate.day == 1 else ''} {MONTHS_FR[bdate.month - 1]} {bdate.year}",
                "nat": delta(now_d, was_d, kb_nat, was_k),
                "c": {str(c["lau2"]): delta(per_d.get(c["lau2"], zd), wper_d.get(c["lau2"], zd),
                                            kb_per.get(c["lau2"], zero), wper_k.get(c["lau2"], zero))
                      for c in communes}}
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
        "sizes_c": sizes_c,
        "kb": kb,
        "hist": hist,
        # lignes de plus de 100 kW apparues ou disparues d'une copie archivée à la suivante
        # (pas d'identifiant d'installation dans le fichier : méthode dans grandes.py)
        "bigs": grandes.detect(snaps or [], lambda x: f"{x.day}{'er' if x.day == 1 else ''} {MONTHS_FR[x.month - 1]} {x.year}"),
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
# abréviations produites par _label_fr (MONTHS_FR_ABBR) ; mars, mai, juin et août
# restent entiers (gérés par _MONTH_RE)
_ABBR = {MONTHS_FR_ABBR[i]: MONTHS_EN[i][:3] for i in range(12) if MONTHS_FR_ABBR[i] != MONTHS_FR[i]}

# Lëtzebuergesch : mêmes mécanismes, mais les conventions numériques FRANÇAISES
# sont conservées (virgule décimale, espace des milliers, locale fr-FR).
MONTHS_LB = ["Januar", "Februar", "Mäerz", "Abrëll", "Mee", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]
_FR2LB_MONTH = {fr: MONTHS_LB[i] for i, fr in enumerate(MONTHS_FR)}
_ABBR_LB_SHORT = ["Jan.", "Feb.", "Mäe.", "Abr.", "Mee", "Jun.", "Jul.",
                  "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]
_ABBR_LB = {MONTHS_FR_ABBR[i]: _ABBR_LB_SHORT[i] for i in range(12) if MONTHS_FR_ABBR[i] != MONTHS_FR[i]}
# date-jour luxembourgeoise : ordinal avec point : « 6 Juli » → « 6. Juli »
# (« 1er juillet » FR → « 1er Juli » → « 1. Juli ») ; s'applique après la
# substitution des mois, sur noms complets et abréviations.
_LB_ORD_RE = re.compile(
    r"\b(\d{1,2})(?:er)?\s(?=(?:" +
    "|".join(sorted(map(re.escape, set(MONTHS_LB) | set(_ABBR_LB_SHORT)),
                    key=len, reverse=True)) + r"))")

# Allemand (/de) : mêmes mécanismes ; public = frontaliers et propriétaires
# allemands. Comme pour le lëtzebuergesch, les conventions numériques
# FRANÇAISES sont CONSERVÉES (virgule décimale, groupement par espace,
# locale fr-FR : conforme DIN 5008 et au style du STATEC).
MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
             "August", "September", "Oktober", "November", "Dezember"]
_FR2DE_MONTH = {fr: MONTHS_DE[i] for i, fr in enumerate(MONTHS_FR)}
_ABBR_DE_SHORT = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli",
                  "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]
_ABBR_DE = {MONTHS_FR_ABBR[i]: _ABBR_DE_SHORT[i] for i in range(12) if MONTHS_FR_ABBR[i] != MONTHS_FR[i]}
# date-jour allemande : ordinal avec point : « 6 Juli » → « 6. Juli »
# (« 1er juillet » FR → « 1er Juli » → « 1. Juli »), après substitution des mois.
_DE_ORD_RE = re.compile(
    r"\b(\d{1,2})(?:er)?\s(?=(?:" +
    "|".join(sorted(map(re.escape, set(MONTHS_DE) | set(_ABBR_DE_SHORT)),
                    key=len, reverse=True)) + r"))")


# Portugais européen (/pt/) : simulateur /pt/simulador/ (8/11/2026), puis TOUT le site le
# même jour (tableau de bord /pt/, pages communales /pt/municipio/<slug>/, « Pour les
# communes » /pt/para-os-municipios/). Public : la communauté portugaise du Luxembourg
# (Differdange, Esch…). Nombres : virgule décimale, milliers séparés par une espace
# insécable FINE (U+202F, celle que toLocaleString('fr-FR') produit : la locale JS
# 'fr-FR' est gardée telle quelle). Dates : « 2 de novembro de 2026 ».
MONTHS_PT = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro"]
_FR2PT_MONTH = {fr: MONTHS_PT[i] for i, fr in enumerate(MONTHS_FR)}
_ABBR_PT_SHORT = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.",
                  "ago.", "set.", "out.", "nov.", "dez."]
_ABBR_PT = {MONTHS_FR_ABBR[i]: _ABBR_PT_SHORT[i] for i in range(12) if MONTHS_FR_ABBR[i] != MONTHS_FR[i]}
# « 2 novembro 2026 » → « 2 de novembro de 2026 » (après substitution des mois)
_PT_DATE_RE = re.compile(r"\b(\d{1,2})(?:er)? (" + "|".join(MONTHS_PT) + r")(?: (\d{4}))?\b")


def _load_i18n(*names):
    """Fusionne plusieurs dictionnaires (texte HTML du tableau de bord, littéraux
    JS, puis les mêmes pour la page simulateur) ; une clé en double est une
    erreur de build."""
    d = {}
    for name in names:
        part = json.loads((ROOT / "scripts" / name).read_text())
        dup = set(d) & set(part)
        if dup:
            sys.exit(f"{name} : clés en double avec un dictionnaire précédent {sorted(dup)[:5]}")
        d.update(part)
    pairs = sorted(d.items(), key=lambda kv: -len(kv[0]))   # plus longue d'abord
    return d, pairs


I18N_FILES = {"en": ("i18n_en.json", "i18n_js.json", "i18n_sim_en.json", "i18n_sim_js.json"),
              "lb": ("i18n_lb.json", "i18n_lb_js.json", "i18n_sim_lb.json", "i18n_sim_lb_js.json"),
              "de": ("i18n_de.json", "i18n_de_js.json", "i18n_sim_de.json", "i18n_sim_de_js.json"),
              "pt": ("i18n_pt.json", "i18n_pt_js.json", "i18n_sim_pt.json", "i18n_sim_pt_js.json")}
I18N, I18N_PAIRS = _load_i18n(*I18N_FILES["en"])
I18N_LB, I18N_LB_PAIRS = _load_i18n(*I18N_FILES["lb"])
I18N_DE, I18N_DE_PAIRS = _load_i18n(*I18N_FILES["de"])
I18N_PT, I18N_PT_PAIRS = _load_i18n(*I18N_FILES["pt"])


def _dict_parts(lang):
    """Les quatre dictionnaires d'une langue, fichier par fichier, dans l'ordre de I18N_FILES."""
    return [json.loads((ROOT / "scripts" / n).read_text()) for n in I18N_FILES[lang]]


def load_templates():
    """template.html et template_simulateur.html, ossature commune (bandeau, colophon, styles :
    scripts/ossature.py) insérée AVANT traduction : les clés des dictionnaires la couvrent aussi."""
    return (ossature.expand((ROOT / "template.html").read_text()),
            ossature.expand((ROOT / "template_simulateur.html").read_text()))


def check_dicts(tpl, parts=None):
    """Garde d'intégrité i18n, AVANT toute édition des gabarits : chaque clé des
    dictionnaires doit exister dans l'un des gabarits (`tpl` = concaténation de
    template.html et template_simulateur.html ; une clé morte = une phrase qui
    reste silencieusement en français), et LB/DE/PT doivent couvrir exactement les
    clés EN, FICHIER PAR FICHIER (i18n_pt.json = i18n_en.json, i18n_pt_js.json =
    i18n_js.json, i18n_sim_pt.json = i18n_sim_en.json, i18n_sim_pt_js.json =
    i18n_sim_js.json) : la date de contenu du tableau de bord ne lit que ses propres
    dictionnaires. `parts` = {langue: [dictionnaire par fichier]} (tests) ; par défaut,
    les fichiers de I18N_FILES."""
    parts = parts or {lang: _dict_parts(lang) for lang in I18N_FILES}
    problems = []
    for lang, ps in parts.items():
        dead = [k for p in ps for k in p if k not in tpl]
        if dead:
            problems.append(f"clés {lang.upper()} absentes du gabarit ({len(dead)}) :\n  " +
                            "\n  ".join(repr(k[:90]) for k in dead))
    for lang, ps in parts.items():
        if lang == "en":
            continue
        for name_en, name_x, a, b in zip(I18N_FILES["en"], I18N_FILES[lang], parts["en"], ps):
            only_en, only_x = set(a) - set(b), set(b) - set(a)
            if only_en or only_x:
                problems.append(f"parité {name_en} / {name_x} : {len(only_en)} clés EN sans {lang.upper()}, "
                                f"{len(only_x)} clés {lang.upper()} sans EN :\n  "
                                + "\n  ".join(repr(k[:90]) for k in sorted(only_en | only_x)))
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
    s = re.sub(r"\b1er(?= [A-Z])", "1", s)                  # « 1er October » → « 1 October »
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


def _tr_str_de(s):
    """Variante allemande : trimestre T→Q, abréviations et noms de mois,
    puis ordinal du jour (« 6 Juli » → « 6. Juli »). Les formats numériques
    français (virgule décimale, espace des milliers) sont CONSERVÉS (DIN 5008)."""
    s = re.sub(r"(\d{4}) T(\d)", r"\1 Q\2", s)               # « 2025 T1 » → « 2025 Q1 »
    for fr, de in _ABBR_DE.items():                          # « juil. » → « Juli »
        s = s.replace(fr, de)
    s = _MONTH_RE.sub(lambda m: _FR2DE_MONTH[m.group(1)], s)  # « juillet » → « Juli »
    return _DE_ORD_RE.sub(r"\1. ", s)                        # « 6 Juli » → « 6. Juli »


def _tr_str_pt(s):
    """Variante portugaise : trimestres gardés (« 2025 T1 », T = trimestre),
    abréviations et noms de mois, puis « 2 de novembro de 2026 » ; « 1er » → « 1 ».
    Formats numériques français conservés (virgule décimale)."""
    for fr, pt in _ABBR_PT.items():                          # « juil. » → « jul. »
        s = s.replace(fr, pt)
    s = _MONTH_RE.sub(lambda m: _FR2PT_MONTH[m.group(1)], s)  # « juillet » → « julho »
    return _PT_DATE_RE.sub(lambda m: f"{m.group(1)} de {m.group(2)}" + (f" de {m.group(3)}" if m.group(3) else ""), s)


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


def to_de(html):
    """HTML allemand : même mécanique que to_lb. Les littéraux JS liés aux
    nombres (locale 'fr-FR', virgule décimale) restent intacts : l'allemand
    garde les conventions numériques françaises (cf. commentaire MONTHS_DE)."""
    for fr, de in I18N_DE_PAIRS:
        if fr in html:
            html = html.replace(fr, de)
    return html


def to_pt(html):
    """HTML portugais (tableau de bord et simulateur) : dictionnaire seul, comme to_de. La locale JS
    'fr-FR' reste intacte : elle produit exactement le format portugais voulu (virgule
    décimale, milliers séparés par U+202F)."""
    for fr, pt in I18N_PT_PAIRS:
        if fr in html:
            html = html.replace(fr, pt)
    return html


from communes import CPATH, FORPATH, HTML_LANG, slug as _slug   # noqa: E402  (pages communales)


LANG_PATHS = (("en", "/"), ("fr", "/fr/"), ("de", "/de/"), ("lb", "/lb/"),
              ("pt", "/pt/"))   # Cloudflare Pages sert les dossiers avec barre finale
# page simulateur (template_simulateur.html) : mêmes langues, chemins propres
SIM_PATHS = (("en", "/simulator/"), ("fr", "/fr/simulateur/"), ("de", "/de/rechner/"), ("lb", "/lb/rechner/"),
             ("pt", "/pt/simulador/"))
SIM_LANGS = tuple(c for c, _ in SIM_PATHS)
DASH_LANGS = tuple(c for c, _ in LANG_PATHS)   # tableau de bord, pages communales, « Pour les communes »


def _jsround(x):
    """Arrondi de Math.round côté JS (moitié vers +∞) : la prose et les KPI
    calculés dans le navigateur ne peuvent pas diverger d'une unité. Pas de
    floor(x + 0.5) : pour 0.49999999999999994, x + 0.5 vaut 1.0 en flottant alors
    que Math.round renvoie 0 (cas couvert par tests/test_arrondis.py)."""
    f = math.floor(x)
    return f + 1 if x - f >= 0.5 else f


def _thousands(n, lang):
    """Séparateur de milliers de toLocaleString : virgule en anglais, espace
    en FR/LB/DE, espace insécable fine U+202F en portugais (celle de toLocaleString('fr-FR'))."""
    s = format(int(n), ",")
    return s if lang == "en" else s.replace(",", "\u202f" if lang == "pt" else " ")


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


def sim_numbers(lang):
    """Montants d'exemple de la FAQ du simulateur, calculés avec les MÊMES formules
    que le moteur sim-engine.js (bonusPV, feedInTariff), sur les barèmes de
    scripts/baremes.json : plus aucun montant écrit à la main (corrigé le 2/11/2026 :
    « 4 500 à 7 500 € » valait 3 900 à 7 500 €). Coûts NON arrondis (9 600 et
    13 200 €) : le net est calculé sur eux, un seul arrondi à la centaine à la fin."""
    kb, tar = baremes.kb_pv, baremes.tarif   # tar : €/kWh
    c_lo, c_hi = 1600 * 6, 2200 * 6                           # devis 1 600 à 2 200 €/kWc, 6 kWc
    net = lambda c: _jsround((c - kb(6)) / 100) * 100        # après Klimabonus, à la centaine
    return {
        "__KB3__": _thousands(_jsround(kb(3)), lang),
        "__KB6__": _thousands(_jsround(kb(6)), lang),
        "__KB10__": _thousands(_jsround(kb(10)), lang),
        "__C6LO__": _thousands(c_lo, lang),
        "__C6HI__": _thousands(c_hi, lang),
        "__NET6LO__": _thousands(net(c_lo), lang),
        "__NET6HI__": _thousands(net(c_hi), lang),
        # batterie de 7 kWh à 700-1 100 €/kWh (hypothèse de l'outil, sans source
        # publiée) moins le Klimabonus batterie, à la centaine (corrigé le 2/11/2026 :
        # « 4 000 à 6 000 € » écrit à la main valait 2 800 à 5 600 €)
        "__BAT7LO__": _thousands(_jsround((7 * 700 - baremes.kb_batt(7)) / 100) * 100, lang),
        "__BAT7HI__": _thousands(_jsround((7 * 1100 - baremes.kb_batt(7)) / 100) * 100, lang),
        "__TAR26__": _dec1(tar(6, 2026) * 100, lang),
        "__TAR27__": _dec1(tar(6, 2027) * 100, lang),
        **heat_numbers(lang),
    }


# ──────────────── pré-rendu statique du simulateur (robots, aperçus) ──────────
# Les résultats du scénario par défaut et de trois profils types sont calculés
# au build par le MÊME moteur que la page (node + /sim-engine.js, via
# scripts/sim_prerender.mjs) et écrits dans le HTML à la place des tirets ; le
# JS de la page recalcule ensuite les mêmes valeurs. Les libellés viennent de
# l'objet L du gabarit (FR) ou de sa traduction dans i18n_sim_*_js.json : aucune
# phrase n'est dupliquée en Python.
def sim_prerender():
    r = subprocess.run(["node", str(ROOT / "scripts" / "sim_prerender.mjs")], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("sim_prerender.mjs : " + r.stderr.strip())
    return json.loads(r.stdout)


_JSL_RE = {}


def _jsl(lang, name, tpl_sim):
    """Libellé `name:'…'` de l'objet L : dans le gabarit (FR) ou dans la VALEUR du
    dictionnaire JS de la langue cible (la clé est la ligne FR entière)."""
    pat = _JSL_RE.get(name)
    if pat is None:
        pat = _JSL_RE[name] = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r":'((?:[^'\\]|\\.)*)'")
    sources = [tpl_sim] if lang == "fr" else {"en": I18N, "de": I18N_DE, "lb": I18N_LB, "pt": I18N_PT}[lang].values()
    for src in sources:
        m = pat.search(src)
        if m:
            return m.group(1).replace("\\'", "'")
    sys.exit(f"{lang} : libellé JS « {name} » introuvable pour le pré-rendu du simulateur")


def sim_static(html, lang, d, tpl_sim, pre):
    """Remplace les tirets des résultats (ids r-*, a-*, b-*, verdict, tableau 1) par le
    scénario par défaut et substitue les jetons __P1_…__ des trois profils types."""
    L = lambda n: _jsl(lang, n, tpl_sim)   # noqa: E731
    T = lambda x: _thousands(_jsround(x), lang)   # noqa: E731
    eur = lambda x: T(x) + " €"   # noqa: E731
    eurS = lambda x: ("+" if x > 0 else "") + T(x) + " €"   # noqa: E731
    pct_sfx = "%" if lang == "en" else " %"
    pct = lambda x: str(_jsround(x)) + pct_sfx   # noqa: E731

    def dmax1(x):   # toLocaleString(maximumFractionDigits: 1)
        v = _dec1(x, lang)
        return v[:-2] if v.endswith((",0", ".0")) else v

    cts = lambda x: _dec1(x * 100, lang) + " c€/kWh"   # noqa: E731
    ctsS = lambda x: _dec1(x * 100, lang) + " c€"   # noqa: E731
    pb_txt = lambda pb: L("never") if pb is None else ("< 1" + L("year1") if pb < 1 else dmax1(pb) + L("years"))   # noqa: E731
    irr_txt = lambda r: "–" if r is None else dmax1(r * 100) + pct_sfx   # noqa: E731

    R, I = pre["defaut"], pre["defaut"]["I"]
    A, B = R["A"], R["B"]
    a_wins = A["npv"] >= B["npv"]
    best, diff = (A if a_wins else B), abs(A["npv"] - B["npv"])
    pb = best["pb"]
    if pb is None:
        cls, title = "bad", L("vNo")
    elif pb < 8:
        cls, title = "good", L("vFast")
    elif pb < 12:
        cls, title = "good", L("vOk")
    elif pb < 18:
        cls, title = "", L("vSlow")
    else:
        cls, title = "bad", L("vNo")
    verdict = L("vNever") if pb is None else (
        (L("vTextA") if a_wins else L("vTextB")) + "<strong>" + pb_txt(pb) + "</strong>" + L("vThen")
        + "<strong>" + eurS(best["npv"]) + "</strong>" + L("vOver") + L("undisc") + ". "
        + (L("vEq") if diff < 100 else L("vDiff") + "<strong>" + eur(diff) + "</strong>" + L("vDiffEnd")))
    K = next(k for k in d["cantons"] if k["k"] == I["canton"])
    canton = ((L("cantonLineV") if re.match(r"[aeiouyéè]", K["k"], re.I) else L("cantonLine")) + K["k"] + L("cantonMid")
              + T(K["n"]) + L("cantonInst") + T(K["wpc"]) + L("cantonWpc") + _dec1(K["ipk"], lang) + L("cantonIpk")
              + d["meta"]["date"] + L("cantonEnd"))
    vals = {
        "r-prod": T(R["prod"]) + L("kwh"),
        "r-prod-sub": T(R["ey"]) + L("perKwc") + dmax1(R["prod"] / 3900) + L("timesHousehold"),
        "r-self": T(R["self"]) + L("kwh"),
        "r-self-sub": pct(R["self"] / R["prod"] * 100) + L("selfSub") + pct(R["self"] / R["cons"] * 100) + L("ofCons"),
        "r-inj": T(R["inj"]) + L("kwh"),
        "r-inj-sub": pct(R["inj"] / R["prod"] * 100) + L("injSub"),
        "r-gain": T(A["y1"]) + L("eurYear"),
        "r-gain-sub": L("gainA") + eur(A["y1"]) + " · " + L("gainB") + eur(B["y1"]),
        "r-cover": L("cover") + pct(R["prod"] / R["cons"] * 100) + L("coverOf"),
        "r-canton": canton,
        "a-bonus": "<b>" + eur(R["bonus"]) + "</b>", "a-capex": "<b>" + eur(R["capexGross"] - R["bonus"]) + "</b>",
        "a-y1": eur(A["y1"]), "a-pb": "<b>" + pb_txt(A["pb"]) + "</b>", "a-npv": "<b>" + eurS(A["npv"]) + "</b>", "a-irr": irr_txt(A["irr"]),
        "b-tariff": "<b>" + cts(R["tar"]) + "</b>", "b-capex": "<b>" + eur(R["capexGross"]) + "</b>",
        "b-y1": eur(B["y1"]), "b-pb": "<b>" + pb_txt(B["pb"]) + "</b>", "b-npv": "<b>" + eurS(B["npv"]) + "</b>", "b-irr": irr_txt(B["irr"]),
        "r-lcoe": L("lcoe") + cts(R["lcoeA"]) + L("lcoeA") + cts(R["lcoeB"]) + L("lcoeB") + cts(I["price"]) + L("lcoeEnd"),
    }
    for id_, val in vals.items():
        old = f'id="{id_}">–<'
        if html.count(old) != 1:
            sys.exit(f"{lang} : pré-rendu du simulateur, cible {old!r} introuvable ou multiple")
        html = html.replace(old, f'id="{id_}">{val}<')
    old = '<div class="verdict" id="verdict"><div class="big">–</div><p>–</p></div>'
    if html.count(old) != 1:
        sys.exit(f"{lang} : pré-rendu du simulateur, bloc verdict introuvable")
    html = html.replace(old, f'<div class="verdict {cls}" id="verdict"><div class="big">{title}</div><p>{verdict}</p></div>')
    win = L("win")
    html = html.replace('<span class="tag" id="tag-a"></span>', f'<span class="tag{" win" if a_wins else ""}" id="tag-a">{win if a_wins else ""}</span>')
    html = html.replace('<span class="tag" id="tag-b"></span>', f'<span class="tag{"" if a_wins else " win"}" id="tag-b">{"" if a_wins else win}</span>')
    old = '<table class="mini" id="tab-detail"></table>'
    if html.count(old) != 1:
        sys.exit(f"{lang} : pré-rendu du simulateur, tableau 1 introuvable")
    price, market, tar = I["price"], I["market"], R["tar"]
    tab = (f'<table class="mini" id="tab-detail"><thead><tr><th scope="col">{L("thItem")}</th><th scope="col">{L("thA")}</th><th scope="col">{L("thB")}</th></tr></thead><tbody>'
           f'<tr><th scope="row">{L("rowSelf")}</th><td>{T(R["self"])} × {ctsS(price)} = {eur(R["self"] * price)}</td><td>{T(R["self"])} × {ctsS(price)} = {eur(R["self"] * price)}</td></tr>'
           f'<tr><th scope="row">{L("rowInj")}</th><td>{T(R["inj"])} × {ctsS(market)} = {eur(R["inj"] * market)}</td><td>{T(R["inj"])} × {ctsS(tar)} = {eur(R["inj"] * tar)}</td></tr>'
           f'<tr><th scope="row"><strong>{L("rowTotal")}</strong></th><td class="{"best" if A["y1"] >= B["y1"] else ""}"><strong>{eur(A["y1"])}</strong></td><td class="{"best" if B["y1"] > A["y1"] else ""}"><strong>{eur(B["y1"])}</strong></td></tr>'
           f'<tr><th scope="row">{L("rowBonus")}</th><td>{eur(R["bonus"])}</td><td>0 €</td></tr>'
           f'<tr><th scope="row">{L("rowCapex")}</th><td>{eur(R["capexGross"] - R["bonus"])}</td><td>{eur(R["capexGross"])}</td></tr></tbody></table>')
    html = html.replace(old, tab)
    # trois profils types (tableau 7)
    for i, key in ((1, "p1"), (2, "p2"), (3, "p3")):
        P = pre[key]
        for tok, val in {
            "PROD": T(P["prod"]) + L("kwh"), "SC": pct(P["sc"] * 100), "KB": eur(P["bonus"]),
            "CAPA": eur(P["capexGross"] - P["bonus"]), "PBA": pb_txt(P["A"]["pb"]), "PBB": pb_txt(P["B"]["pb"]),
            "NPVA": eurS(P["A"]["npv"]), "NPVB": eurS(P["B"]["npv"]),
        }.items():
            html = html.replace(f"__P{i}_{tok}__", val)
    return html


def _decn(x, nd, lang):
    """x à nd décimales fixes (virgule en FR/DE/LB, point en anglais)."""
    s = f"{x:.{nd}f}"
    return s if lang == "en" else s.replace(".", ",")


def heat_numbers(lang):
    """Chiffres de l'outil 3 (pompe à chaleur) cités dans la FAQ, la méthode et les aides, lus
    dans scripts/baremes.json (2/11/2026) : Klimabonus PAC, prix des combustibles, CO2, COP."""
    B = baremes.B
    k, ch = B["klimabonus_pac"]["valeur"], B["modele_chaleur"]["valeur"]
    cop, co2 = B["cop_pac"]["valeur"], B["co2_combustibles"]["valeur"]
    th = lambda v: _thousands(_jsround(v), lang)
    return {
        "__KBPAC_R__": th(k["remplacement"]), "__KBPAC_RM__": th(k["remplacementMajore"]),
        "__KBPAC_S__": th(k["sansRemplacement"]), "__KBPAC_SM__": th(k["sansRemplacementMajore"]),
        "__KBPAC_CUVE__": th(k["cuveMazout"]), "__KBPAC_ZONE__": th(k["zoneEau"]),
        "__KBPAC_DISTPCT__": th(k["distTaux"] * 100), "__KBPAC_DISTMAX__": th(k["distMax"]),
        "__KBPAC_BALLON__": th(k["ballonLParKw"]), "__KBPAC_COP__": _decn(k["copMinA7W35"], 1, lang),
        "__MAZOUT_L__": _decn(B["prix_mazout"]["valeur"]["eurParL"], 3, lang),
        "__GAZ_ILR__": _decn(B["prix_gaz"]["valeur"]["ilr2025"] * 100, 2, lang),
        "__GAZ_RET__": _decn(B["prix_gaz"]["valeur"]["retenu"] * 100, 1, lang),
        "__ELEC_ACHAT__": _decn(B["prix_electricite"]["valeur"]["achat"], 2, lang),
        "__CO2_GAZ__": _dec1(co2["gazPCS"] * 1000, lang), "__CO2_MAZ__": _dec1(co2["mazoutPCI"] * 1000, lang),
        "__CO2_EL__": _dec1(B["co2_electricite"]["valeur"]["reseau"] * 1000, lang),
        "__COP_A__": _decn(cop["a"], 2, lang), "__COP_B__": _decn(abs(cop["b"]), 2, lang),
        "__COP_C__": _decn(cop["c"], 4, lang), "__COP_F__": _decn(cop["f"], 2, lang),
        "__COP_DTMIN__": th(cop["dTmin"]), "__HORIZON_H__": th(ch["horizon"]),
    }


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
        "__TOPGROWTHCOMMUNE__": html_mod.escape(top["c"]),
        "__TOPGROWTHPCT__": str(_jsround(top["gp"])) if top["gp"] is not None else "n.d.",
        "__TOP4NAMES__": html_mod.escape(", ".join(r["c"] for r in d["meta"]["top_records"])),
        # nombre de communes du relevé (badge, titre de la table) : plus de « 100 » écrit en dur
        "__NCOMMUNES__": str(len(d["communes"])),
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


# ──────────────── pré-rendu statique (robots, aperçus de liens, sans JS) ─────
# Même balisage que le JS du gabarit, qui remplace ces blocs par innerHTML sans
# les dupliquer. Injecté APRÈS traduction : tout y est déjà localisé.
TECH_ORDER = [("pv", "Photovoltaïque", "--amber"), ("wind", "Éolien", "--wind"),
              ("biomass", "Biomasse", "--bio"), ("chp", "Cogénération", "--chp"),
              ("hydro", "Hydroélectrique", "--hydro"), ("biogas", "Biogaz", "--biogas")]


def _js_lit(lang, fr_literal):
    """Un littéral JS du gabarit (quotes comprises) dans la langue cible, via
    i18n_js.json / i18n_lb_js.json : « ' inst.' » → « inst.» ;
    « name:'Éolien' » → « Wind ». Python et JS restent ainsi en phase."""
    dct = {"en": I18N, "lb": I18N_LB, "de": I18N_DE, "pt": I18N_PT}.get(lang, {})
    v = dct.get(fr_literal, fr_literal)
    return v.split("'", 1)[1].rsplit("'", 1)[0]


def _pct_label(p, lang):
    """Étiquette du graphique « paradoxe » : une décimale sous 1 %, comme le JS."""
    if p < 1:
        s = f"{p:.1f}"
        return s if lang == "en" else s.replace(".", ",")
    return str(_jsround(p))


def prerender(d, lang):
    """Fragments HTML statiques (marqueur → HTML) pour les KPI-listes, les
    classements, les cantons, le paradoxe, les tableaux de données des
    graphiques et les 100 lignes de la table des communes."""
    T = lambda n: _thousands(n, lang)          # noqa: E731
    D1 = lambda x: _dec1(x, lang)              # noqa: E731
    sign = lambda x: "+" if x > 0 else ""      # noqa: E731
    last = d["series"][-1]
    names = {k: _js_lit(lang, f"name:'{fr}'") for k, fr, _ in TECH_ORDER}
    tot = sum(last[k] for k, _, _ in TECH_ORDER)
    E = html_mod.escape                        # noms de communes et de cantons : défense en profondeur
    # filet de contraste (WCAG 1.4.11) : ambre du PV et vert clair du biogaz, mêmes classes que le JS
    CL = {"pv": "am", "biogas": "bg"}
    cls = lambda k: f' class="{CL[k]}"' if k in CL else ""   # noqa: E731

    def hb(rows, val, sub, mx):
        return "".join(
            f'<div class="nm">{E(r["c"])} <small>· {E(r["k"])}</small></div>'
            f'<div class="tr"><div class="fl" style="width:{val(r) / mx * 100}%"></div></div>'
            f'<div class="vv">{sub(r)}</div>' for r in rows)

    top15 = d["communes"][:15]
    topg = sorted(d["communes"], key=lambda c: -c["g"])[:10]
    topw = sorted(d["communes"], key=lambda c: -c["wpc"])[:10]
    lbl_w, lbl_r = _js_lit(lang, "' W/hab.'"), _js_lit(lang, "' toitures/1 000'")
    lbl_i, lbl_week = _js_lit(lang, "' inst.'"), _js_lit(lang, "'hebdo vs trim.'")
    A = d["additions"]
    amax = max(a["pv_mw"] for a in A)
    n_all = sum(s["count"] for s in d["sizes"])
    mw_all = sum(s["mw"] for s in d["sizes"])

    def paradox_row(s):
        pn, pc = s["count"] / n_all * 100, s["mw"] / mw_all * 100
        unit = "" if "MW" in s["bin"] else " kW"
        return (f'<div class="bin">{s["bin"]}{unit}</div><div class="duo">'
                f'<div class="b cnt" style="width:{max(pn, 0.4)}%"><i>{_pct_label(pn, lang)} % · {T(s["count"])} inst.</i></div>'
                f'<div class="b cap" style="width:{max(pc, 0.4)}%"><i>{_pct_label(pc, lang)} % · {D1(s["mw"])} MW</i></div></div>')

    def paradox_table_row(s):
        pn, pc = s["count"] / n_all * 100, s["mw"] / mw_all * 100
        unit = "" if "MW" in s["bin"] else " kW"
        return (f'<tr><th scope="row">{s["bin"]}{unit}</th><td>{T(s["count"])}</td><td>{D1(pn)} %</td>'
                f'<td>{D1(s["mw"])}</td><td>{D1(pc)} %</td></tr>')

    return {
        "<!--PRE_MIXBAR-->": "".join(
            f'<div{cls(k)} style="width:{last[k] / tot * 100}%;background:var({css})" title="{names[k]} {D1(last[k] / tot * 100)} %"></div>'
            for k, _, css in TECH_ORDER),
        "<!--PRE_MIXLIST-->": "".join(
            f'<div class="mixrow"><span class="sw{" " + CL[k] if k in CL else ""}" style="background:var({css})"></span>{names[k]}'
            f'<span class="vv"><b>{D1(last[k] / tot * 100)} %</b> · {D1(last[k])} MW</span></div>'
            for k, _, css in TECH_ORDER),
        "<!--PRE_TOP_PV-->": hb(top15, lambda r: r["pv"],
                                lambda r: f'<b>{T(_jsround(r["pv"]))}</b> · {D1(r["share"])} %', top15[0]["pv"]),
        "<!--PRE_TOP_GROWTH-->": hb(topg, lambda r: r["g"],
                                    lambda r: f'<b>+{T(_jsround(r["g"]))}</b> · +{_jsround(r["gp"] or 0)} %', topg[0]["g"]),
        "<!--PRE_TOP_WPC-->": hb(topw, lambda r: r["wpc"],
                                 lambda r: f'<b>{T(r["wpc"])}</b>{lbl_w} · {D1(r["rpk"])}{lbl_r}', topw[0]["wpc"]),
        "<!--PRE_CANTONS-->": "".join(
            f'<tr><td>{E(k["k"])}</td><td>{T(_jsround(k["pv"]))}</td><td>{T(k["n"])}</td><td>{T(k["pop"])}</td>'
            f'<td>{T(k["wpc"])}</td><td>{D1(k["ipk"])}</td></tr>' for k in d["cantons"]),
        "<!--PRE_ADDITIONS-->": "".join(
            f'<div class="nm">{a["from"]} → {a["to"]}{" <small>· " + lbl_week + "</small>" if a["kind"] == "weekly" else ""}</div>'
            f'<div class="tr"><div class="fl" style="width:{max(a["pv_mw"], 0) / amax * 100}%"></div></div>'
            f'<div class="vv"><b>{sign(a["pv_mw"])}{D1(a["pv_mw"])} MW</b> · {sign(a["pv_n"])}{T(a["pv_n"])}{lbl_i}</div>'
            for a in A),
        "<!--PRE_PARADOX-->": "".join(paradox_row(s) for s in d["sizes"]),
        "<!--PRE_PARADOX_ROWS-->": "".join(paradox_table_row(s) for s in d["sizes"]),
        "<!--PRE_BIGNEW-->": grandes.dashboard_section(d.get("bigs"), lang, CPATH[lang], _slug),
        "<!--PRE_AREA_HEAD-->": "".join(f'<th scope="col">{names[k]}</th>' for k, _, _ in TECH_ORDER),
        "<!--PRE_AREA_ROWS-->": "".join(
            f'<tr><th scope="row">{r["label"]}</th>' + "".join(f'<td>{D1(r[k])}</td>' for k, _, _ in TECH_ORDER) + "</tr>"
            for r in d["series"]),
        "<!--PRE_ROWS-->": "".join(
            f'<tr id="c-{r["lau2"]}"><td><a class="cl" href="{CPATH[lang]}{_slug(r["c"])}/">{E(r["c"])}</a></td><td>{E(r["k"])}</td><td>{T(_jsround(r["pv"]))}</td><td>{T(r["n"])}</td>'
            f'<td><span class="sharecell"><span class="minitr"><i style="width:{r["share"]}%"></i></span>{D1(r["share"])} %</span></td>'
            f'<td class="{"pos" if r["g"] > 0 else ""}">{sign(r["g"])}{T(_jsround(r["g"]))}</td>'
            f'<td>{T(_jsround(r["tot"]))}</td><td>{T(r["wpc"])}</td><td>{D1(r["ipk"])}</td></tr>'
            for r in d["communes"]),
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


# ──────────────── date de contenu honnête ───────────────────────────────────
STATE = ROOT / "scripts" / "build_state.json"


def content_date(lang, parts):
    """Date du dernier build qui a CHANGÉ la page de cette langue : empreinte
    du gabarit, du dictionnaire, des données, de rt.js et de la version du
    pipeline, mémorisée dans scripts/build_state.json (commité, jamais servi).
    Une seule valeur pour lastmod, dateModified et la version citée."""
    h = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if st.get(lang, {}).get("hash") != h:
        st[lang] = {"hash": h, "date": date.today().isoformat()}
        STATE.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n")
    return st[lang]["date"]


# ──────────────── exports CSV publics + manifeste ───────────────────────────
# Titres par langue = configuration du kit (pas des clés de dictionnaire).
CSV_TITLES = {
    # {n} = nombre de lignes du CSV (communes, cantons), substitué par write_exports
    "solaire_communes": {"fr": "Capacité PV par commune ({n} communes)",
                         "en": "PV capacity by municipality ({n} municipalities)",
                         "lb": "PV-Kapazitéit pro Gemeng ({n} Gemengen)",
                         "de": "PV-Leistung je Gemeinde ({n} Gemeinden)",
                         "pt": "Potência fotovoltaica por município ({n} municípios)"},
    "solaire_cantons": {"fr": "Capacité PV par canton ({n} cantons)",
                        "en": "PV capacity by canton ({n} cantons)",
                        "lb": "PV-Kapazitéit pro Kanton ({n} Kantonen)",
                        "de": "PV-Leistung je Kanton ({n} Kantone)",
                        "pt": "Potência fotovoltaica por cantão ({n} cantões)"},
    "solaire_filieres": {"fr": "Capacité installée par filière et par relevé",
                         "en": "Installed capacity by technology and reading",
                         "lb": "Installéiert Kapazitéit pro Filière a Relevé",
                         "de": "Installierte Leistung je Technologie und Erhebung",
                         "pt": "Potência instalada por tecnologia e por levantamento"},
    "solaire_tailles": {"fr": "Installations PV par classe de taille",
                        "en": "PV installations by size class",
                        "lb": "PV-Installatiounen no Gréisstklass",
                        "de": "PV-Anlagen nach Größenklasse",
                        "pt": "Instalações fotovoltaicas por classe de potência"},
    "solaire_communes_tailles": {"fr": "Installations PV par commune et par classe de taille",
                                 "en": "PV installations by municipality and size class",
                                 "lb": "PV-Installatiounen pro Gemeng an no Gréisstklass",
                                 "de": "PV-Anlagen je Gemeinde und Größenklasse",
                                 "pt": "Instalações fotovoltaicas por município e por classe de potência"},
    "solaire_communes_tranches_aides": {"fr": "Installations PV par commune, tranches des aides communales (Klimabonus Gemengen)",
                                        "en": "PV installations by municipality, municipal subsidy bands (Klimabonus Gemengen)",
                                        "lb": "PV-Installatiounen pro Gemeng, Tranche vun de Gemengenhëllefen (Klimabonus Gemengen)",
                                        "de": "PV-Anlagen je Gemeinde, Stufen der Gemeindeförderung (Klimabonus Gemengen)",
                                        "pt": "Instalações fotovoltaicas por município, escalões das ajudas municipais (Klimabonus Gemengen)"},
    "solaire_grandes_installations": {"fr": "Lignes de plus de 100 kW apparues ou disparues entre deux relevés ({n} lignes)",
                                      "en": "Rows over 100 kW that appeared or disappeared between two readings ({n} rows)",
                                      "lb": "Zeilen iwwer 100 kW, déi tëscht zwee Relevéen dobäikomm oder ewechgefall sinn ({n} Zeilen)",
                                      "de": "Zeilen über 100 kW, die zwischen zwei Erhebungen hinzugekommen oder weggefallen sind ({n} Zeilen)",
                                      "pt": "Linhas acima de 100 kW que surgiram ou desapareceram entre dois levantamentos ({n} linhas)"},
}
JSON_TITLE = {"fr": "Toutes les données de la page (JSON)", "en": "All the data on this page (JSON)",
              "lb": "All d'Donnéeë vun dëser Säit (JSON)", "de": "Alle Daten dieser Seite (JSON)",
              "pt": "Todos os dados do painel de dados (JSON)"}
CSV_NOTES = {
    "solaire_communes": {"fr": "Relevé hebdomadaire Leneda par commune ; population RNPP (somme des quatre colonnes mineurs/majeurs).",
                         "en": "Leneda weekly reading by municipality; RNPP population (sum of the four minors/adults columns).",
                         "lb": "Wëchentleche Leneda-Relevé pro Gemeng; RNPP-Populatioun (Zomm vun de véier Kolonne Mannerjäreger/Volljäreger).",
                         "de": "Wöchentliche Leneda-Erhebung je Gemeinde; RNPP-Bevölkerung (Summe der vier Spalten Minderjährige/Volljährige).",
                         "pt": "Levantamento semanal da Leneda por município; população RNPP (soma das quatro colunas menores/maiores)."},
    "solaire_cantons": {"fr": "Agrégé à partir des communes.", "en": "Aggregated from the municipalities.", "lb": "Aus de Gemengen zesummegerechent.",
                        "de": "Aus den Gemeinden aggregiert.", "pt": "Agregado a partir dos municípios."},
    "solaire_filieres": {"fr": "Une ligne par relevé : fichiers trimestriels (reading_kind=quarterly) et relevé hebdomadaire courant (weekly), deux extraits Leneda distincts.",
                         "en": "One row per reading: quarterly files (reading_kind=quarterly) and the current weekly reading (weekly), two separate Leneda extracts.",
                         "lb": "Eng Zeil pro Relevé: Quartalsfichieren (reading_kind=quarterly) an den aktuelle wëchentleche Relevé (weekly), zwee verschidden Leneda-Extraiten.",
                         "de": "Eine Zeile je Erhebung: Quartalsdateien (reading_kind=quarterly) und aktuelle Wochenerhebung (weekly), zwei verschiedene Leneda-Auszüge.",
                         "pt": "Uma linha por levantamento: ficheiros trimestrais (reading_kind=quarterly) e levantamento semanal atual (weekly), dois extratos distintos da Leneda."},
    "solaire_tailles": {"fr": "Fichier hebdomadaire par installation ; bornes fermées à droite (kw_max inclus).",
                        "en": "Weekly per-installation file; right-closed bins (kw_max included).",
                        "lb": "Wëchentleche Fichier pro Installatioun; Klasse riets zou (kw_max abegraff).",
                        "de": "Wöchentliche Datei je Anlage; rechts geschlossene Klassen (kw_max inbegriffen).",
                        "pt": "Ficheiro semanal por instalação; classes fechadas à direita (kw_max incluído)."},
    "solaire_communes_tailles": {"fr": "Fichier hebdomadaire par installation, regroupé par commune (LAU2) ; bornes fermées à droite (kw_max inclus) ; capacité en kW.",
                                 "en": "Weekly per-installation file, grouped by municipality (LAU2); right-closed bins (kw_max included); capacity in kW.",
                                 "lb": "Wëchentleche Fichier pro Installatioun, pro Gemeng (LAU2) gruppéiert; Klasse riets zou (kw_max abegraff); Kapazitéit a kW.",
                                 "de": "Wöchentliche Datei je Anlage, nach Gemeinde (LAU2) gruppiert; rechts geschlossene Klassen (kw_max inbegriffen); Leistung in kW.",
                                 "pt": "Ficheiro semanal por instalação, agrupado por município (LAU2); classes fechadas à direita (kw_max incluído); potência em kW."},
    "solaire_communes_tranches_aides": {"fr": f"Même fichier, tranches 30 / 200 / 500 kWc / 5 MWc du Klimabonus Gemengen (barème {KBG_YEAR}) ; capacité en kW.",
                                        "en": f"Same file, Klimabonus Gemengen bands 30 / 200 / 500 kWp / 5 MWp ({KBG_YEAR} scale); capacity in kW.",
                                        "lb": f"Selwechte Fichier, Tranche 30 / 200 / 500 kWp / 5 MWp vum Klimabonus Gemengen (Bareem {KBG_YEAR}); Kapazitéit a kW.",
                                        "de": f"Gleiche Datei, Stufen 30 / 200 / 500 kWp / 5 MWp des Klimabonus Gemengen (Stand {KBG_YEAR}); Leistung in kW.",
                                        "pt": f"Mesmo ficheiro, escalões de 30 / 200 / 500 kWp / 5 MWp do Klimabonus Gemengen (tabela de {KBG_YEAR}); potência em kW."},
    "solaire_grandes_installations": {
        "fr": "Copies archivées du fichier hebdomadaire par installation, comparées deux à deux par commune et par filière (lignes de plus de 100 kW, seuil exclu). Sans identifiant d'installation : une ligne apparue peut être une installation nouvelle, agrandie, corrigée ou rattachée à une autre commune.",
        "en": "Archived copies of the weekly per-installation file, compared pairwise by municipality and technology (rows over 100 kW, threshold excluded). No installation identifier: a row that appears may be a new, extended or corrected installation, or one assigned to another municipality.",
        "lb": "Archivéiert Kopie vum wëchentleche Fichier pro Installatioun, zwou a zwou pro Gemeng a pro Filière verglach (Zeilen iwwer 100 kW, Schwell ausgeschloss). Ouni Identifiant: eng nei Zeil kann eng nei, erweidert oder korrigéiert Installatioun sinn, oder eng, déi enger anerer Gemeng zougeuerdnet gouf.",
        "de": "Archivierte Kopien der wöchentlichen Datei je Anlage, paarweise je Gemeinde und Technologie verglichen (Zeilen über 100 kW, Schwelle ausgenommen). Ohne Anlagenkennung: Eine hinzugekommene Zeile kann eine neue, erweiterte oder korrigierte Anlage sein oder einer anderen Gemeinde zugeordnet worden sein.",
        "pt": "Cópias arquivadas do ficheiro semanal por instalação, comparadas duas a duas por município e por tecnologia (linhas acima de 100 kW, limiar excluído). Sem identificador de instalação: uma linha que surge pode ser uma instalação nova, ampliada ou corrigida, ou atribuída a outro município."},
}


def _period(label):
    """« 2025 T1 » → « 2025-Q1 » ; autre libellé (hebdo) → chaîne vide."""
    m = re.match(r"^(\d{4}) T(\d)$", label)
    return f"{m.group(1)}-Q{m.group(2)}" if m else ""


def exports(d):
    """Tables CSV dérivées du blob FR (mêmes valeurs que la page). En-têtes en
    snake_case anglais, STABLES une fois publiés ; décimale point ; dates ISO."""
    m, P = d["meta"], d["population"]
    q_labels = [r["label"] for r in d["series"] if _period(r["label"])]
    first_q = _period(q_labels[0])
    bin_bounds = {lbl: (BIN_EDGES[i], BIN_EDGES[i + 1]) for i, lbl in enumerate(BIN_LABELS)}
    return [
        {"slug": "solaire_communes", "source": DATASET_URL,
         "headers": ["reading_date", "lau2", "commune", "canton", "pv_kw", "pv_installations", "pv_share_pct",
                     "pv_delta_kw_since_first_reading", "first_reading", "total_kw", "wind_kw", "hydro_kw", "chp_kw",
                     "bio_kw", "population", "population_date", "population_source_url", "w_per_inhabitant",
                     "installations_per_1000", "rooftops_le30kw_per_1000"],
         "rows": [[m["date_iso"], c["lau2"], c["c"], c["k"], c["pv"], c["n"], c["share"], c["g"], first_q, c["tot"],
                   c["wind"], c["hydro"], c["chp"], c["bio"], c["pop"], P["date_iso"], RNPP_URL, c["wpc"], c["ipk"], c["rpk"]]
                  for c in d["communes"]]},
        {"slug": "solaire_cantons", "source": DATASET_URL,
         "headers": ["reading_date", "canton", "pv_kw", "pv_installations", "total_kw", "pv_share_pct", "population",
                     "population_date", "population_source_url", "w_per_inhabitant", "installations_per_1000"],
         "rows": [[m["date_iso"], k["k"], k["pv"], k["n"], k["tot"], k["share"], k["pop"], P["date_iso"], RNPP_URL,
                   k["wpc"], k["ipk"]] for k in d["cantons"]]},
        {"slug": "solaire_filieres", "source": DATASET_URL,
         "headers": ["reading", "reading_kind", "pv_mw", "wind_mw", "hydro_mw", "chp_mw", "biomass_mw", "biogas_mw",
                     "pv_installations"],
         "rows": [[_period(r["label"]) or m["date_iso"], "quarterly" if _period(r["label"]) else "weekly",
                   r["pv"], r["wind"], r["hydro"], r["chp"], r["biomass"], r["biogas"], r["pv_count"]]
                  for r in d["series"]]},
        {"slug": "solaire_tailles", "source": DATASET_URL,
         "headers": ["reading_date", "size_class", "kw_min_excl", "kw_max_incl", "pv_installations", "capacity_mw"],
         "rows": [[m["date_iso"], s["bin"].replace("–", "-").replace(",", ".") + ("" if "MW" in s["bin"] else " kW"),
                   bin_bounds[s["bin"]][0], bin_bounds[s["bin"]][1], s["count"], s["mw"]] for s in d["sizes"]]},
        {"slug": "solaire_communes_tailles", "source": DATASET_URL,
         "headers": ["reading_date", "lau2", "commune", "canton", "size_class", "kw_min_excl", "kw_max_incl",
                     "pv_installations", "capacity_kw"],
         "rows": [[m["date_iso"], c["lau2"], c["c"], c["k"],
                   s["bin"].replace("–", "-").replace(",", ".") + ("" if "MW" in s["bin"] else " kW"),
                   bin_bounds[s["bin"]][0], bin_bounds[s["bin"]][1], n, kw]
                  for c in sorted(d["communes"], key=lambda c: c["c"])
                  for s, (n, kw) in zip(d["sizes"], d["sizes_c"][str(c["lau2"])])]},
        {"slug": "solaire_communes_tranches_aides", "source": DATASET_URL,
         "headers": ["reading_date", "lau2", "commune", "canton", "size_class", "kw_min_excl", "kw_max_incl",
                     "pv_installations", "capacity_kw"],
         "rows": [[m["date_iso"], c["lau2"], c["c"], c["k"],
                   b.replace("–", "-").replace(",", ".") + ("" if "MW" in b else " kW"),
                   KB_EDGES[KB_LABELS.index(b)], KB_EDGES[KB_LABELS.index(b) + 1], n, kw]
                  for c in sorted(d["communes"], key=lambda c: c["c"])
                  for b, (n, kw) in zip(d["kb"]["bins"], d["kb"]["c"][str(c["lau2"])])]},
        grandes.csv_table(d.get("bigs"), DATASET_URL),
    ]


def write_exports(tables, cdate):
    """data/csv/<slug>.csv (UTF-8 avec BOM, virgule, colonne source_url) et
    data/manifest.json, qui alimente la liste de téléchargements et le JSON-LD."""
    out = ROOT / "data" / "csv"
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for t in tables:
        p = out / f"{t['slug']}.csv"
        with open(p, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(t["headers"] + ["source_url"])
            for r in t["rows"]:
                w.writerow([("" if v is None else v) for v in r] + [t["source"]])
        files.append({"path": f"/data/csv/{t['slug']}.csv", "format": "text/csv", "rows": len(t["rows"]),
                      "title": {lg: v.replace("{n}", str(len(t["rows"]))) for lg, v in CSV_TITLES[t["slug"]].items()},
                      "source": t["source"], "notes": CSV_NOTES[t["slug"]]})
    for lang, name in (("fr", "data.json"), ("en", "data.en.json"), ("de", "data.de.json"), ("lb", "data.lb.json"),
                       ("pt", "data.pt.json")):
        files.append({"path": f"/data/{name}", "format": "application/json", "rows": 0, "lang": lang,
                      "title": JSON_TITLE, "source": DATASET_URL, "notes": {}})
    manifest = {"site": "lux-solaire", "content_date": cdate, "license": LICENSE_URL,
                "sources": [DATASET_URL, RNPP_URL], "files": files}
    (ROOT / "data" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n")
    return manifest


def rt_downloads(manifest, lang):
    """Liste <li> de la boîte à outils : les CSV et le JSON de la locale (titres du manifeste)."""
    items = []
    for f in manifest["files"]:
        if f.get("lang") and f["lang"] != lang:
            continue
        kind = "CSV" if f["format"] == "text/csv" else "JSON"
        items.append(f'<li><a href="{f["path"]}" download>{f["title"][lang]}</a> <small>{kind}</small></li>')
    return "".join(items)


def write_seo(groups):
    """robots.txt + sitemap.xml : chaque page dans ses trois langues avec ses
    alternates hreflang (identiques aux <link rel=alternate> des pages) et un
    lastmod honnête = date de contenu de chaque locale, jamais l'horloge du
    build. `groups` = [(chemins par langue, dates par langue), ...]."""
    (ROOT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n")
    rows = []
    for paths, cdates in groups:
        alts = "".join(f'<xhtml:link rel="alternate" hreflang="{c}" href="{SITE}{p}"/>' for c, p in paths)
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE}{dict(paths)["en"]}"/>'
        rows += [f"<url><loc>{SITE}{p}</loc><lastmod>{cdates[c]}</lastmod>{alts}</url>" for c, p in paths]
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(rows) + "\n</urlset>\n")


# ──────────────── JSON-LD (un seul @graph, construit APRÈS traduction) ──────
PUBLISHED = "2026-07-06"   # premier commit du site (680114d)
PERSON = {"@type": "Person", "@id": "https://sitraka.lu/#person", "name": "Sitraka Forler",
          "url": "https://sitraka.lu/",
          "sameAs": ["https://www.linkedin.com/in/sitraka-matthieu-forler/", "https://github.com/Sitraka17"]}
LUXEMBOURG = {"@type": "Place", "name": "Luxembourg", "sameAs": "https://www.wikidata.org/wiki/Q32"}
DATASET = {
    "name": {"fr": "lux-solaire : indicateurs dérivés du parc photovoltaïque luxembourgeois",
             "en": "lux-solaire: indicators derived from Luxembourg's solar PV fleet",
             "lb": "lux-solaire: Indicateuren ofgeleet vum lëtzebuergesche Photovoltaik-Park",
             "de": "lux-solaire: Kennzahlen aus dem luxemburgischen Photovoltaik-Park",
             "pt": "lux-solaire: indicadores derivados do parque fotovoltaico luxemburguês"},
    "description": {
        "fr": "Capacité photovoltaïque installée par commune et par canton, W par habitant (population RNPP), "
              "ajouts nets entre relevés, mix par filière et histogramme des tailles d'installation, recalculés "
              "à chaque relevé depuis les fichiers Leneda publiés sur data.public.lu (CC0). Données dérivées "
              "sous licence CC BY 4.0, téléchargeables en CSV et JSON.",
        "en": "Installed solar PV capacity by municipality and canton, W per inhabitant (RNPP population), "
              "net additions between readings, technology mix and installation-size histogram, recomputed at "
              "each reading from the Leneda files published on data.public.lu (CC0). Derived data under "
              "CC BY 4.0, downloadable as CSV and JSON.",
        "lb": "Installéiert PV-Kapazitéit pro Gemeng a Kanton, W pro Awunner (RNPP-Populatioun), Netto-Zouwuess "
              "tëscht de Relevéen, Mix vun de Filièren an Histogramm vun de Gréissten, bei all Relevé nei "
              "berechent aus de Leneda-Fichieren op data.public.lu (CC0). Ofgeleet Donnéeën ënner CC BY 4.0, "
              "als CSV a JSON erofzelueden.",
        "de": "Installierte Photovoltaik-Leistung je Gemeinde und Kanton, W pro Einwohner (RNPP-Bevölkerung), "
              "Netto-Zubau zwischen den Erhebungen, Technologie-Mix und Histogramm der Anlagengrößen, bei jeder "
              "Erhebung neu berechnet aus den Leneda-Dateien auf data.public.lu (CC0). Abgeleitete Daten unter "
              "CC BY 4.0, als CSV und JSON herunterladbar.",
        "pt": "Potência fotovoltaica instalada por município e por cantão, W por habitante (população RNPP), "
              "acréscimos líquidos entre levantamentos, mix por tecnologia e histograma das dimensões das "
              "instalações, recalculados em cada levantamento a partir dos ficheiros da Leneda publicados no "
              "data.public.lu (CC0). Dados derivados sob a licença CC BY 4.0, descarregáveis em CSV e JSON."},
    "keywords": {"fr": ["photovoltaïque", "Luxembourg", "communes", "capacité installée", "open data", "Leneda"],
                 "en": ["solar PV", "Luxembourg", "municipalities", "installed capacity", "open data", "Leneda"],
                 "lb": ["Photovoltaik", "Lëtzebuerg", "Gemengen", "installéiert Kapazitéit", "Open Data", "Leneda"],
                 "de": ["Photovoltaik", "Luxemburg", "Gemeinden", "installierte Leistung", "Open Data", "Leneda"],
                 "pt": ["fotovoltaico", "Luxemburgo", "municípios", "potência instalada", "dados abertos", "Leneda"]},
    "variables": {"fr": ["capacité photovoltaïque installée (kW)", "nombre d'installations photovoltaïques",
                         "part du photovoltaïque dans la capacité décentralisée (%)",
                         "variation de capacité depuis le premier relevé trimestriel (kW)",
                         "puissance photovoltaïque par habitant (W)", "installations photovoltaïques pour 1 000 habitants"],
                  "en": ["installed solar PV capacity (kW)", "number of PV installations",
                         "PV share of decentralised capacity (%)", "capacity change since the first quarterly reading (kW)",
                         "PV capacity per inhabitant (W)", "PV installations per 1,000 inhabitants"],
                  "lb": ["installéiert PV-Kapazitéit (kW)", "Zuel vun de PV-Installatiounen",
                         "Undeel vum PV un der dezentraler Kapazitéit (%)", "Ännerung vun der Kapazitéit zanter dem éischte Quartalsrelevé (kW)",
                         "PV-Leeschtung pro Awunner (W)", "PV-Installatioune pro 1 000 Awunner"],
                  "de": ["installierte Photovoltaik-Leistung (kW)", "Zahl der PV-Anlagen",
                         "PV-Anteil an der dezentralen Leistung (%)", "Leistungsänderung seit der ersten Quartalserhebung (kW)",
                         "PV-Leistung pro Einwohner (W)", "PV-Anlagen je 1 000 Einwohner"],
                  "pt": ["potência fotovoltaica instalada (kW)", "número de instalações fotovoltaicas",
                         "parte do fotovoltaico na potência descentralizada (%)",
                         "variação da potência desde o primeiro levantamento trimestral (kW)",
                         "potência fotovoltaica por habitante (W)", "instalações fotovoltaicas por 1 000 habitantes"]},
}


def _grab(pattern, s):
    m = re.search(pattern, s, re.S)
    return html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def jsonld(final_html, lang, canonical, cdate, manifest, d):
    """WebSite + WebPage + Article + Dataset + Person. Titre, description et
    headline sont RELUS dans la page traduite (aucune dérive possible) ;
    seuls nom, description, mots-clés et variables du Dataset viennent de
    DATASET. Dates honnêtes : première mise en ligne + date de contenu."""
    title = _grab(r"<title>(.*?)</title>", final_html)
    desc = _grab(r'<meta\s+name="description"\s+content="([^"]*)"', final_html)
    h1 = _grab(r"<h1[^>]*>(.*?)</h1>", final_html)
    og = _grab(r'<meta\s+property="og:image"\s+content="([^"]*)"', final_html)
    q_labels = [r["label"] for r in d["series"] if re.match(r"^\d{4} [TQ]\d$", r["label"])]
    y, q = q_labels[0][:4], int(q_labels[0][-1])
    temporal = f"{y}-{q * 3:02d}/{d['meta']['date_iso']}"        # fin du 1er trimestre relevé → relevé hebdo
    graph = [
        {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "Lux-Solaire",
         "inLanguage": [c for c, _ in LANG_PATHS], "publisher": {"@id": PERSON["@id"]}},
        {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical, "name": title, "description": desc,
         "inLanguage": lang, "isPartOf": {"@id": SITE + "/#website"},
         "primaryImageOfPage": {"@type": "ImageObject", "url": og},
         "datePublished": PUBLISHED, "dateModified": cdate, "about": {"@id": SITE + "/#dataset"}},
        {"@type": "Article", "@id": canonical + "#article", "mainEntityOfPage": {"@id": canonical + "#webpage"},
         "headline": h1[:110], "description": desc, "inLanguage": lang, "image": og,
         "datePublished": PUBLISHED, "dateModified": cdate,
         "author": {"@id": PERSON["@id"]}, "publisher": {"@id": PERSON["@id"]},
         "isBasedOn": [DATASET_URL, RNPP_URL, SOURCES["ilr"]["url"], SOURCES["pnec"]["url"]], "license": LICENSE_URL},
        {"@type": "Dataset", "@id": SITE + "/#dataset", "url": SITE + "/", "identifier": SITE + "/",
         "name": DATASET["name"][lang], "description": DATASET["description"][lang], "keywords": DATASET["keywords"][lang],
         "license": LICENSE_URL, "isAccessibleForFree": True, "creator": {"@id": PERSON["@id"]},
         "isBasedOn": [DATASET_URL, RNPP_URL], "temporalCoverage": temporal, "spatialCoverage": LUXEMBOURG,
         "dateModified": cdate, "version": cdate, "variableMeasured": DATASET["variables"][lang],
         "distribution": [{"@type": "DataDownload", "name": f["title"][lang], "encodingFormat": f["format"],
                           "contentUrl": SITE + f["path"]} for f in manifest["files"]]},
        PERSON,
    ]
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    return '<script type="application/ld+json">' + payload.replace("<", "\\u003c") + "</script>"


OG_FILES = {"fr": "og.png", "en": "og.en.png", "lb": "og.lb.png", "de": "og.de.png", "pt": "og.pt.png"}
OG_LOCALE = {"fr": "fr_FR", "en": "en_US", "lb": "lb_LU", "de": "de_DE", "pt": "pt_PT"}
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
    "de": ("LUX-SOLAIRE · PHOTOVOLTAIK · OPEN DATA", "Photovoltaik in Luxemburg,", "Gemeinde für Gemeinde",
           "angeschlossene PV-Leistung", "PV-Anlagen · installierte Leistung, nicht Energie",
           "solaire.sitraka.lu · Leneda / data.public.lu (CC0) · DE · FR · EN · LU"),
    "pt": ("LUX-SOLAIRE · FOTOVOLTAICO · DADOS ABERTOS", "A energia fotovoltaica no Luxemburgo,", "município a município",
           "de potência ligada à rede", "instalações fotovoltaicas · potência instalada, não energia",
           "solaire.sitraka.lu · Leneda / data.public.lu (CC0) · PT · FR · EN · DE · LU"),
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
        # le sélecteur de langue lie volontairement les autres langues (href="/fr/simulateur/")
        html = re.sub(r'<ul class="langs".*?</ul>', "", html, count=1, flags=re.S)
        leaks = [k for k, v in dct.items() if v != k and k in html]
        if leaks:
            sys.exit(f"{lang} : {len(leaks)} clés non traduites subsistent :\n  " +
                     "\n  ".join(repr(k[:90]) for k in leaks))


# ──────────────── page simulateur : JSON-LD, og:image ──────────────────────
SIM_PUBLISHED = "2026-10-23"   # première mise en ligne du simulateur
OG_SIM_FILES = {"fr": "og.sim.png", "en": "og.sim.en.png", "lb": "og.sim.lb.png", "de": "og.sim.de.png", "pt": "og.sim.pt.png"}
_OG_SIM_TEXT = {
    "fr": ("LUX-SOLAIRE · SIMULATEUR GRATUIT · SANS INSCRIPTION", "Panneaux solaires au Luxembourg :",
           "est-ce rentable chez vous ?", "par kWc et par an, plein sud à 35° (PVGIS)",
           "Production · Klimabonus 2026 · tarif garanti · retour sur investissement",
           "solaire.sitraka.lu/fr/simulateur/ · FR · EN · LU"),
    "en": ("LUX-SOLAIRE · FREE CALCULATOR · NO SIGN-UP", "Solar panels in Luxembourg:",
           "are they worth it for your home?", "per kWp per year, due south at 35° (PVGIS)",
           "Yield · Klimabonus 2026 · guaranteed tariff · payback time",
           "solaire.sitraka.lu/simulator/ · EN · FR · LU"),
    "lb": ("LUX-SOLAIRE · GRATIS RECHNER · OUNI UMELDUNG", "Solaranlag zu Lëtzebuerg:",
           "rentéiert et sech bei Iech?", "pro kWp a pro Joer, Südden, 35° (PVGIS)",
           "Produktioun · Klimabonus 2026 · garantéierten Tarif · Amortisatioun",
           "solaire.sitraka.lu/lb/rechner/ · LU · FR · EN"),
    "de": ("LUX-SOLAIRE · GRATIS-RECHNER · OHNE ANMELDUNG", "Solaranlagen in Luxemburg:",
           "lohnt es sich bei Ihnen?", "pro kWp und Jahr, Südausrichtung, 35° (PVGIS)",
           "Ertrag · Klimabonus 2026 · garantierter Tarif · Amortisation",
           "solaire.sitraka.lu/de/rechner/ · DE · FR · EN · LU"),
    "pt": ("LUX-SOLAIRE · SIMULADOR GRATUITO · SEM REGISTO", "Painéis solares no Luxemburgo:",
           "compensa na sua casa?", "por kWp e por ano, virado a sul, 35° (PVGIS)",
           "Produção · Klimabonus 2026 · tarifa de injeção · retorno do investimento",
           "solaire.sitraka.lu/pt/simulador/ · PT · FR · EN · DE · LU"),
}


def make_og_sim(pv, lang):
    """og:image du simulateur : productible de référence PVGIS en grand."""
    try:
        from PIL import Image, ImageDraw
        eyebrow, l1, l2, kwc_label, mid_label, foot = _OG_SIM_TEXT[lang]
        serif = _font(_FONT_SERIF, 64)
        big, mid, small = _font(_FONT_SANS, 120), _font(_FONT_SANS, 36), _font(_FONT_SANS, 30)
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
        ref = _thousands(pv["grid"]["0:35"], lang) + " kWh"
        dr.text((80, 296), ref, font=big, fill="#C77F00")
        dr.text((80, 428), kwc_label, font=fit(kwc_label, mid), fill="#5A6472")
        dr.text((80, 486), mid_label, font=fit(mid_label, small), fill="#5A6472")
        dr.text((80, 556), foot, font=small, fill="#6B7380")
        img.save(ROOT / OG_SIM_FILES[lang])
        return True
    except Exception as e:  # noqa: BLE001
        print(f"attention : {OG_SIM_FILES[lang]} non régénéré ({e.__class__.__name__}: {e})", file=sys.stderr)
        return False


def _text(s):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def jsonld_sim(final_html, lang, canonical, cdate, pv):
    """WebSite + WebPage + BreadcrumbList + WebApplication + FAQPage + Person.
    Titre, description, fil d'Ariane et questions/réponses sont RELUS dans la
    page traduite (la FAQ affichée et la FAQ structurée ne peuvent pas diverger)."""
    title = _grab(r"<title>(.*?)</title>", final_html)
    desc = _grab(r'<meta\s+name="description"\s+content="([^"]*)"', final_html)
    og = _grab(r'<meta\s+property="og:image"\s+content="([^"]*)"', final_html)
    m = re.search(r'<nav class="crumbs"[^>]*><ol><li><a href="([^"]*)">(.*?)</a></li><li aria-current="page">(.*?)</li></ol></nav>',
                  final_html, re.S)
    home_path, home_name, here = m.group(1), _text(m.group(2)), _text(m.group(3))
    faq_sec = re.search(r'<section id="faq".*?</section>', final_html, re.S).group(0)
    qa = re.findall(r"<summary>(.*?)</summary>\s*<p>(.*?)</p>", faq_sec, re.S)
    if len(qa) < 5:
        sys.exit(f"{lang} : FAQ du simulateur incomplète ({len(qa)} questions)")
    graph = [
        {"@type": "WebSite", "@id": SITE + "/#website", "url": SITE + "/", "name": "Lux-Solaire",
         "inLanguage": [c for c, _ in SIM_PATHS], "publisher": {"@id": PERSON["@id"]}},
        {"@type": "WebPage", "@id": canonical + "#webpage", "url": canonical, "name": title, "description": desc,
         "inLanguage": lang, "isPartOf": {"@id": SITE + "/#website"},
         "primaryImageOfPage": {"@type": "ImageObject", "url": og},
         "breadcrumb": {"@id": canonical + "#breadcrumb"},
         "datePublished": SIM_PUBLISHED, "dateModified": cdate, "mainEntity": {"@id": canonical + "#app"}},
        {"@type": "BreadcrumbList", "@id": canonical + "#breadcrumb", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": home_name, "item": SITE + home_path},
            {"@type": "ListItem", "position": 2, "name": here, "item": canonical}]},
        {"@type": "WebApplication", "@id": canonical + "#app", "name": title, "url": canonical, "description": desc,
         "applicationCategory": "FinanceApplication", "operatingSystem": "Web browser",
         "browserRequirements": "Requires JavaScript", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
         "inLanguage": lang, "image": og, "datePublished": SIM_PUBLISHED, "dateModified": cdate,
         "author": {"@id": PERSON["@id"]}, "publisher": {"@id": PERSON["@id"]},
         "areaServed": LUXEMBOURG,
         "isBasedOn": [pv["url"], "https://guichet.public.lu/fr/citoyens/aides/logement-construction/klimabonus-2026/aide-installations-techniques.html",
                       "https://legilux.public.lu/eli/etat/leg/rgd/2014/08/01/n1/jo", DATASET_URL]},
        {"@type": "FAQPage", "@id": canonical + "#faq", "mainEntity": [
            {"@type": "Question", "name": _text(q), "acceptedAnswer": {"@type": "Answer", "text": _text(a)}} for q, a in qa]},
        PERSON,
    ]
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    return '<script type="application/ld+json">' + payload.replace("<", "\\u003c") + "</script>"


def write_ev_allowlist(communes_fr, checked):
    """Listes blanches du compteur /e (functions/e.js) : slugs RÉELS des communes et fichiers
    de données réellement liés depuis les pages. Fichier généré, réécrit seulement s'il change
    (functions/ est compilé par wrangler, jamais copié dans le dist)."""
    slugs = sorted({_slug(c["c"]) for c in communes_fr})
    files = sorted({m.split("/")[-1] for _, html, _, _ in checked
                    for m in re.findall(r'href="(/data/[^"]+\.(?:csv|json))"', html)})
    js = ("// GÉNÉRÉ par scripts/build.py (write_ev_allowlist) : ne pas éditer à la main.\n"
          "// Listes blanches du compteur /e : slugs réels des communes, fichiers de données liés.\n"
          f"export const SLUGS = new Set({json.dumps(slugs)});\n"
          f"export const FILES = new Set({json.dumps(files)});\n")
    out = ROOT / "functions" / "_allow.js"
    if not out.exists() or out.read_text() != js:
        out.write_text(js)


def render_all(data):
    """Écrit les JSON dérivés (EN, DE, LB, PT) et les dix pages (tableau de bord
    et simulateur, cinq langues chacun) depuis le blob FR, puis les pages communales."""
    # endpoint public : la source reste en FR ; variantes EN, LB, DE et PT pour réutilisation
    data_en = translate_data(data)
    (ROOT / "data" / "data.en.json").write_text(json.dumps(data_en, ensure_ascii=False))
    data_lb = translate_data(data, _tr_str_lb)
    (ROOT / "data" / "data.lb.json").write_text(json.dumps(data_lb, ensure_ascii=False))
    data_de = translate_data(data, _tr_str_de)
    (ROOT / "data" / "data.de.json").write_text(json.dumps(data_de, ensure_ascii=False))
    data_pt = translate_data(data, _tr_str_pt)
    (ROOT / "data" / "data.pt.json").write_text(json.dumps(data_pt, ensure_ascii=False))
    pv = json.loads((ROOT / "data" / "pvgis.json").read_text())
    for lang in DASH_LANGS:
        make_og(data, lang)
    for lang in SIM_LANGS:
        make_og_sim(pv, lang)
    tpl, tpl_sim = load_templates()
    check_dicts(tpl + "\n" + tpl_sim)
    for name, t in (("template.html", tpl), ("template_simulateur.html", tpl_sim)):
        if "—" in t:
            sys.exit(f"{name} contient un tiret cadratin (U+2014)")
    # date de contenu par page et par langue, puis exports (le manifeste porte la plus récente)
    rt_js = (ROOT / "rt.js").read_text()
    grandes_src = (ROOT / "scripts" / "grandes.py").read_text()   # textes du bloc « grandes installations »
    # moteur du simulateur (fonctions pures) : servi à part, version = empreinte du contenu
    # son bloc BAREMES est régénéré depuis scripts/baremes.json (source unique) avant l'empreinte
    sim_engine = baremes.sync_engine(ROOT / "sim-engine.js")
    bar_txt = baremes.PATH.read_text()
    bar_json = json.dumps(baremes.engine_bar(), ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    sim_engine_v = hashlib.sha256(sim_engine.encode()).hexdigest()[:10]
    pre_sim = sim_prerender()   # scénario par défaut + 3 profils, par le moteur JS (node)
    dict_txt = {"fr": "", **{lang: "".join((ROOT / "scripts" / n).read_text() for n in names)
                            for lang, names in I18N_FILES.items()}}
    # tableau de bord : ses seuls dictionnaires, sans ceux du simulateur (une clé ajoutée
    # au simulateur ne doit pas rajeunir la date du jeu de données ni le manifeste)
    dict_dash = {"fr": "", **{lang: "".join((ROOT / "scripts" / n).read_text() for n in names
                                            if not n.startswith("i18n_sim_"))
                              for lang, names in I18N_FILES.items()}}
    blobs = {"fr": data, "en": data_en, "de": data_de, "lb": data_lb, "pt": data_pt}
    pv_txt = json.dumps(pv, sort_keys=True)
    cdates = {lang: content_date(lang, [tpl, dict_dash[lang], json.dumps(blobs[lang], ensure_ascii=False, sort_keys=True),
                                        rt_js, KIT_VERSION, bar_txt, grandes_src]) for lang in DASH_LANGS}
    cdates_sim = {lang: content_date("sim_" + lang, [tpl_sim, sim_engine, bar_txt, dict_txt[lang], pv_txt,
                                                     json.dumps({"meta": blobs[lang]["meta"], "cantons": blobs[lang]["cantons"]},
                                                                ensure_ascii=False, sort_keys=True),
                                                     rt_js, KIT_VERSION]) for lang in SIM_LANGS}
    manifest = write_exports(exports(data), max(cdates.values()))
    write_seo([(LANG_PATHS, cdates), (SIM_PATHS, cdates_sim)])

    F_GB = ('<svg width="16" height="11" viewBox="0 0 60 44" aria-hidden="true" focusable="false">'
            '<rect width="60" height="44" fill="#012169"/>'
            '<path d="M0 0 60 44M60 0 0 44" stroke="#fff" stroke-width="9"/>'
            '<path d="M0 0 60 44M60 0 0 44" stroke="#C8102E" stroke-width="4"/>'
            '<path d="M30 0V44M0 22H60" stroke="#fff" stroke-width="15"/>'
            '<path d="M30 0V44M0 22H60" stroke="#C8102E" stroke-width="8"/></svg>')
    F_FR = ('<svg width="16" height="11" viewBox="0 0 60 44" aria-hidden="true" focusable="false">'
            '<rect width="20" height="44" fill="#0055A4"/>'
            '<rect x="20" width="20" height="44" fill="#fff"/>'
            '<rect x="40" width="20" height="44" fill="#EF4135"/></svg>')
    F_LU = ('<svg width="16" height="11" viewBox="0 0 60 44" aria-hidden="true" focusable="false">'
            '<rect width="60" height="15" fill="#EF3340"/>'
            '<rect y="15" width="60" height="14" fill="#fff"/>'
            '<rect y="29" width="60" height="15" fill="#00A2E1"/></svg>')
    F_DE = ('<svg width="16" height="11" viewBox="0 0 60 44" aria-hidden="true" focusable="false">'
            '<rect width="60" height="15" fill="#000"/>'
            '<rect y="15" width="60" height="14" fill="#DD0000"/>'
            '<rect y="29" width="60" height="15" fill="#FFCE00"/></svg>')
    # drapeau portugais simplifié (vert 2/5, rouge 3/5, sphère armillaire réduite à un disque jaune)
    F_PT = ('<svg width="16" height="11" viewBox="0 0 60 44" aria-hidden="true" focusable="false">'
            '<rect width="24" height="44" fill="#046A38"/>'
            '<rect x="24" width="36" height="44" fill="#DA291C"/>'
            '<circle cx="24" cy="22" r="9" fill="#FFE900"/>'
            '<circle cx="24" cy="22" r="5" fill="#DA291C" stroke="#fff" stroke-width="1.5"/></svg>')
    _FLAG = {"en": F_GB, "fr": F_FR, "de": F_DE, "lb": F_LU, "pt": F_PT}

    def render(d, lang, sim):
        t, paths = (tpl_sim, SIM_PATHS) if sim else (tpl, LANG_PATHS)
        canonical = SITE + dict(paths)[lang]
        cdate = (cdates_sim if sim else cdates)[lang]
        # le simulateur n'embarque que le nécessaire (relevé et cantons), pas les 100 communes
        blob = json.dumps({"meta": d["meta"], "cantons": d["cantons"]} if sim else d,
                          ensure_ascii=False).replace("<", "\\u003c")
        toggle = ossature.lang_nav(paths, lang, _FLAG)
        og_locale = f'<meta property="og:locale" content="{OG_LOCALE[lang]}">' + "".join(
            f'<meta property="og:locale:alternate" content="{OG_LOCALE[c]}">'
            for c, _ in paths if c != lang)
        html = (t.replace("/*__DATA__*/", blob)
                 .replace("/*__PVGIS__*/", json.dumps(pv, ensure_ascii=False).replace("<", "\\u003c"))
                 .replace("__LANG__", HTML_LANG.get(lang, lang))
                 .replace("__CANONICAL_ENC__", urllib.parse.quote(canonical, safe=""))
                 .replace("__CONTENT_DATE__", cdate)
                 .replace("__CANONICAL__", canonical)
                 .replace("__OGIMAGE__", (OG_SIM_FILES if sim else OG_FILES)[lang])
                 .replace("<!--OGLOCALE-->", og_locale)
                 .replace("__CPATH__", CPATH[lang])
                 .replace("__FORPATH__", FORPATH[lang]))
        dct = None
        if lang == "en":
            html, dct = to_en(html), I18N
        elif lang == "lb":
            html, dct = to_lb(html), I18N_LB
        elif lang == "de":
            html, dct = to_de(html), I18N_DE
        elif lang == "pt":
            html, dct = to_pt(html), I18N_PT
        # sélecteur de langue APRÈS traduction : sinon la clé href="/fr/simulateur/" des
        # dictionnaires réécrivait aussi le lien FR du sélecteur (lien FR du simulateur
        # EN/DE/LB/PT pointant vers la page elle-même, corrigé le 9/11/2026)
        html = html.replace("<!--LANGTOGGLE-->", toggle)
        # jetons de prose (dont __DATE__) : APRÈS traduction, pour que les clés
        # des dictionnaires puissent les contenir
        for token, value in prose_numbers(d, lang).items():
            html = html.replace(token, value)
        if sim:
            html = html.replace("__SIMENGINE_V__", sim_engine_v)
            html = (html.replace("__BAREMES_JSON__", bar_json)
                        .replace("__HEMS_MAX__", str(baremes.B["aide_hems"]["valeur"]["aideMax"])))
            for token, value in sim_numbers(lang).items():
                html = html.replace(token, value)
            html = sim_static(html, lang, d, tpl_sim, pre_sim)
        # fragments prérendus (déjà localisés) : après traduction et jetons
        if not sim:
            for marker, frag in prerender(d, lang).items():
                if marker not in html:
                    sys.exit(f"{lang} : marqueur {marker} absent du gabarit")
                html = html.replace(marker, frag)
        html = html.replace("<!--RT_DOWNLOADS-->", rt_downloads(manifest, lang))
        # JSON-LD en dernier : il relit le <title>, la description et le <h1> traduits
        if "<!--JSONLD-->" not in html:
            sys.exit(f"{lang} : marqueur <!--JSONLD--> absent du gabarit")
        ld = jsonld_sim(html, lang, canonical, cdate, pv) if sim else jsonld(html, lang, canonical, cdate, manifest, d)
        html = html.replace("<!--JSONLD-->", ld)
        if "<!--" in html and re.search(r"<!--(PRE_|RT_|JSONLD|OGLOCALE|LANGTOGGLE)", html):
            sys.exit(f"{lang} : marqueur de gabarit non substitué")
        check_output(html, lang, dct)
        return html

    checked = []   # (nom, html, langue, type) : contrôle des chiffres de barème cités
    for sim, paths in ((False, LANG_PATHS), (True, SIM_PATHS)):
        for lang, path in paths:
            out = ROOT / path.strip("/") / "index.html" if path.strip("/") else ROOT / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            page = render(blobs[lang], lang, sim)
            out.write_text(page)
            checked.append((str(out.relative_to(ROOT)), page, lang, "sim" if sim else "dash"))
    # pages par commune et « Pour les communes » (reprennent le style des pages rendues)
    import communes
    csrc = (ROOT / "scripts" / "communes.py").read_text() + (ROOT / "scripts" / "ossature.py").read_text()
    cdates_c = {lang: content_date("communes_" + lang, [csrc, json.dumps(blobs[lang], ensure_ascii=False, sort_keys=True),
                                                        KIT_VERSION, bar_txt, grandes_src]) for lang in DASH_LANGS}
    groups_c = communes.write_all(ROOT, SITE, blobs, cdates_c, _thousands, _dec1, PERSON, LUXEMBOURG, _FLAG, _jsround)
    for lang in DASH_LANGS:
        for f in sorted((ROOT / communes.CPATH[lang].strip("/")).glob("*/index.html")):
            checked.append((str(f.relative_to(ROOT)), f.read_text(), lang, "commune"))
        f = ROOT / communes.FORPATH[lang].strip("/") / "index.html"
        checked.append((str(f.relative_to(ROOT)), f.read_text(), lang, "info"))
    write_ev_allowlist(blobs["fr"]["communes"], checked)
    problems = baremes.check_pages(checked)
    if problems:
        sys.exit("chiffres de barème cités qui ne correspondent plus à scripts/baremes.json "
                 "(corriger la phrase dans le gabarit, les dictionnaires i18n ou communes.py) :\n  "
                 + "\n  ".join(problems[:40]) + (f"\n  … et {len(problems) - 40} autres" if len(problems) > 40 else ""))
    print(f"barèmes : {len(checked)} pages contrôlées contre scripts/baremes.json (version {baremes.B['version']})")
    write_seo([(LANG_PATHS, cdates), (SIM_PATHS, cdates_sim)] + groups_c)
    print(f"{len(groups_c) * len(DASH_LANGS)} pages communales et « pour les communes » écrites "
          f"({len(groups_c)} × {'/'.join(DASH_LANGS)})")
    print(f"{len(LANG_PATHS) + len(SIM_PATHS)} pages rebuilt (tableau de bord et simulateur × {'/'.join(SIM_LANGS)}) : "
          f"PV {data['meta']['pv_mw']} MW au {data['meta']['date']} / "
          f"as of {data_en['meta']['date']} / Stand (DE) {data_de['meta']['date']} / "
          f"Stand (LB) {data_lb['meta']['date']} / PT {data_pt['meta']['date']}")


def main():
    frames, wdate, ng = fetch_resources()
    check_leneda(frames, ng)
    archive_snapshot(ng, wdate)
    pop, pop_date = fetch_population()
    data = build(frames, wdate, ng, pop, pop_date, load_baseline(wdate), load_archives(wdate))
    check_claims(data)
    (ROOT / "data" / "data.json").write_text(json.dumps(data, ensure_ascii=False))
    render_all(data)


if __name__ == "__main__":
    main()
