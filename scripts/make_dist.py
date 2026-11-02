#!/usr/bin/env python3
"""Construit le dossier publié (dist) par LISTE BLANCHE, pour le workflow du lundi ET le
déploiement local (même script, même liste) :

    python3 scripts/make_dist.py /tmp/lux-solaire-dist
    npx --yes wrangler@3.114.17 pages deploy /tmp/lux-solaire-dist --project-name=lux-solaire --branch=main --commit-dirty=true

(wrangler lancé depuis la RACINE du dépôt : il compile functions/ lui-même, functions/ n'est
jamais copié dans le dist.)

Contrôles, le script ÉCHOUE (exit 1) si :
  - une entrée de la liste blanche manque (build non lancé ?) ;
  - une entrée suivie par git à la racine n'est ni publiée ni déclarée interne : nouveau
    fichier à classer ici (sinon il disparaîtrait du site sans bruit) ;
  - un fichier interne se retrouve dans le dist (CONTEXT.md, README.md, scripts/, tests/,
    archive/, functions/, .github/, gabarits, .py, .md, et tout motif de .vercelignore).
"""
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fichiers servis à la racine.
PUBLIC_FILES = [
    "index.html", "404.html", "_headers", "robots.txt", "sitemap.xml",
    "favicon.svg", "vignette.png",
    "og.png", "og.en.png", "og.de.png", "og.lb.png",
    "og.sim.png", "og.sim.en.png", "og.sim.de.png", "og.sim.lb.png",
    "rt.js", "ev.js", "sim-engine.js",
    "google525f5d72f5a60fbe.html",                 # vérification Google Search Console
    "078ba8d6c1483f19b0aff325f01647a8.txt",        # clé IndexNow
]
# Dossiers servis (copiés entiers, hors fichiers système).
PUBLIC_DIRS = [
    "data", "fr", "de", "lb", "simulator", "municipality", "for-municipalities",
]
# Entrées suivies par git qui ne doivent JAMAIS être publiées.
INTERNAL = {
    ".github", ".gitignore", ".vercelignore", "CONTEXT.md", "README.md", "STRATEGY.md",
    "archive", "functions", "scripts", "tests", "template.html", "template_simulateur.html",
    "wrangler.toml",
}
# Motifs interdits dans le dist (chemins relatifs, fnmatch), en plus de .vercelignore.
FORBIDDEN = [
    "CONTEXT.md", "README.md", "STRATEGY.md", "*.md", "*.py", "*.pyc", "*.mjs", "*.sh",
    "template.html", "template_simulateur.html", "wrangler.toml", ".gitignore", ".vercelignore",
    ".DS_Store", "*/.DS_Store",
]
FORBIDDEN_DIRS = [
    "scripts", "tests", "archive", "functions", ".github", ".git", ".cache", ".claude", ".vercel",
    ".wrangler", ".pytest_cache", ".ruff_cache", "__pycache__", "node_modules",
]
SKIP = shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc")


def tracked_top_level():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None                      # hors dépôt git : contrôle de classement sauté
    return {line.split("/", 1)[0] for line in out.splitlines() if line}


def vercelignore_patterns():
    f = ROOT / ".vercelignore"
    if not f.exists():
        return []
    pats = []
    for line in f.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pats.append(line)
    return pats


def leaks(dist):
    files = [p.relative_to(dist).as_posix() for p in dist.rglob("*")]
    bad = set()
    for rel in files:
        parts = rel.split("/")
        if any(part in FORBIDDEN_DIRS for part in parts):
            bad.add(rel)
        if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(parts[-1], pat) for pat in FORBIDDEN):
            bad.add(rel)
    for pat in vercelignore_patterns():
        if pat.endswith("/"):
            bad.update(r for r in files if r == pat[:-1] or r.startswith(pat))
        else:
            bad.update(r for r in files if fnmatch.fnmatch(r, pat) or fnmatch.fnmatch(r.split("/")[-1], pat))
    return sorted(bad)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage : python3 scripts/make_dist.py <dossier de sortie>")
    dist = Path(sys.argv[1]).resolve()
    if dist == ROOT or ROOT in dist.parents:
        sys.exit(f"dist : le dossier de sortie doit être HORS du dépôt ({dist})")

    problems = []
    missing = [n for n in PUBLIC_FILES if not (ROOT / n).is_file()]
    missing += [n + "/" for n in PUBLIC_DIRS if not (ROOT / n).is_dir()]
    if missing:
        problems.append("entrées publiques absentes (build lancé ?) : " + ", ".join(missing))
    tracked = tracked_top_level()
    if tracked is not None:
        unknown = sorted(tracked - set(PUBLIC_FILES) - set(PUBLIC_DIRS) - INTERNAL)
        if unknown:
            problems.append("entrées non classées (à ajouter à PUBLIC_FILES / PUBLIC_DIRS ou INTERNAL "
                            "dans scripts/make_dist.py) : " + ", ".join(unknown))
    if problems:
        sys.exit("dist non construit :\n  " + "\n  ".join(problems))

    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    for n in PUBLIC_FILES:
        shutil.copy2(ROOT / n, dist / n)
    for n in PUBLIC_DIRS:
        shutil.copytree(ROOT / n, dist / n, ignore=SKIP)

    bad = leaks(dist)
    if bad:
        sys.exit(f"dist : {len(bad)} fichier(s) interne(s) publié(s), déploiement refusé :\n  " +
                 "\n  ".join(bad[:30]))
    for must in ("index.html", "fr/index.html", "de/index.html", "lb/index.html", "simulator/index.html",
                 "data/data.json", "sim-engine.js", "_headers"):
        if not (dist / must).is_file():
            sys.exit(f"dist : {must} absent")
    n = sum(1 for p in dist.rglob("*") if p.is_file())
    print(f"dist : {n} fichiers dans {dist} (liste blanche, aucun fichier interne)")


if __name__ == "__main__":
    main()
