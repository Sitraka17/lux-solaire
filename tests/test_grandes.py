"""Grandes installations, lignes apparues (scripts/grandes.py) : comparaison en multi-ensemble des lignes
de plus de 100 kW (seuil exclu) entre deux copies du fichier Leneda par installation."""
import json
from datetime import date

import pandas as pd

import grandes

PV = "Installation photovoltaïque"


def _df(rows):
    """rows = [(LAU2, commune, filière, kW)]"""
    return pd.DataFrame([{"LAU1": 1, "Commune": c, "LAU2": l, "Canton": "K", "Type d'installation": t,
                          "Puissance installée [kW]": kw} for l, c, t, kw in rows])


BASE = [(202, "Differdange", PV, 150.0), (202, "Differdange", PV, 20.0), (304, "Luxembourg", PV, 500.0)]


def test_nouvelle_ligne():
    ev = grandes.diff_big(_df(BASE), _df(BASE + [(202, "Differdange", PV, 999.6)]))
    assert [(x["l"], x["kw"], x["e"], x["m"], x["r"]) for x in ev] == [(202, 999.6, 1, None, 0)]
    assert ev[0]["c"] == "Differdange"


def test_ligne_disparue():
    ev = grandes.diff_big(_df(BASE), _df(BASE[1:]))
    assert [(x["l"], x["kw"], x["e"]) for x in ev] == [(202, 150.0, -1)]


def test_inchangee():
    assert grandes.diff_big(_df(BASE), _df(list(reversed(BASE)))) == []


def test_seuil_100_kw_exclu():
    ev = grandes.diff_big(_df(BASE), _df(BASE + [(202, "Differdange", PV, 100.0), (202, "Differdange", PV, 100.01)]))
    assert [x["kw"] for x in ev] == [100.01]
    assert grandes.count_big(_df([(1, "A", PV, 100.0)])) == {}
    assert grandes.count_big(_df([(1, "A", PV, 100.01)])) == {1: 1}


def test_petites_lignes_ignorees():
    assert grandes.diff_big(_df(BASE), _df(BASE + [(202, "Differdange", PV, 30.0)])) == []


def test_doublons_multi_ensemble():
    two = BASE + [(204, "Esch", PV, 199.5)] * 2
    ev = grandes.diff_big(_df(two), _df(two + [(204, "Esch", PV, 199.5)]))
    assert [(x["l"], x["kw"], x["e"]) for x in ev] == [(204, 199.5, 1)]


def test_changement_de_commune_signale():
    old = BASE + [(703, "Ell", "Eolienne", 12600.0)]
    new = BASE + [(704, "Rambrouch", "Eolienne", 12600.0)]
    ev = {x["e"]: x for x in grandes.diff_big(_df(old), _df(new))}
    assert ev[1]["m"] == 703 and ev[1]["mc"] == "Ell"
    assert ev[-1]["m"] == 704 and ev[-1]["mc"] == "Rambrouch"


def test_meme_commune_meme_filiere_signale():
    old = BASE + [(410, "Nommern", "Biogaz", 300.0)]
    new = BASE + [(410, "Nommern", "Biogaz", 350.0)]
    ev = grandes.diff_big(_df(old), _df(new))
    assert sorted((x["e"], x["r"]) for x in ev) == [(-1, 1), (1, 1)]


def test_detect_paires_et_comptes():
    s1, s2, s3 = _df(BASE), _df(BASE + [(202, "Differdange", PV, 999.6)]), _df(BASE[1:] + [(202, "Differdange", PV, 999.6)])
    b = grandes.detect([(date(2026, 11, 2), s3), (date(2026, 9, 14), s1), (date(2026, 10, 26), s2)], lambda d: d.isoformat())
    assert [s["iso"] for s in b["snaps"]] == ["2026-09-14", "2026-10-26", "2026-11-02"]
    assert [(x["p"], x["e"], x["kw"]) for x in b["ev"]] == [(2, -1, 150.0), (1, 1, 999.6)]
    assert b["n"]["202"] == [1, 1] and b["n"]["304"] == [1, 1] and b["nat"] == [2, 2]
    assert grandes.detect([(date(2026, 9, 14), s1)], str) is None


def test_rendu_quatre_langues_sans_entree():
    b = grandes.detect([(date(2026, 9, 14), _df(BASE)), (date(2026, 10, 26), _df(BASE))], lambda d: d.isoformat())
    for lang in ("fr", "en", "de", "lb"):
        h = grandes.dashboard_section(b, lang, "/x/", lambda n: n.lower())
        assert 'class="bignone"' in h and "<table" not in h and "—" not in h
        c = grandes.commune_section(b, lang, 202, "Differdange", "/")
        assert 'class="bignone"' in c and "—" not in c


def test_lede_dit_la_periode_reelle():
    """Le chapeau du tableau de bord donne la période couverte (premier et dernier relevé) et la part
    du dernier relevé, au lieu de laisser croire à un seul intervalle hebdomadaire."""
    s1, s2 = _df(BASE), _df(BASE + [(202, "Differdange", PV, 999.6)])
    s3 = _df(BASE + [(202, "Differdange", PV, 999.6), (304, "Luxembourg", PV, 4623.84)])
    b = grandes.detect([(date(2026, 9, 14), s1), (date(2026, 10, 26), s2), (date(2026, 11, 2), s3)],
                       lambda d: d.isoformat())
    for lang in ("fr", "en", "de", "lb"):
        h = grandes.dashboard_section(b, lang, "/x/", lambda n: n.lower())
        lede = h.split('class="lede">')[1].split("</p>")[0]
        assert lede.count("2026-09-14") == 2 and "2026-11-02" in lede and " 3 " in lede, (lang, lede)
        assert "Entre deux relevés" not in lede and "Between two" not in lede
    # DE / LB : l'année du relevé n'est jamais collée au nombre d'installations
    for lang in ("de", "lb"):
        c = grandes.commune_section(b, lang, 202, "Differdange", "/")
        assert "2026-11-02 <strong>" not in c and "<strong>2 " in c, (lang, c)


def test_parite_des_textes():
    keys = set(grandes.S["fr"])
    assert all(set(grandes.S[l]) == keys for l in ("en", "de", "lb"))
    assert all(set(grandes.TYPE_NAMES[l]) == set(grandes.TYPE_CODE) for l in grandes.TYPE_NAMES)


def test_noms_des_filieres_alignes_sur_le_mix(root):
    fr = {"Installation photovoltaïque": "Photovoltaïque", "Eolienne": "Éolien", "Biomasse": "Biomasse",
          "Cogénération": "Cogénération", "Installation hydroélectrique": "Hydroélectrique", "Biogaz": "Biogaz"}
    assert grandes.TYPE_NAMES["fr"] == fr
    for lang, f in (("en", "i18n_js.json"), ("de", "i18n_de_js.json"), ("lb", "i18n_lb_js.json")):
        d = json.loads((root / "scripts" / f).read_text())
        for t, name in fr.items():
            assert d[f"name:'{name}'"] == f"name:'{grandes.TYPE_NAMES[lang][t]}'", (lang, t)


def test_fmt_kw():
    assert grandes.fmt_kw(4623.84, "fr") == "4 623,84"
    assert grandes.fmt_kw(12600.0, "en") == "12,600"
    assert grandes.fmt_kw(120.10, "de") == "120,1"
