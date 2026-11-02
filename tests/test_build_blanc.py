"""Build « à blanc » : copie du dépôt dans un dossier temporaire, puis build complet sur les
réponses déjà en cache (.cache/, rempli par LUX_SOLAIRE_CACHE=1) et les archives locales,
SANS réseau : tout téléchargement manquant fait sauter le test proprement. Le dépôt lui-même
n'est pas touché. Les données en cache peuvent être anciennes : ce test vérifie le pipeline
(format, garde-fous, rendu des 4 langues, contrôle des barèmes), pas la fraîcheur."""
import os
import shutil
import subprocess
import sys

import pytest

RUNNER = r'''
import sys
sys.path.insert(0, sys.argv[1])
import build
def _offline(url, timeout):
    print("HORS CACHE : " + url)
    sys.exit(77)
build._fetch = _offline
build.main()
'''


def test_build_a_blanc(root, tmp_path):
    if not (root / ".cache").is_dir() or not any((root / ".cache").iterdir()):
        pytest.skip("pas de .cache/ local (lancer une fois LUX_SOLAIRE_CACHE=1 /usr/bin/python3 scripts/build.py)")
    dst = tmp_path / "site"
    shutil.copytree(root, dst, ignore=shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".pytest_cache"))
    env = {**os.environ, "LUX_SOLAIRE_CACHE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-c", RUNNER, str(dst / "scripts")], cwd=dst, env=env,
                       capture_output=True, text=True, timeout=600)
    if r.returncode == 77:
        pytest.skip("build à blanc impossible sans réseau : " + r.stdout.strip().splitlines()[-1])
    assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-3000:])
    assert "pages contrôlées contre scripts/baremes.json" in r.stdout
    for p in ("index.html", "fr/index.html", "de/index.html", "lb/index.html", "simulator/index.html",
              "fr/simulateur/index.html", "de/rechner/index.html", "lb/rechner/index.html",
              "municipality/differdange/index.html", "lb/gemeng/differdange/index.html"):
        assert (dst / p).stat().st_size > 10_000, p
