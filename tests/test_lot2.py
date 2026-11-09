"""Lot 2 du cahier des charges UX/UI (9/11/2026) : tableau de bord, pages communales et « Pour les
communes ». Contrôles statiques sur les pages rendues (le build doit avoir tourné)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DASH = {"fr": "fr/index.html", "en": "index.html", "de": "de/index.html", "lb": "lb/index.html", "pt": "pt/index.html"}
COMM = {"fr": "fr/commune/differdange", "en": "municipality/differdange", "de": "de/gemeinde/differdange",
        "lb": "lb/gemeng/differdange", "pt": "pt/municipio/differdange"}
FOR = {"fr": "fr/pour-les-communes", "en": "for-municipalities", "de": "de/fuer-gemeinden",
       "lb": "lb/fir-gemengen", "pt": "pt/para-os-municipios"}


def _read(rel):
    p = ROOT / rel
    p = p if p.suffix else p / "index.html"
    if not p.exists():
        pytest.skip("pages non construites")
    return p.read_text()


def _main(html):
    return html[html.index("<main"):html.index("</main>")]


@pytest.mark.parametrize("lang", DASH)
def test_tableau_de_bord_numerotation(lang):
    m = _main(_read(DASH[lang]))
    figs = re.findall(r"<figcaption><b>\S+ (\d+)\.</b>", m)
    assert figs == [str(i) for i in range(1, 8)]
    assert m.count("<table") == m.count("<caption")
    tabs = re.findall(r"<caption[^>]*>(?:<span[^>]*>)?<b>\S+ (\d+)\.</b>", m)
    assert tabs == [str(i) for i in range(1, 7)]
    assert m.count('class="src"') >= 7
    assert 'id="pick-c"' in m and m.count("<option value=\"/") == 100


@pytest.mark.parametrize("lang", COMM)
def test_pages_communales(lang):
    m = _main(_read(COMM[lang]))
    assert m.count("<table") == m.count("<caption")
    tabs = re.findall(r"<caption[^>]*><span[^>]*><b>\S+ (\d+)\.</b>", m)
    assert tabs[:3] == ["1", "2", "3"]
    assert 'class="contact-cta cta-pair"' in m and '<details class="note">' in m


@pytest.mark.parametrize("lang", FOR)
def test_page_offre(lang):
    m = _main(_read(FOR[lang]))
    text = re.sub(r"<[^>]+>", " ", m).lower()
    for w in ("€", "audit", "conseiller en énergie"):
        assert w not in text
    assert m.count("from=solaire-communes") == 2
    assert 'class="kpis k6"' in m   # extrait réel de la page de Differdange
