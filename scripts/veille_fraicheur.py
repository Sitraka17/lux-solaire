"""Veille de fraîcheur EXTERNE de solaire.sitraka.lu (workflow .github/workflows/fraicheur.yml).

Contrôle le site EN LIGNE, indépendamment du build : il voit donc aussi un rebuild du lundi qui
n'a pas tourné du tout et une panne de Cloudflare Pages après un déploiement réussi.
Échec (exit 1, donc e-mail GitHub d'échec de workflow) si :
- https://solaire.sitraka.lu/data/data.json ne répond pas 200, n'est pas du JSON, ou si
  `meta.date_iso` (date du relevé Leneda) a plus de MAX_AGE_DAYS jours ;
- la page d'accueil ou le simulateur (EN et FR) ne répondent pas 200.

Bibliothèque standard seulement (aucune dépendance pip). Lancement local :
    /usr/bin/python3 scripts/veille_fraicheur.py
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

BASE = "https://solaire.sitraka.lu"
DATA = "/data/data.json"
PAGES = ("/", "/simulator/", "/fr/", "/fr/simulateur/")
# même seuil que le garde-fou du build (build.MAX_AGE_DAYS) : le relevé du lundi est en ligne le
# lundi après-midi, un âge de 8 à 10 jours signale déjà un lundi manqué
MAX_AGE_DAYS = 10
UA = "lux-solaire-veille/1 (+https://github.com/Sitraka17/lux-solaire)"


def fetch(url, timeout=30):
    """(statut HTTP, corps en octets) ; statut 0 si la connexion échoue."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"  {url} : {e}", file=sys.stderr)
        return 0, b""


def check_data(status, body, today):
    """Liste des problèmes du fichier de données (vide si tout va bien) et date du relevé."""
    if status != 200:
        return [f"{DATA} : HTTP {status}"], None
    try:
        d = date.fromisoformat(json.loads(body)["meta"]["date_iso"])
    except (ValueError, KeyError, TypeError) as e:
        return [f"{DATA} : meta.date_iso illisible ({e.__class__.__name__})"], None
    age = (today - d).days
    if age > MAX_AGE_DAYS:
        return [f"{DATA} : relevé Leneda du {d.isoformat()}, {age} jours (plus de {MAX_AGE_DAYS})"], d
    if age < -1:
        return [f"{DATA} : relevé daté du {d.isoformat()}, dans le futur"], d
    return [], d


def check_pages(statuses):
    """statuses : {chemin: statut HTTP}. Problèmes des pages qui ne répondent pas 200."""
    return [f"{p} : HTTP {s}" for p, s in statuses.items() if s != 200]


def main(fetch=fetch, today=None):
    today = today or datetime.now(timezone.utc).date()
    probs, d = check_data(*fetch(BASE + DATA), today)
    probs += check_pages({p: fetch(BASE + p)[0] for p in PAGES})
    if probs:
        print("Veille de fraîcheur de solaire.sitraka.lu : ÉCHEC", file=sys.stderr)
        for p in probs:
            print(f"- {p}", file=sys.stderr)
        return 1
    print(f"OK : relevé Leneda du {d.isoformat()} ({(today - d).days} j), {len(PAGES)} pages en HTTP 200")
    return 0


if __name__ == "__main__":
    sys.exit(main())
