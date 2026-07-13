#!/usr/bin/env python3
"""Rebuild the Lux-Solaire dashboard from the latest Leneda open data.

Downloads the quarterly + weekly CSVs from data.public.lu, recomputes the
aggregates, and injects them into template.html -> index.html.

Usage:  python3 scripts/build.py
Deps:   pandas, requests
"""
import io
import json
import re
import sys
from datetime import date
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

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
             "août", "septembre", "octobre", "novembre", "décembre"]


def fetch_resources():
    """Return {label: dataframe} for quarterly commune files + weekly commune file."""
    meta = requests.get(DATASET_API, timeout=30).json()
    quarterly, weekly = {}, None
    for r in meta["resources"]:
        title = r["title"]
        m = re.match(r"open-data-power-generation-q(\d)-(\d{4})\.csv", title)
        if m:
            q, y = m.group(1), m.group(2)
            quarterly[f"{y} T{q}"] = r["url"]
        elif re.match(r"open-data-power-generation-weekly-.*-commune\.csv", title):
            m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", title)
            weekly = (date(*map(int, m2.groups())), r["url"])
    frames = {}
    for label in sorted(quarterly):
        frames[label] = pd.read_csv(io.BytesIO(requests.get(quarterly[label], timeout=30).content))
    if weekly is None:
        sys.exit("no weekly commune file found in dataset")
    wdate, wurl = weekly
    wlabel = f"{wdate.day} {MONTHS_FR[wdate.month - 1][:4]}. {wdate.year}" if wdate.month != 5 \
        else f"{wdate.day} mai {wdate.year}"
    frames[wlabel] = pd.read_csv(io.BytesIO(requests.get(wurl, timeout=30).content))
    return frames, wdate


def build(frames, wdate):
    labels = list(frames)
    series = []
    for label, df in frames.items():
        row = {"label": label}
        for t in TECHS:
            row[SHORT[t]] = round(pd.to_numeric(df[t + " Performance [kW]"]).sum() / 1000, 2)
        row["pv_count"] = int(pd.to_numeric(df["Installation photovoltaïque Producteur [#]"]).sum())
        series.append(row)

    latest, first = frames[labels[-1]].copy(), frames[labels[0]]
    for df in (latest,):
        for t in TECHS:
            df[t + " Performance [kW]"] = pd.to_numeric(df[t + " Performance [kW]"])
    latest["total_kw"] = sum(latest[t + " Performance [kW]"] for t in TECHS)
    pv0 = first.set_index("LAU2")["Installation photovoltaïque Performance [kW]"]

    communes = []
    for _, r in latest.iterrows():
        pv = r["Installation photovoltaïque Performance [kW]"]
        base = float(pv0.get(r["LAU2"], 0))
        communes.append({
            "c": r["Commune"], "k": r["Canton"],
            "pv": round(pv, 1),
            "n": int(r["Installation photovoltaïque Producteur [#]"]),
            "tot": round(r["total_kw"], 1),
            "share": round(pv / r["total_kw"] * 100, 1) if r["total_kw"] > 0 else 0,
            "g": round(pv - base, 1),
            "gp": round((pv / base - 1) * 100, 1) if base > 0 else None,
            "wind": round(r["Eolienne Performance [kW]"], 1),
            "hydro": round(r["Installation hydroélectrique Performance [kW]"], 1),
            "chp": round(r["Cogénération Performance [kW]"], 1),
            "bio": round(r["Biogaz Performance [kW]"] + r["Biomasse Performance [kW]"], 1),
        })
    communes.sort(key=lambda x: -x["pv"])

    # size histogram needs the not-grouped weekly file
    meta = requests.get(DATASET_API, timeout=30).json()
    ng_url = next(r["url"] for r in meta["resources"] if "not-grouped" in r["title"])
    ng = pd.read_csv(io.BytesIO(requests.get(ng_url, timeout=60).content))
    ng["p"] = pd.to_numeric(ng["Puissance installée [kW]"])
    pv_inst = ng[ng["Type d'installation"] == "Installation photovoltaïque"]
    bins = [0, 5, 10, 15, 30, 100, 500, 1000, 5000, 1e9]
    bin_labels = ["0–5", "5–10", "10–15", "15–30", "30–100", "100–500",
                  "0,5–1 MW", "1–5 MW", ">5 MW"]
    cut = pd.cut(pv_inst["p"], bins=bins, labels=bin_labels)
    hist = pv_inst.groupby(cut, observed=True).agg(count=("p", "size"), cap=("p", "sum"))
    sizes = [{"bin": str(i), "count": int(r["count"]), "mw": round(r["cap"] / 1000, 1)}
             for i, r in hist.iterrows()]

    return {
        "series": series,
        "communes": communes,
        "sizes": sizes,
        "meta": {
            "pv_mw": round(latest["Installation photovoltaïque Performance [kW]"].sum() / 1000, 1),
            "total_mw": round(latest["total_kw"].sum() / 1000, 1),
            "pv_n": int(latest["Installation photovoltaïque Producteur [#]"].sum()),
            "date": f"{wdate.day}{'er' if wdate.day == 1 else ''} {MONTHS_FR[wdate.month - 1]} {wdate.year}",
        },
    }


SITE = "https://lux-solaire.vercel.app"

# ─────────────────────────── i18n (EN par défaut, FR sur /fr) ──────────────
# Deux dictionnaires FR→EN : i18n_en.json (texte statique du HTML) et
# i18n_js.json (chaînes construites en JS). Le HTML anglais s'obtient par
# remplacement « plus longue clé d'abord » ; les libellés d'affichage des
# DONNÉES (mois, trimestres, virgule décimale) sont traduits séparément.
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
_FR2EN_MONTH = {fr: MONTHS_EN[i] for i, fr in enumerate(MONTHS_FR)}
_MONTH_RE = re.compile(r"\b(" + "|".join(MONTHS_FR) + r")\b")
# abréviations produites par fetch_resources : MONTHS_FR[m-1][:4] + "." — mai
# reste un mot entier (géré par _MONTH_RE), donc exclu de la table d'abréviations
_ABBR = {(MONTHS_FR[i][:4] + "."): MONTHS_EN[i][:3] for i in range(12) if i != 4}


def _load_i18n():
    d = json.loads((ROOT / "scripts" / "i18n_en.json").read_text())
    d.update(json.loads((ROOT / "scripts" / "i18n_js.json").read_text()))
    pairs = sorted(d.items(), key=lambda kv: -len(kv[0]))   # plus longue d'abord
    return d, pairs


I18N, I18N_PAIRS = _load_i18n()


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


def translate_data(obj):
    if isinstance(obj, dict):
        return {k: translate_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_data(v) for v in obj]
    if isinstance(obj, str):
        return _tr_str(obj)
    return obj


def to_en(html):
    """HTML anglais : dictionnaire (plus longue clé d'abord), puis bascule des
    littéraux JS couplés à la langue (locale des nombres, virgule décimale)."""
    for fr, en in I18N_PAIRS:
        if fr in html:
            html = html.replace(fr, en)
    return (html.replace("'fr-FR'", "'en-US'")
                .replace(".replace('.',',')", ""))


def main():
    frames, wdate = fetch_resources()
    data = build(frames, wdate)
    (ROOT / "data" / "data.json").write_text(json.dumps(data, ensure_ascii=False))
    # endpoint public : la source reste en FR ; variante EN pour réutilisation
    data_en = translate_data(data)
    (ROOT / "data" / "data.en.json").write_text(json.dumps(data_en, ensure_ascii=False))
    tpl = (ROOT / "template.html").read_text()

    def render(d, lang):
        blob = json.dumps(d, ensure_ascii=False)
        canonical = SITE + ("/" if lang == "en" else "/fr")
        toggle = ('<a href="/" class="cur">EN</a><a href="/fr">FR</a>'
                  if lang == "en" else
                  '<a href="/">EN</a><a href="/fr" class="cur">FR</a>')
        html = (tpl.replace("/*__DATA__*/", blob)
                   .replace("__DATE__", d["meta"]["date"])
                   .replace("__LANG__", lang)
                   .replace("__CANONICAL__", canonical)
                   .replace("<!--LANGTOGGLE-->", toggle))
        return to_en(html) if lang == "en" else html

    (ROOT / "index.html").write_text(render(data_en, "en"))    # EN par défaut
    (ROOT / "fr").mkdir(exist_ok=True)
    (ROOT / "fr" / "index.html").write_text(render(data, "fr"))
    print(f"index.html (EN) + fr/index.html rebuilt — PV {data['meta']['pv_mw']} MW "
          f"au {data['meta']['date']} / as of {data_en['meta']['date']}")


if __name__ == "__main__":
    main()
