"""Portugais européen sur TOUT le site (9/11/2026) : tableau de bord /pt/, 100 pages communales
/pt/municipio/<slug>/, « Pour les communes » /pt/para-os-municipios/, simulateur /pt/simulador/.
Sélecteur de langue, hreflang réciproques (5 langues, x-default = EN), sitemap, liens PT vers PT,
compteur /e et absence de français résiduel. Les tests sur pages rendues sautent sans build."""
import json
import re
import shutil
import subprocess
import sys

import pytest

import communes
from francais_residuel import french_words

SITE = "https://solaire.sitraka.lu"
LANGS = ("en", "fr", "de", "lb", "pt")
DASH = {"en": "/", "fr": "/fr/", "de": "/de/", "lb": "/lb/", "pt": "/pt/"}
SIM = {"en": "/simulator/", "fr": "/fr/simulateur/", "de": "/de/rechner/", "lb": "/lb/rechner/",
       "pt": "/pt/simulador/"}


def _file(root, path):
    return root / path.strip("/") / "index.html" if path.strip("/") else root / "index.html"


@pytest.fixture(scope="module")
def built(root):
    if not (root / "pt" / "index.html").exists() or not (root / "pt" / "municipio").is_dir():
        pytest.skip("pages PT absentes : lancer scripts/build.py")
    return root


@pytest.fixture(scope="module")
def groups(built, commune_names):
    """Groupes de pages équivalentes {langue: chemin} : tableau de bord, simulateur,
    « Pour les communes » et chaque commune."""
    g = [("dash", DASH), ("sim", SIM), ("for", dict(communes.FORPATH))]
    g += [("commune", {l: communes.CPATH[l] + communes.slug(n) + "/" for l in LANGS}) for n in commune_names]
    return g


@pytest.fixture(scope="module")
def official_names(root):
    d = json.loads((root / "data" / "data.json").read_text())
    return {c["c"] for c in d["communes"]} | {c["k"] for c in d["communes"]}


def _pt_pages(root):
    return ([root / "pt" / "index.html", root / "pt" / "simulador" / "index.html",
             root / "pt" / "para-os-municipios" / "index.html"]
            + sorted((root / "pt" / "municipio").glob("*/index.html")))


def test_chemins_portugais():
    assert communes.CPATH["pt"] == "/pt/municipio/" and communes.FORPATH["pt"] == "/pt/para-os-municipios/"
    assert communes.LANGS == LANGS and communes.FLAG_LABEL["pt"] == "PT"


def test_cent_trois_pages_pt(built, commune_names):
    pages = _pt_pages(built)
    assert len(pages) == 3 + len(commune_names) == 103
    assert {p.parent.name for p in pages[3:]} == {communes.slug(n) for n in commune_names}


def test_hreflang_reciproques_cinq_langues(built, groups):
    for kind, paths in groups:
        expected = {(l, SITE + p) for l, p in paths.items()}
        for lang, p in paths.items():
            h = _file(built, p).read_text()
            alts = set(re.findall(r'<link rel="alternate" hreflang="([a-z-]+)" href="([^"]+)">', h))
            assert {a for a in alts if a[0] != "x-default"} == expected, (kind, p)
            assert [a for a in alts if a[0] == "x-default"] == [("x-default", SITE + paths["en"])], (kind, p)
            assert h.count('hreflang="x-default"') == 1, (kind, p)


def test_selecteur_avec_pt_sur_chaque_type_de_page(built, groups):
    """Chaque page a PT dans son sélecteur, chaque lien du sélecteur mène à la même page dans
    l'autre langue (aller ET retour depuis les pages PT), la langue courante est marquée."""
    for kind, paths in groups:
        for lang, p in paths.items():
            h = _file(built, p).read_text()
            assert h.count('<ul class="langs"') == 1, (kind, p)
            tog = re.search(r'<ul class="langs"[^>]*>(.*?)</ul>', h, re.S).group(1)
            links = re.findall(r'<a href="([^"]+)" lang="[^"]+" hreflang="([a-z]+)"( aria-current="page")?>'
                               r'.*?(EN|FR|DE|LB|PT)<span class="vh"> [^<]+</span></a>', tog, re.S)
            code = {"EN": "en", "FR": "fr", "DE": "de", "LB": "lb", "PT": "pt"}
            assert [(code[c], href) for href, _, _, c in links] == [(l, paths[l]) for l in LANGS], (kind, p, links)
            assert all(code[c] == hl for _, hl, _, c in links), (kind, p)
            assert [code[c] for _, _, cur, c in links if cur] == [lang], (kind, p)


def test_sitemap_contient_les_pages_pt(built, groups):
    sm = (built / "sitemap.xml").read_text()
    for kind, paths in groups:
        assert f"<loc>{SITE}{paths['pt']}</loc>" in sm, (kind, paths["pt"])
        assert f'hreflang="pt" href="{SITE}{paths["pt"]}"' in sm, kind
    assert sm.count(f"<loc>{SITE}/pt/") == 103


def test_liens_internes_pt_vers_pt(built):
    """Hors sélecteur de langue : aucun lien interne d'une page PT vers une autre langue, et
    plus de « (em francês) » vers une page qui existe en portugais."""
    for p in _pt_pages(built):
        h = re.sub(r'<ul class="langs".*?</ul>', "", p.read_text(), count=1, flags=re.S)
        bad = [u for u in re.findall(r'href="(/[^"#?]*)', h)
               if not u.startswith(("/pt/", "/data/", "/favicon"))]
        assert not bad, (p, bad[:5])
        # « (em francês) » : seulement vers des documents externes (sources, contact sitraka.lu),
        # jamais vers une page de ce site, qui existe toutes en portugais
        for m in re.finditer(r'<a href="([^"]+)"[^>]*>[^<]*\(em francês\)', h):
            assert not m.group(1).startswith(("/", SITE)), (p, m.group(1))


def test_aucun_francais_residuel_sur_les_pages_pt(built, official_names):
    for p in _pt_pages(built):
        found = french_words(p.read_text(), official_names)
        assert not found, (str(p.relative_to(built)), found[:6])


def test_detecteur_voit_le_francais(built, official_names):
    """Garde du détecteur lui-même : il trouve bien du français sur les pages FR."""
    for p in ("fr/index.html", "fr/commune/differdange/index.html", "fr/pour-les-communes/index.html"):
        assert len(french_words((built / p).read_text(), official_names)) > 50, p


def test_metadonnees_pt(built):
    h = (built / "pt" / "index.html").read_text()
    assert '<html lang="pt-PT">' in h
    assert '<link rel="canonical" href="https://solaire.sitraka.lu/pt/">' in h
    assert '<meta property="og:locale" content="pt_PT">' in h and "og.pt.png" in h
    assert (built / "og.pt.png").is_file()
    assert re.search(r"\d{1,2} de (janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|"
                     r"novembro|dezembro) de \d{4}", h)
    assert '<a href="/data/data.pt.json" download>' in h
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', h, re.S).group(1))
    assert "pt" in json.dumps(ld) and '"inLanguage": "pt"' in json.dumps(ld, ensure_ascii=False)
    for p in ("pt/municipio/differdange/index.html", "pt/para-os-municipios/index.html"):
        c = (built / p).read_text()
        assert '<html lang="pt-PT">' in c, p
        assert '"inLanguage": "pt"' in c and '<meta name="description" content="' in c, p
    c = (built / "pt/municipio/differdange/index.html").read_text()
    assert "Grandes instalações" in c and 'id="grandes-installations"' in c
    assert "cantão de Esch" in c and "Differdange" in c


def test_donnees_et_manifeste_pt(built):
    d = json.loads((built / "data" / "data.pt.json").read_text())
    assert " de " in d["meta"]["date"]
    m = json.loads((built / "data" / "manifest.json").read_text())
    assert any(f["path"] == "/data/data.pt.json" and f["lang"] == "pt" for f in m["files"])
    assert all("pt" in f["title"] for f in m["files"])


def test_404_lien_pt(root):
    h = (root / "404.html").read_text()
    assert '<a href="/pt/"' in h


def test_make_dist_publie_pt():
    import make_dist
    assert "pt" in make_dist.PUBLIC_DIRS and "og.pt.png" in make_dist.PUBLIC_FILES


def test_allowlist_contient_data_pt(root):
    assert '"data.pt.json"' in (root / "functions" / "_allow.js").read_text()


@pytest.fixture(scope="module")
def e_js(root, tmp_path_factory):
    """functions/e.js chargé dans node (copie .mjs, _allow.js réel), base D1 simulée."""
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node absent")
    d = tmp_path_factory.mktemp("efn")
    (d / "_allow.mjs").write_text((root / "functions" / "_allow.js").read_text())
    (d / "e.mjs").write_text((root / "functions" / "e.js").read_text().replace('"./_allow.js"', '"./_allow.mjs"'))
    runner = d / "run.mjs"
    runner.write_text(
        "import { onRequestPost } from './e.mjs';\n"
        "const bodies = JSON.parse(process.argv[2]); const out = [];\n"
        "for (const b of bodies) {\n"
        "  const rows = [];\n"
        "  const env = { DB: { prepare: () => ({ bind: (...a) => ({ run: async () => rows.push(a) }) }) } };\n"
        "  const req = new Request('https://solaire.sitraka.lu/e', { method: 'POST', body: JSON.stringify(b),\n"
        "    headers: { 'Sec-Fetch-Site': 'same-origin' } });\n"
        "  await onRequestPost({ request: req, env }); out.push(rows.map(r => r[2]));\n"
        "}\n"
        "process.stdout.write(JSON.stringify(out));\n")

    def run(bodies):
        r = subprocess.run([exe, str(runner), json.dumps(bodies)], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    return run


def test_compteur_e_accepte_pt(e_js):
    ev = lambda l, p, t="page", x="differdange": {"t": t, "l": l, "p": p, "x": x, "r": ""}  # noqa: E731
    out = e_js([
        ev("pt-PT", "/pt/municipio/differdange/"),          # ce que ev.js envoie (html lang)
        ev("pt", "/pt/municipio/differdange/"),
        ev("pt-PT", "/pt/", "commune", "lux"),
        ev("pt-PT", "/pt/para-os-municipios/", "contact", "hello@sitraka.lu"),
        ev("pt-PT", "/pt/", "dl", "data.pt.json"),
        ev("fr", "/fr/commune/differdange/"),                # non-régression
        ev("es", "/pt/municipio/differdange/"),              # langue inconnue : ignorée
        ev("pt-PT", "/pt/municipio/inexistante/"),           # slug inconnu : ignoré
        ev("pt-BR", "/pt/"),                                 # variante non publiée : ignorée
    ])
    assert out == [["pt"], ["pt"], ["pt"], ["pt"], ["pt"], ["fr"], [], [], []]
