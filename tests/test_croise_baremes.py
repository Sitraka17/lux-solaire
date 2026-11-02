"""Test croisé Python / JS des formules de barème : kb_pv, kb_batt, tarif et kb_pac (scripts/baremes.py,
FAQ du simulateur et tests) contre bonusPV, bonusBattery, feedInTariff et klimabonusPAC de sim-engine.js
(calcul réel des pages), sur une grille fine. Les deux copies des formules restent (le build Python
ne dépend pas de node) ; ce test garantit qu'elles ne divergent pas, à 1e-9 près."""
import itertools
import json

import baremes

TOL = 1e-9
# puissances 0 à 40 kWc au pas de 0,01 (bornes 2, 10 et 15 comprises, valeurs exactes en JSON)
PUISSANCES = [i / 100 for i in range(0, 4001)]
BATTERIES = [i / 100 for i in range(0, 2501)]          # 0 à 25 kWh au pas de 0,01
ANNEES = list(range(2019, 2036))                        # 2019 à 2035
PUISS_TARIF = [i / 10 for i in range(0, 401)]           # 0 à 40 kW au pas de 0,1 × 17 années

# PAC : dates de commande dans et hors de la période majorée (bornes comprises), avec ou sans facture
COMMANDES = [None, "2025-12-31", "2026-01-01", "2026-11-15", "2027-06-30", "2027-07-01", "2028-03-01"]
FACTURES = [None, "2027-01-15", "2028-12-31", "2029-01-01"]
COUTS_DIST = [0, -100, 500, 3999.99, 4000, 4000.01, 12000]
CAS_PAC = list(itertools.product(COMMANDES, FACTURES, (True, False), ("gaz", "mazout", "electrique"),
                                 (False, True), COUTS_DIST))

JS = """
const E = require('./sim-engine.js'), B = E.BAREMES;
const g = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify({
  pv: g.p.map(p => E.bonusPV(p, B)),
  batt: g.q.map(q => E.bonusBattery(q, B)),
  tarif: g.pt.map(p => g.y.map(y => E.feedInTariff(p, y, B))),
  pac: g.pac.map(c => E.klimabonusPAC({commande: c[0], facture: c[1], remplacement: c[2], energie: c[3],
                                       zoneEau: c[4], coutDistribution: c[5]}, B).total),
}));
"""


def _ecarts(py, js, cles):
    return [(k, a, b) for k, a, b in zip(cles, py, js) if abs(a - b) > TOL]


def test_formules_python_identiques_au_moteur(node):
    js = node(JS, {"p": PUISSANCES, "q": BATTERIES, "pt": PUISS_TARIF, "y": ANNEES, "pac": CAS_PAC})

    assert len(js["pv"]) == len(PUISSANCES)
    e = _ecarts([baremes.kb_pv(p) for p in PUISSANCES], js["pv"], PUISSANCES)
    assert not e, f"Klimabonus PV : {e[:5]}"

    e = _ecarts([baremes.kb_batt(q) for q in BATTERIES], js["batt"], BATTERIES)
    assert not e, f"Klimabonus batterie : {e[:5]}"

    cles = [(p, y) for p in PUISS_TARIF for y in ANNEES]
    e = _ecarts([baremes.tarif(p, y) for p, y in cles], [v for row in js["tarif"] for v in row], cles)
    assert not e, f"tarif d'injection : {e[:5]}"

    py = [baremes.kb_pac(c, f, rep, en == "mazout", ze, d) for c, f, rep, en, ze, d in CAS_PAC]
    e = _ecarts(py, js["pac"], CAS_PAC)
    assert not e, f"Klimabonus PAC : {e[:5]}"


def test_grille_couvre_les_cas_utiles():
    """Garde-fou sur la grille elle-même : bornes des barèmes et majoration PAC présentes."""
    pv, bt = baremes.B["klimabonus_pv"]["valeur"], baremes.B["klimabonus_batterie"]["valeur"]
    tr, kp = baremes.B["tarif_injection"]["valeur"], baremes.B["klimabonus_pac"]["valeur"]
    for x in (pv["pMin"], pv["pCap"], tr["seuilKw"]):
        assert x in PUISSANCES and x in PUISS_TARIF
    assert bt["qMin"] in BATTERIES and bt["qCap"] in BATTERIES
    assert kp["majoreCommandeDe"] in COMMANDES and kp["majoreCommandeA"] in COMMANDES
    assert kp["majoreFactureA"] in FACTURES
    assert kp["distMax"] / kp["distTaux"] in COUTS_DIST
    montants = {baremes.kb_pac(c, f, rep) for c, f, rep, *_ in CAS_PAC}
    assert {kp["remplacement"], kp["remplacementMajore"], kp["sansRemplacement"], kp["sansRemplacementMajore"]} <= montants
    assert json.loads(json.dumps(PUISSANCES)) == PUISSANCES
