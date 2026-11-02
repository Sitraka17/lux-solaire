#!/usr/bin/env python3
"""Année météo type HORAIRE à Luxembourg-Ville d'après PVGIS 5.3 seriescalc (JRC, Commission
européenne), base SARAH3 (rayonnement) et ERA5 (température), 2005-2023, pour le volet chauffage
du moteur sim-engine.js (computeHeat). Le moteur ne lit aucun fichier : la page ou le test charge
data/annee_type.json et le passe en paramètre.

Choix de l'année : celle dont la production PV annuelle ET les degrés-jours de chauffage (base 15 °C,
sur la moyenne journalière) sont les plus proches de la moyenne 2005-2023 (somme des écarts
normalisés au carré). Plan sud, inclinaison 35°, pertes système 14 % (comme data/pvgis.json).
Heure d'hiver (UTC+1) toute l'année : la série UTC est décalée d'une heure (la dernière heure de
l'année reprend la première heure UTC du 1er janvier).

Sortie : data/annee_type.json { pv_w_par_kwc[8760] (W par kWc, entiers), t2m_dixiemes[8760]
(°C × 10, entiers), métadonnées }. Lancer à la main, rarement.

Usage : /usr/bin/python3 scripts/fetch_annee_type.py
"""
import json
import statistics
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
CENTER = (49.61, 6.13)   # Luxembourg-Ville, même point que data/pvgis.json
PARAMS = {"lat": CENTER[0], "lon": CENTER[1], "raddatabase": "PVGIS-SARAH3", "startyear": 2005,
          "endyear": 2023, "pvcalculation": 1, "peakpower": 1, "loss": 14, "angle": 35, "aspect": 0,
          "outputformat": "json"}


def fetch():
    for attempt in range(4):
        try:
            r = requests.get(API, params=PARAMS, timeout=180)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            print(f"  retry {attempt + 1} ({e})", file=sys.stderr)
            time.sleep(5)
    sys.exit("PVGIS indisponible")


def main():
    raw = fetch()
    years = {}
    for r in raw["outputs"]["hourly"]:
        years.setdefault(int(r["time"][:4]), []).append(r)
    stats = {}
    for y, rs in years.items():
        pv = sum(r["P"] for r in rs) / 1000
        days = {}
        for r in rs:
            days.setdefault(r["time"][:8], []).append(r["T2m"])
        hdd = sum(max(0, 15 - sum(v) / len(v)) for v in days.values())
        stats[y] = (pv, hdd, len(rs))
    mpv = statistics.mean(s[0] for s in stats.values())
    spv = statistics.pstdev(s[0] for s in stats.values())
    mh = statistics.mean(s[1] for s in stats.values())
    sh = statistics.pstdev(s[1] for s in stats.values())
    score = {y: ((s[0] - mpv) / spv) ** 2 + ((s[1] - mh) / sh) ** 2 for y, s in stats.items() if s[2] == 8760}
    for y in sorted(stats):
        print(y, round(stats[y][0]), round(stats[y][1]), round(score.get(y, 99), 2))
    best = min(score, key=score.get)
    rs = years[best]
    pv = [round(r["P"]) for r in rs]
    t = [round(r["T2m"] * 10) for r in rs]
    pv, t = pv[-1:] + pv[:-1], t[-1:] + t[:-1]
    url = API + "?" + "&".join(f"{k}={v}" for k, v in PARAMS.items())
    out = {"source": "PVGIS 5.3 seriescalc, JRC (Commission européenne)", "url": url,
           "lieu": "Luxembourg-Ville (49,61 N ; 6,13 E)",
           "radiation_db": raw["inputs"]["meteo_data"]["radiation_db"],
           "meteo_db": raw["inputs"]["meteo_data"]["meteo_db"], "annee": best,
           "periode": [min(years), max(years)], "pv_moyen_kwh_kwc": round(mpv), "dj15_moyen": round(mh),
           "pv_annee_kwh_kwc": round(stats[best][0]), "dj15_annee": round(stats[best][1]),
           "plan": "sud, inclinaison 35°, pertes système 14 %", "heure": "UTC+1 (heure d'hiver toute l'année)",
           "telecharge_le": time.strftime("%Y-%m-%d"),
           "pv_w_par_kwc": pv, "t2m_dixiemes": t}
    (ROOT / "data" / "annee_type.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"moyenne {round(mpv)} kWh/kWc, {round(mh)} DJ15 ; année retenue {best} ; data/annee_type.json écrit")


if __name__ == "__main__":
    main()
