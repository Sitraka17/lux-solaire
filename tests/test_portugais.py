"""Simulateur en portugais (/pt/simulador/, 8/11/2026) : dictionnaires à parité, formats
portugais, page rendue sans français résiduel, contrôle des barèmes actif."""
import html
import json
import re

import pytest

import baremes
import build

PAGE = "pt/simulador/index.html"


def test_parite_dictionnaire_pt():
    """Mêmes clés que le simulateur EN, plus les clés du tableau de bord présentes sur la page
    simulateur ; aucune clé morte (check_dict_pt sort en erreur sinon)."""
    tpl_sim = (build.ROOT / "template_simulateur.html").read_text()
    build.check_dict_pt(tpl_sim)
    sim_en = set()
    for name in build.I18N_FILES["en"][2:]:
        sim_en |= set(json.loads((build.ROOT / "scripts" / name).read_text()))
    assert sim_en <= set(build.I18N_PT)


def test_parite_detecte_une_cle_manquante(monkeypatch):
    tpl_sim = (build.ROOT / "template_simulateur.html").read_text()
    d = dict(build.I18N_PT)
    d.pop(next(iter(d)))
    monkeypatch.setattr(build, "I18N_PT", d)
    with pytest.raises(SystemExit):
        build.check_dict_pt(tpl_sim)


def test_formats_portugais():
    assert build._thousands(38187, "pt") == "38 187"
    assert build._dec1(12345.65, "pt") == "12 345,7"
    assert build._tr_str_pt("2 novembre 2026") == "2 de novembro de 2026"
    assert build._tr_str_pt("1er octobre 2026") == "1 de outubro de 2026"
    assert build._tr_str_pt("2025 T1") == "2025 T1"


def test_milliers_comme_tolocalestring(node):
    """La page PT garde la locale JS 'fr-FR' : son séparateur de milliers est U+202F, le même
    que _thousands(…, 'pt') (pré-rendu Python et recalcul JS identiques)."""
    js = node("process.stdout.write(JSON.stringify([38187, 1234567].map(x => x.toLocaleString('fr-FR'))));")
    assert js == [build._thousands(38187, "pt"), build._thousands(1234567, "pt")]


@pytest.fixture(scope="module")
def page(root):
    p = root / PAGE
    if not p.exists():
        pytest.skip("page PT absente : lancer scripts/build.py")
    return p.read_text()


def test_page_pt_metadonnees(page):
    assert '<html lang="pt">' in page
    assert '<link rel="canonical" href="https://solaire.sitraka.lu/pt/simulador/">' in page
    assert 'hreflang="x-default" href="https://solaire.sitraka.lu/simulator/"' in page
    assert '<meta property="og:locale" content="pt_PT">' in page
    assert "og.sim.pt.png" in page
    assert '"@type": "FAQPage"' in page or '"@type":"FAQPage"' in page


def test_hreflang_pt_sur_les_cinq_pages(root):
    for p in ("simulator", "fr/simulateur", "de/rechner", "lb/rechner", "pt/simulador"):
        h = (root / p / "index.html").read_text()
        assert '<link rel="alternate" hreflang="pt" href="https://solaire.sitraka.lu/pt/simulador/">' in h, p
        assert h.count('hreflang="x-default"') == 1, p
    assert "https://solaire.sitraka.lu/pt/simulador/" in (root / "sitemap.xml").read_text()


def test_aucun_francais_residuel(page):
    """Texte visible, attributs, FAQ structurée et littéraux JS (hors commentaires) : aucun mot
    outil français. « ou » et « que » existent en portugais et ne sont pas cherchés."""
    body = re.sub(r"<style\b.*?</style>", " ", page, flags=re.S)
    body = re.sub(r'<script type="application/ld\+json">(.*?)</script>',
                  lambda m: " ".join(re.findall(r'"(?:name|text|description)": ?"((?:[^"\\]|\\.)*)"', m.group(1))),
                  body, flags=re.S)
    body = re.sub(r"<script\b[^>]*>(.*?)</script>",
                  lambda m: " ".join(re.findall(r"'((?:[^'\\\n]|\\.)*)'",
                                                re.sub(r"//[^\n]*|/\*.*?\*/", "", m.group(1), flags=re.S))),
                  body, flags=re.S)
    attrs = " ".join(re.findall(r'(?:aria-label|title|placeholder|alt|content|data-l-[a-z-]+)="([^"]*)"', body))
    txt = html.unescape(re.sub(r"<[^>]+>", " ", body) + " " + attrs)
    txt = re.sub(r"https?://\S+", " ", txt)
    fr = ["les", "des", "du", "et(?! al\\.)", "pour", "avec", "sur", "dans", "une", "est", "au", "aux", "votre",
          "vos", "sans", "année", "ans", "chauffage", "panneaux", "toit", "coût", "prix", "sont", "qui", "pas",
          "plus", "chez", "kWc", "Option", "Simulateur", "Tableau", "Outil"]
    found = [(w, txt[max(0, m.start() - 40):m.end() + 40]) for w in fr
             for m in re.finditer(r"(?<![\wÀ-ÿ])" + w + r"(?![\wÀ-ÿ])", txt)]
    assert not found, found[:10]


def test_baremes_controles_sur_la_page_pt(page):
    assert baremes.check_page(page, "pt", "sim") == []
    import copy
    b = copy.deepcopy(baremes.B)
    b["klimabonus_pv"]["valeur"]["max"] = 9000
    assert baremes.check_page(page, "pt", "sim", b)
