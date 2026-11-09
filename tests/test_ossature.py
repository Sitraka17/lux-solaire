"""Ossature commune (lot 1 du cahier des charges, 9/11/2026) : bandeau de la série, sélecteur de 5
langues, fil d'Ariane, section Méthode, colophon commun, conteneurs défilants, mois abrégés.
Contrôle STATIQUE des pages rendues (les mesures dans le navigateur, débordement à 320/375/768/1 280 px
et taille des cibles, se font avec Chrome sans tête, voir CONTEXT.md). Saute sans build."""
import re
from datetime import date

import pytest

import build
import communes
import ossature

DASH = dict(build.LANG_PATHS)
SIM = dict(build.SIM_PATHS)


def _file(root, path):
    return root / path.strip("/") / "index.html" if path.strip("/") else root / "index.html"


@pytest.fixture(scope="module")
def pages(root):
    if not (root / "pt" / "index.html").exists():
        pytest.skip("pages absentes : lancer scripts/build.py")
    out = []
    for lang in build.DASH_LANGS:
        out += [("dash", lang, DASH[lang]), ("sim", lang, SIM[lang]), ("for", lang, communes.FORPATH[lang]),
                ("commune", lang, communes.CPATH[lang] + "differdange/"),
                ("commune", lang, communes.CPATH[lang] + "wincrange/")]
    return [(k, l, p, _file(root, p).read_text()) for k, l, p in out]


def test_bandeau_et_selecteur_sur_chaque_type_de_page(pages):
    for kind, lang, path, h in pages:
        assert h.count('<div class="masthead">') == 1, path
        assert "seriesbar" not in h and "langtoggle" not in h, path
        nav = re.search(r'<ul class="langs" aria-label="([^"]+)">(.*?)</ul>', h, re.S)
        assert nav and nav.group(1) == ossature.ARIA_LANG[lang], path
        codes = re.findall(r'hreflang="([a-z]+)"', nav.group(2))
        assert codes == ["en", "fr", "de", "lb", "pt"], (path, codes)
        assert nav.group(2).count('aria-current="page"') == 1, path
        assert re.search(rf'href="{re.escape(path)}" lang="[^"]+" hreflang="{lang}" aria-current="page"', nav.group(2)), path
        # drapeaux : repère secondaire, cachés aux lecteurs d'écran ; nom natif en texte masqué
        assert nav.group(2).count('aria-hidden="true" focusable="false"') == 5, path
        assert nav.group(2).count('<span class="vh"> ') == 5, path
        # deux copies de la liste (bureau, repli mobile), chacune avec un seul site courant
        series = re.findall(r'<ul class="series">(.*?)</ul>', h, re.S)
        assert len(series) == 2 and all(s.count("aria-current") == 1 and s.count("<li>") == 8 for s in series), path


def test_fil_d_ariane_et_colophon(pages):
    for kind, lang, path, h in pages:
        if kind != "dash":   # racine : pas de fil d'Ariane, un surtitre
            crumbs = re.search(r'<nav class="crumbs" aria-label="[^"]+"><ol>(.*?)</ol></nav>', h, re.S)
            assert crumbs, path
            assert crumbs.group(1).count('aria-current="page"') == 1, path
        assert h.count('<footer class="colophon"') == 1, path
        foot = h[h.index('<footer class="colophon"'):h.index("</footer>")]
        assert f'href="{communes.FORPATH[lang]}"' in foot, path          # « Pour les communes » dans chaque colophon
        assert "github.com/Sitraka17/lux-solaire" in foot and "sitraka.lu/" in foot, path
        assert foot.count("<tr") == 9, path                                # tableau A : en-tête + 8 sites
        assert h.index("</main>") < h.index('<footer class="colophon"'), path
        if kind in ("dash", "sim"):
            assert re.search(r'<section id="methode" class="method"', h), path
            assert h.index('id="methode"') < h.index("</main>"), path


def test_aucune_pilule_ni_largeur_minimale_globale(pages):
    for kind, lang, path, h in pages:
        css = re.search(r"<style>(.*?)</style>", h, re.S).group(1)
        assert "999px" not in css, path
        assert not re.search(r"(?<![\w.#-])table\{[^}]*min-width:900px", css), path
        # les tableaux larges défilent dans leur conteneur, pas la page
        for m in re.finditer(r'<table class="bigtab"', h):
            assert h.rfind('<div class="tblscroll"', 0, m.start()) > h.rfind("</div>", 0, m.start()), path


def test_mois_abreges():
    assert build._label_fr(date(2026, 11, 9)) == "9 nov. 2026"
    assert build._label_fr(date(2026, 10, 5)) == "5 oct. 2026"
    assert build._label_fr(date(2026, 3, 2)) == "2 mars 2026"
    assert build._label_fr(date(2026, 4, 6)) == "6 avr. 2026"
    assert build._tr_str("9 nov. 2026") == "9 Nov 2026"
    assert build._tr_str_de("9 nov. 2026") == "9. Nov. 2026"
    assert build._tr_str_pt("9 nov. 2026") == "9 nov. 2026"


def test_aucune_abreviation_fautive(root, pages):
    data = (root / "data" / "data.json").read_text()
    for bad in ("nove.", "octo.", "déce.", "avri.", "janv. janv.", "sept. sept."):
        assert bad not in data, bad
        for _, _, path, h in pages:
            assert bad not in h, (path, bad)
