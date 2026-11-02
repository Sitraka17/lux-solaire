/* sim-engine.js : moteur de calcul du simulateur photovoltaïque de solaire.sitraka.lu.
 *
 * Fonctions PURES : aucun accès au DOM, aucune variable globale lue ou écrite
 * (hors l'export final). Toutes les règles chiffrées (aides, tarifs, horizon,
 * heuristique d'autoconsommation) viennent d'UN objet de barèmes passé en
 * paramètre ; BAREMES ci-dessous est celui du site (sources relues le 2/11/2026),
 * régénéré par scripts/build.py depuis scripts/baremes.json (source unique).
 * Chargement : script classique (<script src="/sim-engine.js">) qui expose
 * window.SimEngine, ou require() / createRequire() sous Node (CommonJS).
 * API documentée dans CONTEXT.md, section « Moteur du simulateur ».
 * Aucun texte affiché ici : la mise en forme et les libellés restent dans la page.
 */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module && module.exports) module.exports = api;
  else root.SimEngine = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /* Barèmes du site. Formules :
   *  Klimabonus PV       : 0 sous pMin kWc ; p × (a − a/b × p) jusqu'à pCap ; max au-delà
   *  Klimabonus batterie : 0 sous qMin kWh ; q × (a − a/b × q) jusqu'à qCap ; max au-delà
   *  Aide HEMS           : montant saisi, plafonné à aideMax ET au coût du HEMS, option A seulement
   *  Tarif garanti       : (p ≤ seuilKw ? petit : grand) × baisse^(année − anneeBase) / 1000 €/kWh,
   *                        pendant duree ans, puis prix de marché
   *  Autoconsommation    : s = base × (prod/cons)^expo borné à [min, max] ; batterie :
   *                        + battGain × (1 − exp(−batt / (battJour × cons/365))), borné à max */
  /* BAREMES:DEBUT : bloc régénéré par scripts/build.py depuis scripts/baremes.json, ne pas éditer à la main. anneeOnduleur = indice d'année (0 = première année). */
  var BAREMES = Object.freeze({
    version: "2026-11-02",
    sources: "guichet.lu Klimabonus 2026 (11/08/2026), gouvernement.lu (16/07/2026), ILR (loi du 22/07/2026)",
    klimabonusPV: Object.freeze({ pMin: 2, pCap: 15, a: 1155, b: 35, max: 10000 }),
    klimabonusBatt: Object.freeze({ qMin: 2, qCap: 9, a: 500, b: 18, max: 2250 }),
    hems: Object.freeze({ aideMax: 500 }),
    tarif: Object.freeze({ seuilKw: 10, petit: 165, grand: 155, baisse: 0.97, anneeBase: 2019, duree: 15 }),
    horizon: 25,
    anneeOnduleur: 12,
    autoconso: Object.freeze({ base: 0.3, expo: -0.6, min: 0.1, max: 0.9, battGain: 0.35, battJour: 0.5 }),
  });
  /* BAREMES:FIN */

  /* ---- productible ---- */
  // kWh par kWc et par an au centre du pays (grille PVGIS), symétrie est/ouest
  function gridYield(pvgis, az, tilt) {
    var g = pvgis.grid;
    if (tilt === 0) return g['0:0'];
    var v = g[az + ':' + tilt];
    return v !== undefined && v !== null ? v : g[(-az) + ':' + tilt];
  }
  // même chose corrigée du facteur cantonal
  function yieldPerKwc(pvgis, az, tilt, canton) {
    return gridYield(pvgis, az, tilt) * pvgis.cantons[canton].factor;
  }

  /* ---- autoconsommation (heuristique maison, voir CONTEXT.md) ---- */
  function selfShare(prod, cons, batt, bar) {
    var k = bar.autoconso;
    var s = k.base * Math.pow(prod / cons, k.expo);
    s = Math.min(k.max, Math.max(k.min, s));
    if (batt > 0) { var daily = cons / 365; s += k.battGain * (1 - Math.exp(-batt / (k.battJour * daily))); }
    return Math.min(k.max, s);
  }

  /* ---- aides et tarifs ---- */
  function bonusPV(p, bar) {
    var k = bar.klimabonusPV;
    return p < k.pMin ? 0 : (p < k.pCap ? p * (k.a - k.a / k.b * p) : k.max);
  }
  function bonusBattery(q, bar) {
    var k = bar.klimabonusBatt;
    return q < k.qMin ? 0 : (q < k.qCap ? q * (k.a - k.a / k.b * q) : k.max);
  }
  // cost (facultatif) : coût saisi du HEMS ; l'aide ne peut pas le dépasser (un HEMS à 0 €
  // ne rapporte pas 500 €)
  function hemsAid(hems, amount, bar, cost) {
    if (!hems) return 0;
    var cap = (cost === undefined || cost === null) ? bar.hems.aideMax : Math.min(cost, bar.hems.aideMax);
    return Math.max(0, Math.min(amount, cap));
  }
  // €/kWh, selon la puissance et l'année de première injection
  function feedInTariff(p, year, bar) {
    var k = bar.tarif;
    return (p <= k.seuilKw ? k.petit : k.grand) * Math.pow(k.baisse, year - k.anneeBase) / 1000;
  }

  /* ---- flux annuels ----
   * o : { capex (net de l'aide déduite), self, inj (kWh de la 1re année), price, growth (%/an),
   *       deg (%/an), inv (onduleur, €), injPrice(y) (€/kWh pour l'année y) }
   * Renvoie { cf, gains } : cf[0] = −capex, cf[1..N] = gain de l'année (onduleur déduit) ;
   * gains[y] = gain brut de l'année y (sans l'onduleur). */
  function annualFlows(o, bar) {
    var cf = [-o.capex], gains = [];
    for (var y = 0; y < bar.horizon; y++) {
      var f = Math.pow(1 - o.deg / 100, y);
      var price = o.price * Math.pow(1 + o.growth / 100, y);
      var g = o.self * f * price + o.inj * f * o.injPrice(y);
      gains.push(g);
      if (y === bar.anneeOnduleur) g -= o.inv;
      cf.push(g);
    }
    return { cf: cf, gains: gains };
  }

  /* ---- indicateurs ---- */
  function cumulative(cf) {
    var cum = [], acc = 0;
    cf.forEach(function (v) { acc += v; cum.push(acc); });
    return cum;
  }
  // valeur actualisée nette au taux r (fraction, 0.03 = 3 %)
  function npvAt(cf, r) {
    return cf.reduce(function (a, v, t) { return a + v / Math.pow(1 + r, t); }, 0);
  }
  // gain net : trésorerie cumulée en fin d'horizon (disc = 0) ou somme des flux actualisés (disc en %)
  function netGain(cf, disc) {
    var r = disc / 100;
    if (r > 0) return npvAt(cf, r);
    var cum = cumulative(cf);
    return cum[cum.length - 1];
  }
  // années (fractionnaires) avant que la trésorerie cumulée redevienne positive ; null si jamais
  function payback(cum) {
    for (var y = 1; y < cum.length; y++) {
      if (cum[y] >= 0 && cum[y - 1] < 0) return (y - 1) + (-cum[y - 1]) / (cum[y] - cum[y - 1]);
    }
    return cum[0] >= 0 ? 0 : null;
  }
  // taux de rendement interne par dichotomie sur [−99 %, 100 %] ; null hors de l'intervalle
  function irr(cf) {
    var lo = -0.99, hi = 1.0;
    var f = function (r) { return npvAt(cf, r); };
    if (f(lo) * f(hi) > 0) return null;
    for (var i = 0; i < 80; i++) { var m = (lo + hi) / 2; if (f(m) > 0) lo = m; else hi = m; }
    return (lo + hi) / 2;
  }
  function analyse(flows, disc) {
    var cum = cumulative(flows.cf);
    return { cum: cum, pb: payback(cum), npv: netGain(flows.cf, disc), irr: irr(flows.cf), y1: flows.gains[0] };
  }

  /* ---- calcul complet ----
   * I (entrées) : p (kWc), az (°, 0 = sud), tilt (°), canton, cons (kWh/an), batt (kWh utiles),
   *   scAuto (booléen), sc (% si scAuto est faux), cost, bcost, hcost, haid (€), hems (booléen),
   *   inv (€), year (1re injection), price (€/kWh évité), growth (%/an), market (€/kWh),
   *   deg (%/an), disc (%, 0 = non actualisé).
   * pvgis : data/pvgis.json (grid, cantons[].factor). bar : objet de barèmes (BAREMES). */
  function compute(I, pvgis, bar) {
    var P = I.p, cons = I.cons;
    var ey = yieldPerKwc(pvgis, I.az, I.tilt, I.canton);
    var prod = P * ey;
    var sc = I.scAuto ? selfShare(prod, cons, I.batt, bar) : I.sc / 100;
    var self = Math.min(prod * sc, cons), inj = prod - self;
    var bonus = bonusPV(P, bar) + bonusBattery(I.batt, bar) + hemsAid(I.hems, I.haid, bar, I.hcost);
    var capexGross = I.cost + (I.batt > 0 ? I.bcost : 0) + (I.hems ? I.hcost : 0);
    var tar = feedInTariff(P, I.year, bar);
    var base = { self: self, inj: inj, price: I.price, growth: I.growth, deg: I.deg, inv: I.inv };
    // option A : Klimabonus déduit, surplus au prix de marché ; option B : tarif garanti puis marché
    var fA = annualFlows(Object.assign({}, base, { capex: capexGross - bonus,
      injPrice: function () { return I.market; } }), bar);
    var fB = annualFlows(Object.assign({}, base, { capex: capexGross - 0,
      injPrice: function (y) { return y < bar.tarif.duree ? tar : I.market; } }), bar);
    var A = analyse(fA, I.disc), B = analyse(fB, I.disc);
    var prodTotal = 0;
    for (var y = 0; y < bar.horizon; y++) prodTotal += prod * Math.pow(1 - I.deg / 100, y);
    return { P: P, cons: cons, ey: ey, prod: prod, sc: sc, self: self, inj: inj, bonus: bonus,
             capexGross: capexGross, tar: tar, A: A, B: B,
             lcoeA: (capexGross - bonus + I.inv) / prodTotal, lcoeB: (capexGross + I.inv) / prodTotal };
  }

  return Object.freeze({
    BAREMES: BAREMES,
    gridYield: gridYield, yieldPerKwc: yieldPerKwc, selfShare: selfShare,
    bonusPV: bonusPV, bonusBattery: bonusBattery, hemsAid: hemsAid, feedInTariff: feedInTariff,
    annualFlows: annualFlows, cumulative: cumulative, npvAt: npvAt, netGain: netGain,
    payback: payback, irr: irr, analyse: analyse, compute: compute,
  });
});
