"""Corrections des cinq relectures du 9/11/2026 (visuel, portugais, technique, accessibilité, offre)."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _read(p):
    f = ROOT / p.strip("/") / "index.html" if p.strip("/") else ROOT / "index.html"
    if not f.exists():
        pytest.skip("pages absentes : lancer scripts/build.py")
    return f.read_text()


def _text(h):
    h = re.sub(r"<(script|style|pre)\b.*?</\1>", " ", h, flags=re.S)
    return re.sub(r"<[^>]+>", "\x00", h)


def test_ev_js_compte_les_liens_portugais_et_le_contact():
    js = (ROOT / "ev.js").read_text()
    sim = re.search(r"else if \((/.*?/)\.test\(h\)\) send\('sim'\)", js).group(1)
    page = re.search(r"else if \((/.*?/)\.test\(h\)\) send\('page'", js).group(1)
    to_py = lambda r: re.compile(r[1:-1].replace("\\/", "/"))   # noqa: E731
    assert to_py(sim).search("/pt/simulador/?canton=Esch")
    assert to_py(page).search("/pt/municipio/sanem/")
    assert "sitraka.lu/contact" in js and '"sitraka.lu/contact"' in (ROOT / "functions" / "e.js").read_text()
    # ev.js versionné par empreinte (servi avec max-age=86400)
    for p in ("/pt/", "/pt/municipio/differdange/"):
        assert re.search(r'src="/ev\.js\?v=[0-9a-f]{10}"', _read(p)), p


def test_appel_principal_vers_la_page_d_offre():
    for p, target in (("/fr/", "/fr/pour-les-communes/"), ("/pt/simulador/", "/pt/para-os-municipios/"),
                      ("/fr/commune/differdange/", "/fr/pour-les-communes/")):
        h = _read(p)
        m = re.search(r'<p class="contact-cta[^"]*">.*?</p>', h, re.S).group(0)
        assert f'href="{target}"' in m and "sitraka.lu/fr/contact/?from=solaire\"" not in m, p


def test_typographie_francaise():
    for p in ("/fr/", "/fr/simulateur/", "/fr/commune/differdange/", "/fr/pour-les-communes/"):
        t = _text(_read(p))
        assert not re.search(r"[  ][;!?]", t), p        # fine insécable avant ; ! ?
        assert not re.search(r" :", t), p                     # insécable avant les deux-points
        assert "« " not in t and " »" not in t, p


def test_sources_sous_figures_et_tableaux_du_simulateur():
    for p in ("/fr/simulateur/", "/pt/simulador/"):
        h = _read(p)
        main = h[h.index("<main"):h.index('id="methode"')]
        assert main.count('<p class="src">') >= 11, p


def test_portugais_tabela_quota_predefinido():
    for p in ("/pt/", "/pt/simulador/", "/pt/municipio/differdange/", "/pt/para-os-municipios/"):
        h = _read(p)
        assert "Quadro" not in h and "por defeito" not in h, p
        assert ">Parte PV<" not in h and "PV (MW)" not in h, p
    assert "remuneração garantida" not in _read("/pt/para-os-municipios/")


def test_accessibilite_bandeau_et_citation():
    for p in ("/fr/", "/fr/simulateur/", "/pt/municipio/differdange/"):
        h = _read(p)
        assert h.count('aria-current="true"') == 3, p      # site courant : 2 listes + tableau A
        if "rt-cite-txt" in h:
            assert re.search(r'id="rt-cite-txt" tabindex="0" role="region" aria-label="[^"]+"', h), p
        css = re.search(r"<style>(.*?)</style>", h, re.S).group(1)
        assert ".pair .b.cap{background:var(--ink);opacity" not in css, p


def test_pages_communales_fil_d_ariane_jsonld_og_locale():
    h = _read("/fr/commune/differdange/")
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', h, re.S).group(1))
    types = [x["@type"] for x in ld["@graph"]]
    assert types == ["WebPage", "BreadcrumbList"]
    assert ld["@graph"][1]["itemListElement"][1]["item"].endswith("/fr/pour-les-communes/#liste")
    assert '<meta property="og:locale" content="fr_FR">' in h
    assert 'href="/fr/pour-les-communes/#liste"' in h and 'id="liste"' in _read("/fr/pour-les-communes/")
    # colonnes communes aux tableaux 2 et 3
    assert h.count('<colgroup><col class="c-rk">') == 2
    # « kW » des en-têtes en capitales protégé
    assert '<span class="nt">kW</span>' in h


def test_page_d_offre_maquettes_et_editeur():
    h = _read("/fr/pour-les-communes/")
    assert "<b>Figure 3.</b>" in h and "<b>Tableau 2.</b>" in h
    assert "sitraka.lu/fr/privacy/" in h and 'class="who"' in h


def test_total_national_identique_kpi_et_figure():
    h = _read("/fr/")
    assert "sum6" in h and 'id="k-tot">1 278<' in h
