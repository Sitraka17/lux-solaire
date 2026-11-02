"""Dist par liste blanche (scripts/make_dist.py) : aucun fichier interne publié, entrées
publiques présentes, et détection d'une fuite injectée."""
import subprocess
import sys

import make_dist


def test_dist_liste_blanche(root, tmp_path):
    dist = tmp_path / "dist"
    r = subprocess.run([sys.executable, str(root / "scripts" / "make_dist.py"), str(dist)],
                       capture_output=True, text=True, cwd=root, timeout=120)
    assert r.returncode == 0, r.stderr
    tops = {p.name for p in dist.iterdir()}
    assert tops == set(make_dist.PUBLIC_FILES) | set(make_dist.PUBLIC_DIRS)
    assert not tops & make_dist.INTERNAL
    assert make_dist.leaks(dist) == []
    for fuite in ("CONTEXT.md", "fr/notes.md", "scripts/build.py", "data/archive/x.csv.gz"):
        f = dist / fuite
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
    found = make_dist.leaks(dist)
    assert {"CONTEXT.md", "fr/notes.md", "scripts/build.py", "data/archive/x.csv.gz"} <= set(found)


def test_dist_dans_le_depot_refuse(root):
    r = subprocess.run([sys.executable, str(root / "scripts" / "make_dist.py"), str(root / "dist")],
                       capture_output=True, text=True, cwd=root, timeout=60)
    assert r.returncode != 0 and "HORS du dépôt" in r.stderr
