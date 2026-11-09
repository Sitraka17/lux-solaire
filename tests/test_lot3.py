"""Lot 3 du cahier des charges UX/UI (simulateur, 9/11/2026) : contrôles statiques sur les 5 pages rendues.
Les mesures dans le navigateur (hauteurs, tabulation, verdict collant, curseurs, URL courte, pré-rendu = JS)
sont faites par un script playwright hors dépôt (voir CONTEXT.md, section « Lot 3 »)."""
import re

import pytest

SIM = {"en": "simulator", "fr": "fr/simulateur", "de": "de/rechner", "lb": "lb/rechner", "pt": "pt/simulador"}


@pytest.fixture(params=sorted(SIM))
def page(request, root):
    return request.param, (root / SIM[request.param] / "index.html").read_text()


def test_sommaire_des_trois_outils(page):
    _, h = page
    m = re.search(r'<nav class="toc" aria-label="[^"]+"><ol>(.*?)</ol></nav>', h, re.S)
    assert m, "sommaire absent"
    assert re.findall(r'href="(#[a-z]+)"', m.group(1)) == ["#production", "#rentabilite", "#chauffage"]
    for a in ("production", "rentabilite", "chauffage"):
        assert f'<section id="{a}">' in h


def test_tableaux_numerotes_dans_l_ordre_avec_caption(page):
    _, h = page
    main = h[h.index("<main"):h.index("</main>")]
    tables = re.findall(r"<table\b[^>]*>(.*?)</table>", main, re.S)
    nums = [re.match(r'\s*<caption id="[a-z-]+"><span class="capin"><b>\S+ (\d+)\.</b>', t) for t in tables]
    assert all(nums), "tableau sans <caption> numérotée"
    assert [int(n.group(1)) for n in nums] == list(range(1, 9))
    figs = re.findall(r"<figcaption><b>\S+ (\d+)\.</b>", main)
    assert figs == ["1", "2", "3"]
    # aucune légende de tableau en <figcaption>
    assert not re.search(r"<figure[^>]*>\s*<table", main)


def test_reperes_apres_l_outil_3_et_appel_communes_avant_la_methode(page):
    _, h = page
    order = [h.index(f'<section id="{s}"') for s in ("production", "rentabilite", "chauffage", "profils", "reperes", "faq", "methode")]
    assert order == sorted(order)
    cta = h.index('<p class="contact-cta">')
    assert h.index('<section id="faq"') < cta < h.index('<section id="methode"')


def test_resultats_avant_le_formulaire(page):
    _, h = page
    for sec, f in (("production", "f1"), ("rentabilite", "f2"), ("chauffage", "f3")):
        s = h[h.index(f'<section id="{sec}">'):]
        assert s.index('<div class="res">') < s.index(f'<form class="card form" id="{f}"')
        assert f'href="#{f}"' in s[:s.index(f'<form class="card form" id="{f}"')]


def test_methode_et_sources_repliees_sources_ancrees(page):
    _, h = page
    m = h[h.index('<section id="methode"'):]
    m = m[:m.index("</section>")]
    assert '<details id="m-calc">' in m and '<details id="m-src">' in m
    assert re.findall(r'<li id="src-(\d+)">', m) == [str(i) for i in range(1, 14)]


def test_curseurs_et_champs_facture(page):
    _, h = page
    ranges = re.findall(r'<input type="range"[^>]*>', h)
    assert len(ranges) == 21
    for i in ("cons-in", "hconso"):
        tag = re.search(rf'<input [^>]*id="{i}"[^>]*>', h).group(0)
        assert 'type="text"' in tag and 'inputmode="decimal"' in tag and "type=\"number\"" not in tag
    # aria-valuetext est posé en JS pour les 21 curseurs : la liste du script les nomme tous
    vt = re.search(r"const VT=\{(.*?)\};", h, re.S).group(1)
    ids = [re.search(r'id="([^"]+)"', r).group(1) for r in ranges]
    for i in ids:
        assert re.search(rf"(^|[\s,{{])'?{re.escape(i)}'?:", vt), i


def test_pre_rendu_tri_a_une_decimale_et_gain_a_et_b(page):
    lang, h = page
    irr = re.search(r'id="b-irr">([^<]+)<', h).group(1)
    assert re.fullmatch(r"\d+[,.]\d %?|\d+[,.]\d%", irr), irr
    gain = re.search(r'id="r-gain">(.*?)</div>', h).group(1)
    assert gain.count("<i>") == 2 and "<i>A</i>" in gain and "<i>B</i>" in gain


def test_profil_par_defaut_etiquette_retour_le_plus_rapide(root):
    h = (root / "fr" / "simulateur" / "index.html").read_text()
    # +6 975 € contre +6 950 € : écart < 2 %, l'étiquette ne dit plus « la plus avantageuse »
    assert 'id="tag-a">retour le plus rapide<' in h
    assert "L'option A demande un apport initial de" in h
