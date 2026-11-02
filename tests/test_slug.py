"""Le slug d'une commune est calculé en Python (communes.slug, chemins des pages communales)
et en JS (slugC du tableau des communes, slug du sélecteur « Voir une commune ») : ils doivent
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
    slug_sel = _js_fn(tpl, r"const slug\s*=\s*(t\s*=>.*?);\n")
    out = node(READ_STDIN + f"const a = {slug_c}; const b = {slug_sel};"
               "process.stdout.write(JSON.stringify(names.map(n => [a(n), b(n)])));", commune_names)
    for name, (js_c, js_sel) in zip(commune_names, out):
        py = communes.slug(name)
        assert py == js_c == js_sel, (name, py, js_c, js_sel)


def test_slugs_uniques_et_propres(commune_names):
    slugs = [communes.slug(n) for n in commune_names]
    assert len(set(slugs)) == 100
    assert all(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", s) for s in slugs)
    assert communes.slug("Esch-sur-Alzette") == "esch-sur-alzette"
    assert communes.slug("Käerjeng") == "kaerjeng"


def test_pages_communales_existent(root, commune_names):
    for n in commune_names:
        assert (root / "municipality" / communes.slug(n) / "index.html").exists(), n
