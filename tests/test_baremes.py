"""scripts/baremes.json est la source unique des barèmes : valeurs clés, formules, alignement
avec sim-engine.js et contrôle des chiffres cités dans les phrases rendues."""
import copy
import json

import pytest

import baremes
import build


def test_structure_et_dates():
    b = baremes.load()
    for k in ("klimabonus_pv", "klimabonus_batterie", "aide_hems", "tarif_injection", "klimabonus_gemengen", "modele"):
        for f in ("valeur", "source", "date_source", "date_verification"):
            assert f in b[k], (k, f)
        if k != "modele":
            assert b[k]["source"].startswith("https://"), k


def test_valeurs_cles():
    b = baremes.B
    assert b["klimabonus_pv"]["valeur"] == {"pMin": 2, "pCap": 15, "a": 1155, "b": 35, "max": 10000}
    assert b["klimabonus_pv"]["valeur"]["a"] / b["klimabonus_pv"]["valeur"]["b"] == 33
    assert b["klimabonus_batterie"]["valeur"] == {"qMin": 2, "qCap": 9, "a": 500, "b": 18, "max": 2250}
    assert b["aide_hems"]["valeur"]["aideMax"] == 500
    t = b["tarif_injection"]["valeur"]
    assert (t["petit"], t["grand"], t["baisse"], t["anneeBase"], t["seuilKw"], t["duree"]) == (165, 155, 0.97, 2019, 10, 15)
    g = b["klimabonus_gemengen"]["valeur"]
    assert g["bareme"] == 2025
    assert [(x["taux"], x["plafond"]) for x in g["tranches"]] == [(50, 675), (45, 505), (40, 425)]
    assert (g["ombriere"]["taux"], g["ombriere"]["plafond"]) == (45, 990)


def test_formules():
    assert baremes.kb_pv(1.9) == 0
    assert baremes.kb_pv(6) == pytest.approx(5742)          # 6 × (1 155 − 33 × 6)
    assert baremes.kb_pv(14.99) < 10000 and baremes.kb_pv(15) == 10000 and baremes.kb_pv(30) == 10000
    assert baremes.kb_batt(1.5) == 0 and baremes.kb_batt(9) == 2250
    assert baremes.kb_batt(5) == pytest.approx(5 * (500 - 500 / 18 * 5))
    assert baremes.tarif(6, 2026) == pytest.approx(0.165 * 0.97 ** 7)     # 0,1333 €/kWh
    assert baremes.tarif(10, 2019) == pytest.approx(0.165)
    assert baremes.tarif(10.5, 2019) == pytest.approx(0.155)


def test_tranches_gemengen():
    assert baremes.kb_edges() == [0, 30, 200, 500, 5000, None]
    assert baremes.kb_labels() == ["0–30", "30–200", "200–500", "0,5–5 MW", "> 5 MW"]
    assert build.KB_EDGES == baremes.kb_edges() and build.KB_LABELS == baremes.kb_labels()


def test_montants_faq_simulateur():
    fr, en = build.sim_numbers("fr"), build.sim_numbers("en")
    assert fr["__KB6__"] == "5 742" and en["__KB6__"] == "5,742"
    assert fr["__NET6LO__"] == "3 900" and fr["__NET6HI__"] == "7 500"
    assert fr["__C6LO__"] == "9 600" and fr["__C6HI__"] == "13 200"
    assert fr["__TAR26__"] == "13,3" and en["__TAR27__"] == "12.9"


def test_sim_engine_aligne_sur_baremes(root, node):
    src = (root / "sim-engine.js").read_text()
    assert baremes.engine_js() in src, "bloc BAREMES de sim-engine.js à régénérer (lancer build.py)"
    js = node("process.stdout.write(JSON.stringify(require('./sim-engine.js').BAREMES));")
    assert js == baremes.engine_bar()


def test_page_simulateur_inline_les_baremes(root):
    tpl = (root / "template_simulateur.html").read_text()
    assert "BAR = Object.freeze(__BAREMES_JSON__)" in tpl
    page = (root / "fr" / "simulateur" / "index.html").read_text()
    assert json.dumps(baremes.engine_bar(), ensure_ascii=False, separators=(",", ":")) in page


SIM_OK = ("<p>l'aide vaut P × (1 155 − 33 × P) euros sous 15 kWc et 10 000 euros à partir de 15 kWc. "
          "Q × (500 − 500/18 × Q) euros, 2 250 € à partir de 9 kWh. Un système (HEMS) reçoit 500 €. "
          "165 × 0,97<sup>n−2019</sup> €/MWh jusqu'à 10 kW, 155 × 0,97<sup>n−2019</sup> au-delà.</p>")
DASH_OK = ("<p>(Klimabonus Gemengen, barème 2025 révisé chaque année) : 50 % des coûts entre 30 et 200 kWc "
           "(plafond 675 €/kWc), 45 % entre 200 et 500 kWc (505 €/kWc), 40 % entre 0,5 et 5 MWc (425 €/kWc) ; "
           "ombrière de parking : 45 % (990 €/kWc).</p>")


def test_controle_phrases_valides():
    assert baremes.check_page(SIM_OK, "fr", "sim") == []
    assert baremes.check_page(DASH_OK, "fr", "dash") == []
    en = ("P × (1,155 − 33 × P) €, €10,000 from 15 kWp; Q × (500 − 500/18 × Q) €, €2,250 from 9 kWh; "
          "(HEMS) connected to two devices: €500. 165 × 0.97<sup>n−2019</sup> €/MWh up to 10 kW, 155 × 0.97<sup>n−2019</sup>")
    assert baremes.check_page(en, "en", "sim") == []


@pytest.mark.parametrize("old,new", [
    ("1 155 − 33", "1 200 − 33"), ("10 000 euros", "9 000 euros"), ("2 250 €", "2 000 €"),
    ("500/18", "500/20"), ("reçoit 500 €", "reçoit 600 €"), ("165 × 0,97", "160 × 0,97"),
    ("n−2019</sup> €/MWh jusqu'à 10", "n−2019</sup> €/MWh jusqu'à 12"), ("0,97<sup>n−2019</sup> au", "0,96<sup>n−2019</sup> au"),
])
def test_controle_phrases_simulateur_perimees(old, new):
    assert old in SIM_OK
    assert baremes.check_page(SIM_OK.replace(old, new), "fr", "sim")


@pytest.mark.parametrize("old,new", [
    ("barème 2025", "barème 2024"), ("675 €", "700 €"), ("45 % entre", "46 % entre"), ("(990", "(1 000"),
    ("0,5 et 5 MWc", "0,5 et 6 MWc"),
])
def test_controle_phrases_gemengen_perimees(old, new):
    assert old in DASH_OK
    assert baremes.check_page(DASH_OK.replace(old, new), "fr", "dash")


def test_controle_phrase_absente():
    """Une phrase reformulée hors des motifs connus ne doit pas rendre le contrôle muet."""
    assert any("absent" in p for p in baremes.check_page("<p>rien</p>", "fr", "sim"))


def test_bareme_modifie_detecte_dans_les_pages_rendues(root):
    b = copy.deepcopy(baremes.B)
    b["klimabonus_pv"]["valeur"]["max"] = 9000
    page = (root / "de" / "rechner" / "index.html").read_text()
    assert baremes.check_page(page, "de", "sim") == []
    assert baremes.check_page(page, "de", "sim", b)
