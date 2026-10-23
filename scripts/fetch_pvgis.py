#!/usr/bin/env python3
"""Productible photovoltaïque au Luxembourg d'après PVGIS (JRC, Commission
européenne), base SARAH3, pour le simulateur de la page.

Deux tables, écrites dans data/pvgis.json :
  - grid    : kWh/kWc/an à Luxembourg-Ville pour chaque couple
              (azimut, inclinaison) ; azimut PVGIS : 0 = sud, -90 = est, 90 = ouest ;
  - cantons : kWh/kWc/an au centre de chaque canton pour un plan sud à 35°,
              rapporté à Luxembourg-Ville (facteur régional).
Pertes système : 14 % (valeur par défaut PVGIS). Lancer à la main, rarement :
le productible climatologique ne change pas d'une semaine à l'autre.

Usage : /usr/bin/python3 scripts/fetch_pvgis.py
"""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
LOSS = 14
CENTER = (49.61, 6.13)   # Luxembourg-Ville
AZIMUTHS = [-90, -60, -45, -30, 0, 30, 45, 60, 90]
TILTS = [0, 10, 20, 30, 35, 40, 50, 60, 90]
CANTONS = {
    "Capellen": (49.645, 5.99), "Clervaux": (50.05, 6.03), "Diekirch": (49.87, 6.16),
    "Echternach": (49.81, 6.42), "Esch": (49.50, 5.98), "Grevenmacher": (49.68, 6.44),
    "Luxembourg": (49.61, 6.13), "Mersch": (49.75, 6.10), "Redange": (49.76, 5.89),
    "Remich": (49.54, 6.37), "Vianden": (49.93, 6.20), "Wiltz": (49.97, 5.93),
}


def pvcalc(lat, lon, angle, aspect):
    for attempt in range(4):
        try:
            r = requests.get(API, params={"lat": lat, "lon": lon, "peakpower": 1, "loss": LOSS,
                                          "angle": angle, "aspect": aspect, "outputformat": "json"}, timeout=60)
            r.raise_for_status()
            o = r.json()["outputs"]
            return {"E_y": round(o["totals"]["fixed"]["E_y"]), "monthly": [round(m["E_m"]) for m in o["monthly"]["fixed"]],
                    "db": r.json()["inputs"]["meteo_data"]["radiation_db"],
                    "years": [r.json()["inputs"]["meteo_data"]["year_min"], r.json()["inputs"]["meteo_data"]["year_max"]]}
        except Exception as e:  # noqa: BLE001
            print(f"  retry {attempt + 1} ({e})", file=sys.stderr)
            time.sleep(3)
    sys.exit("PVGIS indisponible")


def main():
    grid = {}
    meta = None
    for az in AZIMUTHS:
        for tilt in TILTS:
            if tilt == 0 and az != 0:
                continue   # un plan horizontal n'a pas d'azimut
            res = pvcalc(*CENTER, tilt, az)
            grid[f"{az}:{tilt}"] = res["E_y"]
            meta = meta or {"db": res["db"], "years": res["years"]}
            print(f"az {az:4d} tilt {tilt:2d} : {res['E_y']} kWh/kWc", flush=True)
    ref = pvcalc(*CENTER, 35, 0)
    cantons = {}
    for name, (lat, lon) in CANTONS.items():
        res = pvcalc(lat, lon, 35, 0)
        cantons[name] = {"E_y": res["E_y"], "factor": round(res["E_y"] / ref["E_y"], 3)}
        print(f"{name:13s}: {res['E_y']} kWh/kWc (x{cantons[name]['factor']})", flush=True)
    out = {"source": "PVGIS 5.3, JRC (Commission européenne)", "url": "https://re.jrc.ec.europa.eu/pvg_tools/fr/",
           "radiation_db": meta["db"], "years": meta["years"], "system_loss_pct": LOSS,
           "center": {"name": "Luxembourg-Ville", "lat": CENTER[0], "lon": CENTER[1]},
           "azimuths": AZIMUTHS, "tilts": TILTS, "grid": grid,
           "monthly_ref": ref["monthly"], "cantons": cantons}
    (ROOT / "data" / "pvgis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print("data/pvgis.json écrit")


if __name__ == "__main__":
    main()
