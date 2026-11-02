"""Le slug d'une commune est calculé en Python (communes.slug, chemins des pages communales)
et en JS (slugC de template.html, seule définition, utilisée par la table des communes, le sélecteur
« Voir une commune » et le paramètre ?commune=) : ils doivent
coïncider sur les 100 noms réels, sinon les liens du tableau de bord mènent à des 404."""
import re

import communes

READ_STDIN = "const names = JSON.parse(require('fs').readFileSync(0, 'utf8'));"


def _js_fn(tpl, pattern):
    m = re.search(pattern, tpl)
    assert m, f"fonction introuvable dans template.html : {pattern}"
    return m.group(1)


def test_slug_python_js_identiques(root, commune_names, node):
    tpl = (root / "template.html").read_text()
    slug_c = _js_fn(tpl, r"const slugC\s*=\s*(t\s*=>.*?);\n")
    out = node(READ_STDIN + f"const a = {slug_c};"
               "process.stdout.write(JSON.stringify(names.map(n => a(n))));", commune_names)
    for name, js in zip(commune_names, out):
        py = communes.slug(name)
        assert py == js, (name, py, js)


def test_slug_js_unique_et_echappe(root):
    """Une seule fonction de slug côté JS (slugC), écrite avec des échappements \\u0300-\\u036f :
    pas de seconde copie, pas de caractère combinant littéral (invisible, fragile à l'édition)."""
    tpl = (root / "template.html").read_text()
    assert len(re.findall(r"normalize\(\s*['\"]NFD", tpl)) == 1
    assert len(re.findall(r"\bconst slug\w*\s*=", tpl)) == 1
    assert r"[\u0300-\u036f]" in tpl
    for f in ("template.html", "template_simulateur.html", "sim-engine.js", "rt.js", "ev.js"):
        txt = (root / f).read_text()
        assert not re.search("[\u0300-\u036f]", txt), f"caractère combinant littéral dans {f}"


def test_slugs_uniques_et_propres(commune_names):
    slugs = [communes.slug(n) for n in commune_names]
    assert len(set(slugs)) == 100
    assert all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s) for s in slugs)
    assert communes.slug("Esch-sur-Alzette") == "esch-sur-alzette"
    assert communes.slug("Käerjeng") == "kaerjeng"


def test_pages_communales_existent(root, commune_names):
    for n in commune_names:
        assert (root / "municipality" / communes.slug(n) / "index.html").exists(), n
