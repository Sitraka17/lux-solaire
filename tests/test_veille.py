"""Veille de fraîcheur externe (scripts/veille_fraicheur.py, workflow .github/workflows/fraicheur.yml) :
logique testée hors réseau, et garde-fous sur les deux workflows (actions épinglées par SHA,
permissions minimales, dépendances figées)."""
import json
import re
from datetime import date

import pytest

import build
import veille_fraicheur as V

TODAY = date(2026, 11, 2)


def _data(d):
    return json.dumps({"meta": {"date_iso": d}}).encode()


def test_seuil_identique_au_build():
    assert V.MAX_AGE_DAYS == build.MAX_AGE_DAYS


@pytest.mark.parametrize("d,ok", [("2026-11-02", True), ("2026-10-23", True), ("2026-10-22", False),
                                  ("2026-11-03", True), ("2026-11-05", False)])
def test_age_du_releve(d, ok):
    probs, _ = V.check_data(200, _data(d), TODAY)
    assert (probs == []) is ok, probs


@pytest.mark.parametrize("status,body", [(404, b""), (0, b""), (200, b"<html>"), (200, b'{"meta":{}}'),
                                         (200, b'{"meta":{"date_iso":"hier"}}')])
def test_donnees_absentes_ou_cassees(status, body):
    probs, _ = V.check_data(status, body, TODAY)
    assert probs


def test_main_echoue_si_une_page_tombe():
    def fake(url, timeout=30):
        if url.endswith(V.DATA):
            return 200, _data("2026-11-02")
        return (503 if url.endswith("/simulator/") else 200), b""
    assert V.main(fetch=fake, today=TODAY) == 1
    assert V.main(fetch=lambda u, timeout=30: (200, _data("2026-11-02")), today=TODAY) == 0
    assert V.main(fetch=lambda u, timeout=30: (200, _data("2026-10-01")), today=TODAY) == 1


def test_pages_controlees_existent(root):
    for p in V.PAGES:
        assert (root / p.lstrip("/") / "index.html").exists(), p


@pytest.mark.parametrize("wf", ["rebuild.yml", "fraicheur.yml"])
def test_actions_epinglees_par_sha(root, wf):
    txt = (root / ".github" / "workflows" / wf).read_text()
    uses = re.findall(r"uses:\s*(\S+)(.*)", txt)
    assert uses
    for ref, rest in uses:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), f"{wf} : {ref} non épinglé par SHA"
        assert re.search(r"#\s*v\d+\.\d+\.\d+", rest), f"{wf} : tag manquant en commentaire pour {ref}"


def test_veille_lecture_seule(root):
    txt = (root / ".github" / "workflows" / "fraicheur.yml").read_text()
    assert re.search(r"^permissions:\n\s+contents: read\s*$", txt, re.M)
    assert "secrets." not in txt and "git push" not in txt and "schedule:" in txt
    assert "scripts/veille_fraicheur.py" in txt


def test_dependances_figees(root):
    txt = (root / ".github" / "workflows" / "rebuild.yml").read_text()
    assert "pip install -r scripts/requirements.txt -c scripts/constraints.txt" in txt
    assert re.search(r"fonts-dejavu-core=\S+", txt)
    req = (root / "scripts" / "requirements.txt").read_text()
    cons = (root / "scripts" / "constraints.txt").read_text()
    pins = lambda t: dict(re.findall(r"^([A-Za-z0-9_.-]+)==(\S+)", t, re.M))   # noqa: E731
    rp, cp = pins(req), pins(cons)
    assert {"pandas", "requests", "pillow", "pytest"} <= set(rp)
    assert "numpy" in cp
    assert all(cp.get(k) == v for k, v in rp.items()), "requirements.txt et constraints.txt divergent"
    assert not [ln for ln in req.splitlines() + cons.splitlines()
                if ln.strip() and not ln.startswith("#") and "==" not in ln]
