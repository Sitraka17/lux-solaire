/* sim-engine.js : moteur de calcul du simulateur photovoltaïque de solaire.sitraka.lu,
 * étendu le 2/11/2026 au chauffage (pompe à chaleur air-eau, ballon tampon, aides, CO2).
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
    sources: "guichet.lu Klimabonus 2026 (11/08/2026), gouvernement.lu (16/07/2026), ILR (loi du 22/07/2026), petrol.lu (prix maximum du mazout, 27/10/2026), ILR gaz (30/06/2026), ADEME Base Carbone v23.9, Electricity Maps 2025",
    klimabonusPV: Object.freeze({ pMin: 2, pCap: 15, a: 1155, b: 35, max: 10000 }),
    klimabonusBatt: Object.freeze({ qMin: 2, qCap: 9, a: 500, b: 18, max: 2250 }),
    hems: Object.freeze({ aideMax: 500 }),
    tarif: Object.freeze({ seuilKw: 10, petit: 165, grand: 155, baisse: 0.97, anneeBase: 2019, duree: 15 }),
    horizon: 25,
    anneeOnduleur: 12,
    autoconso: Object.freeze({ base: 0.3, expo: -0.6, min: 0.1, max: 0.9, battGain: 0.35, battJour: 0.5 }),
    klimabonusPAC: Object.freeze({ remplacement: 10000, remplacementMajore: 12000, sansRemplacement: 6000, sansRemplacementMajore: 8000, majoreCommandeDe: "2026-01-01", majoreCommandeA: "2027-06-30", majoreFactureA: "2028-12-31", cuveMazout: 1500, zoneEau: 2000, distTaux: 0.5, distMax: 2000, ballonLParKw: 30, copMinA7W35: 3.1 }),
    energie: Object.freeze({ mazoutL: 1.601, gaz: 0.095, achat: 0.2, surplus: 0.07, hausseFossile: 3, hausseElec: 1 }),
    co2: Object.freeze({ gaz: 0.2154, mazout: 0.3247, elec: 0.2122 }),
    cop: Object.freeze({ a: 6.08, b: -0.09, c: 0.0005, dTmin: 10, f: 0.85 }),
    chaleur: Object.freeze({ horizon: 20, rendement: {"gaz": 0.85, "mazout": 0.8, "electrique": 1.0}, pcGazKwhM3: 10.6, pciMazoutKwhL: 10, ecsParPersonne: 800, ecsPartMax: 0.4, tBase: 15, depart: {"radiateurs": {"t0": 40, "pente": -1}, "plancher": {"t0": 30, "pente": -0.5}, "ecs": 50}, puissance: {"tRef": 7, "baisse": 0.25, "surK": 14, "min": 0.6, "max": 1.1}, ballon: {"whParLK": 1.163, "surchauffe": 15, "pertesParH": 0.01}, batterie: {"rendement": 0.9, "puissanceParKwh": 0.5, "puissanceMax": 5}, saisonBase: 0.15, profilBase: [0.55, 0.45, 0.4, 0.38, 0.38, 0.42, 0.6, 0.85, 0.95, 0.9, 0.88, 0.92, 1.0, 0.95, 0.85, 0.8, 0.85, 1.0, 1.25, 1.45, 1.4, 1.2, 0.95, 0.7], profilECS: [0.2, 0.1, 0.1, 0.1, 0.2, 0.6, 1.8, 2.2, 1.6, 0.9, 0.7, 0.7, 0.9, 0.7, 0.5, 0.5, 0.6, 0.9, 1.4, 1.8, 1.7, 1.2, 0.7, 0.4], besoinParEpoque: [190, 175, 165, 140, 105, 70, 40], epoques: ["avant 1949", "1949-1968", "1969-1978", "1979-1994", "1995-2008", "2009-2016", "après 2016"], entretien: {"gaz": 200, "mazout": 200, "electrique": 0, "pac": 150}, coutCuve: 1500 }),
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

  /* =====================================================================================
   * VOLET CHAUFFAGE (2/11/2026) : pompe à chaleur air-eau, ballon tampon, aides, CO2.
   * Simulation heure par heure sur une année météo type, hypothèses de l'outil lux-solaire
   * (voir CONTEXT.md, « Moteur du simulateur : chauffage »). Le moteur ne lit AUCUN fichier : la série horaire est passée en
   * paramètre (`serie` = { t2m_dixiemes[8760] (°C × 10), pv_w_par_kwc[8760] (W par kWc) },
   * format de data/annee_type.json). Barèmes : bar.klimabonusPAC, bar.energie, bar.co2,
   * bar.cop, bar.chaleur. Les fonctions photovoltaïques ci-dessus ne sont PAS modifiées :
   * computeHeat les appelle (bonusPV, bonusBattery, hemsAid, yieldPerKwc, cumulative,
   * payback, npvAt, irr). API documentée dans CONTEXT.md.
   * ===================================================================================== */

  // COP horaire (Ruhnau et al. 2019) : f × (a + b ΔT + c ΔT²), ΔT ≥ dTmin, au moins 1
  function heatPumpCOP(dT, bar, f) {
    var k = bar.cop, ff = (f === undefined || f === null) ? k.f : f;
    dT = Math.max(dT, k.dTmin);
    return Math.max(1, ff * (k.a + k.b * dT + k.c * dT * dT));
  }

  // compare deux dates ISO « AAAA-MM-JJ » (ordre lexicographique = ordre chronologique)
  function inRange(d, lo, hi) { return !!d && d >= lo && d <= hi; }

  /* Klimabonus PAC air-eau, maison unifamiliale.
   * o : { commande (date ISO, obligatoire pour la majoration), facture (date ISO, facultative),
   *       remplacement (booléen, défaut vrai : chaudière fossile ou chauffage électrique direct remplacé),
   *       energie ('gaz' | 'mazout' | 'electrique'), zoneEau (booléen), coutDistribution (€) }
   * → { pac, majore, cuve, zone, distribution, total } (€). Sans date de commande : pas de majoration. */
  function klimabonusPAC(o, bar) {
    var k = bar.klimabonusPAC, rep = o.remplacement !== false;
    var maj = inRange(o.commande, k.majoreCommandeDe, k.majoreCommandeA) && (!o.facture || o.facture <= k.majoreFactureA);
    var pac = rep ? (maj ? k.remplacementMajore : k.remplacement) : (maj ? k.sansRemplacementMajore : k.sansRemplacement);
    var oil = o.energie === 'mazout';
    var cuve = oil && rep ? k.cuveMazout : 0;
    var zone = oil && o.zoneEau ? k.zoneEau : 0;
    var dist = Math.min(k.distMax, k.distTaux * Math.max(0, o.coutDistribution || 0));
    return { pac: pac, majore: maj, cuve: cuve, zone: zone, distribution: dist, total: pac + cuve + zone + dist };
  }
  // volume minimal du ballon tampon exigé (L) ; 0 pour une PAC à modulation de vitesse ou de puissance
  function minBufferLitres(kw, modulante, bar) { return modulante ? 0 : kw * bar.klimabonusPAC.ballonLParKw; }

  /* Aide locale GÉNÉRIQUE (commune, etc.), calculée en part de l'aide de l'État.
   * aides : [{ nom, base ('pac' | 'pv' | 'batterie' | 'hems'), taux (fraction de l'aide de l'État),
   *            plafond (€, facultatif) }] ; etat : { pac, pv, batterie, hems } (€ d'aide de l'État par poste)
   * → { lignes: [{ nom, base, montant }], parBase: { pac, pv, batterie, hems }, total } */
  function localAid(aides, etat) {
    var parBase = { pac: 0, pv: 0, batterie: 0, hems: 0 }, lignes = [], total = 0;
    (aides || []).forEach(function (a) {
      var b = etat[a.base] || 0, m = a.taux * b;
      if (a.plafond !== undefined && a.plafond !== null) m = Math.min(m, a.plafond);
      m = Math.max(0, m);
      lignes.push({ nom: a.nom, base: a.base, montant: m });
      parBase[a.base] = (parBase[a.base] || 0) + m; total += m;
    });
    return { lignes: lignes, parBase: parBase, total: total };
  }

  /* Besoin de chaleur et séries horaires.
   * I : energie ('gaz' | 'mazout' | 'electrique'), rendement (fraction, défaut bar.chaleur.rendement),
   *   puis UNE des trois entrées, dans cet ordre de priorité :
   *     conso + unite ('m3' | 'L' | 'kWh') : combustible ou électricité de chauffage consommés par an ;
   *     besoin : chaleur utile par an (kWh, chauffage + eau chaude) ;
   *     surface (m²) + epoque (indice de bar.chaleur.epoques) ;
   *   occupants, elecBase (kWh/an hors chauffage), p (kWc, pour la série PV), pvScale (facultatif).
   * → { N, T[], pv[], heat[], ecs[], base[], fuelKWh, useful, heatY, ecsY, eta, estimated } */
  function heatDemand(I, serie, bar) {
    var c = bar.chaleur, N = serie.t2m_dixiemes.length, T = new Array(N), pv = new Array(N), i;
    var scale = I.pvScale || 1, p = I.p || 0;
    for (i = 0; i < N; i++) { T[i] = serie.t2m_dixiemes[i] / 10; pv[i] = serie.pv_w_par_kwc[i] / 1000 * p * scale; }
    var eta = (I.rendement !== undefined && I.rendement !== null) ? I.rendement : c.rendement[I.energie];
    var ecsY = (I.occupants || 0) * c.ecsParPersonne, fuelKWh, useful, heatY, estimated = false;
    if (I.conso !== undefined && I.conso !== null) {
      var u = I.unite || 'kWh';
      var k = u === 'kWh' ? 1 : (u === 'm3' ? c.pcGazKwhM3 : c.pciMazoutKwhL);
      fuelKWh = I.conso * k;
      useful = fuelKWh * eta;
      ecsY = Math.min(ecsY, c.ecsPartMax * useful);
      heatY = useful - ecsY;
    } else {
      estimated = true;
      heatY = (I.besoin !== undefined && I.besoin !== null) ? Math.max(0, I.besoin - ecsY) : I.surface * c.besoinParEpoque[I.epoque];
      if (I.besoin !== undefined && I.besoin !== null && I.besoin < ecsY) ecsY = I.besoin;
      useful = heatY + ecsY;
      fuelKWh = useful / eta;
    }
    var dh = 0; for (i = 0; i < N; i++) dh += Math.max(0, c.tBase - T[i]);
    var heat = new Array(N), ecs = new Array(N), base = new Array(N);
    var es = 0; for (i = 0; i < 24; i++) es += c.profilECS[i];
    var bsum = 0;
    for (i = 0; i < N; i++) {
      var h = i % 24, d = Math.floor(i / 24);
      heat[i] = heatY * Math.max(0, c.tBase - T[i]) / dh;
      ecs[i] = ecsY / (N / 24) * c.profilECS[h] / es;
      base[i] = c.profilBase[h] * (1 + c.saisonBase * Math.cos(2 * Math.PI * (d - 15) / 365));
      bsum += base[i];
    }
    var eb = I.elecBase || 0;
    for (i = 0; i < N; i++) base[i] = bsum > 0 ? base[i] * eb / bsum : 0;
    return { N: N, T: T, pv: pv, heat: heat, ecs: ecs, base: base, fuelKWh: fuelKWh, useful: useful,
             heatY: heatY, ecsY: ecsY, eta: eta, estimated: estimated };
  }

  /* Simulation heure par heure d'un scénario.
   * o : { pv, hp, buffer, battery (booléens), direct (chauffage électrique direct existant) }
   * I : pac (kW nominal), emetteurs ('radiateurs' | 'plancher'), ballon (L), surchauffe (K), batt (kWh),
   *     copF (facteur f, facultatif).
   * → { imp, exp, pv, self, hpEl, backupEl, scop, hpH[] (si keep), Emax } (kWh/an) */
  function simulateHourly(S, I, o, bar, keep) {
    var c = bar.chaleur, N = S.N, imp = 0, exp = 0, pvTot = 0, hpEl = 0, backupEl = 0, E = 0;
    var dT = (I.surchauffe !== undefined && I.surchauffe !== null) ? I.surchauffe : c.ballon.surchauffe;
    var Emax = o.buffer ? (I.ballon || 0) * c.ballon.whParLK / 1000 * dT : 0;
    var Bmax = o.battery ? (I.batt || 0) : 0, B = 0;
    var Pb = Math.min(Bmax * c.batterie.puissanceParKwh, c.batterie.puissanceMax), ec = Math.sqrt(c.batterie.rendement);
    var dep = c.depart[I.emetteurs === 'plancher' ? 'plancher' : 'radiateurs'], pw = c.puissance, f = I.copF;
    var hpH = keep ? new Array(N) : null;
    for (var i = 0; i < N; i++) {
      var T = S.T[i], pv = o.pv ? S.pv[i] : 0, base = S.base[i], el = 0;
      pvTot += pv;
      if (o.hp) {
        var sinkH = dep.t0 + dep.pente * T;
        var copH = heatPumpCOP(sinkH - T, bar, f), copW = heatPumpCOP(c.depart.ecs - T, bar, f);
        var qh = S.heat[i], qw = S.ecs[i];
        E *= (1 - c.ballon.pertesParH);
        // déficit solaire : la chaleur stockée sert d'abord (chauffage, puis eau chaude)
        var avail = pv - base;
        if (E > 0) {
          var needEl = qh / copH + qw / copW;
          if (avail < needEl) {
            var coverable = avail > 0 ? (needEl - avail) : needEl;
            var copMix = (qh + qw) > 0 ? (qh + qw) / needEl : copH;
            var take = Math.min(E, coverable * copMix);
            var t1 = Math.min(take, qh); qh -= t1; var t2 = Math.min(take - t1, qw); qw -= t2;
            E -= (t1 + t2);
          }
        }
        var capF = Math.min(pw.max, Math.max(pw.min, 1 + (T - pw.tRef) * pw.baisse / pw.surK));
        var cap = (I.pac || 0) * capF;
        var q = qh + qw, served = Math.min(q, cap), backup = q - served;
        var share = q > 0 ? served / q : 0;
        var e1 = share * (qh / copH + qw / copW);
        el = e1 + backup;
        hpEl += e1; backupEl += backup;
        // surplus solaire : charge du ballon à une eau plus chaude
        var net = pv - base - el;
        if (o.buffer && net > 0 && E < Emax) {
          var sinkC = Math.max(sinkH + dT, c.depart.ecs);
          var copC = heatPumpCOP(sinkC - T, bar, f);
          var room = Math.min(Emax - E, (cap - served) > 0 ? (cap - served) : 0, net * copC);
          if (room > 0) { E += room; var ec2 = room / copC; el += ec2; hpEl += ec2; }
        }
        if (keep) hpH[i] = el;
      } else if (o.direct) {
        el = (S.heat[i] + S.ecs[i]) / S.eta;
      }
      var bal = pv - base - el;
      if (Bmax > 0) {
        if (bal > 0) { var ch = Math.min(bal, Pb, (Bmax - B) / ec); B += ch * ec; bal -= ch; }
        else if (bal < 0) { var dch = Math.min(-bal, Pb, B * ec); B -= dch / ec; bal += dch; }
      }
      if (bal >= 0) exp += bal; else imp -= bal;
    }
    return { imp: imp, exp: exp, pv: pvTot, self: pvTot - exp, hpEl: hpEl, backupEl: backupEl,
             scop: o.hp ? S.useful / (hpEl + backupEl) : null, hpH: hpH, Emax: Emax };
  }

  /* ---- calcul global : photovoltaïque + batterie + HEMS + pompe à chaleur + ballon ----
   * I (entrées ; valeur par défaut entre crochets, prise dans bar) :
   *   logement : energie, conso + unite | besoin | surface + epoque, rendement, occupants, emetteurs,
   *              elecBase (kWh/an hors chauffage) ;
   *   photovoltaïque (mêmes noms que compute) : p (kWc), cost (€ posé), batt (kWh), bcost (€),
   *              hems (booléen), hcost (€), haid (€ demandés, plafonnés par hemsAid), inv (onduleur, €) ;
   *              facultatif : az, tilt, canton (avec pvgis : la série PV est remise à l'échelle de
   *              yieldPerKwc, sinon elle est prise telle quelle) ;
   *   pompe à chaleur : pac (kW), pacCost (€), ballon (L), ballonCost (€), surchauffe (K), copF,
   *              coutCuve (€, mazout) [bar.chaleur.coutCuve], coutDistribution (€), chaudiereEvitee (€) ;
   *   aides : commande, facture (dates ISO), remplacement [vrai], zoneEau, aidesLocales [{nom, base, taux,
   *              plafond}] ; kbPV, kbBatt, kbPAC (forçages facultatifs en €) ;
   *   prix : prixGaz (€/kWh PCS) [bar.energie.gaz], prixMazout (€/L) [bar.energie.mazoutL],
   *          price (électricité €/kWh) [bar.energie.achat], market (surplus €/kWh) [bar.energie.surplus],
   *          hausseFossile, growth (%/an) [bar.energie.hausseFossile, hausseElec], horizon (ans) [bar.chaleur.horizon],
   *          disc (%, actualisation du seul gain net, 0 par défaut) ;
   *   co2 : facteurs facultatifs co2Gaz, co2Mazout, co2Elec (kg/kWh) [bar.co2].
   * serie : année type horaire (voir heatDemand). pvgis : facultatif.
   * Scénarios : A situation actuelle ; B panneaux (+ batterie), chauffage inchangé ; C pompe à chaleur
   * seule ; D panneaux + pompe à chaleur + ballon (+ batterie, + HEMS) ; D0 = D sans ballon (énergie seulement).
   * Chaque scénario : { inv, aideEtat, aideLocale, evite, net, fuelKWh, fuelCost, elCost, sale, maint, bill,
   *   co2 (t/an), co2Baisse (fraction vs A), energie: simulateHourly, cum[] (dépense cumulée, horizon+1),
   *   cf[] (flux de l'écart avec A), ecart[] (= cumulative(cf)), pb (années ou null), gain (vs A à l'horizon,
   *   ou valeur actualisée si disc > 0), irr (fraction ou null), save (économie de la 1re année vs A) }. */
  function computeHeat(I, serie, bar, pvgis) {
    var c = bar.chaleur, en = bar.energie, def = function (v, d) { return (v === undefined || v === null) ? d : v; };
    var energie = I.energie || 'gaz', isOil = energie === 'mazout', isEl = energie === 'electrique';
    var nativeY = 0; for (var h = 0; h < serie.pv_w_par_kwc.length; h++) nativeY += serie.pv_w_par_kwc[h] / 1000;
    var pvScale = (pvgis && I.canton) ? yieldPerKwc(pvgis, def(I.az, 0), def(I.tilt, 35), I.canton) / nativeY : 1;
    var S = heatDemand(Object.assign({}, I, { energie: energie, pvScale: pvScale }), serie, bar);
    var hasBat = (I.batt || 0) > 0, hasBuf = (I.ballon || 0) > 0;
    var R = {
      A: simulateHourly(S, I, { pv: false, hp: false, direct: isEl }, bar),
      B: simulateHourly(S, I, { pv: true, hp: false, direct: isEl, battery: hasBat }, bar),
      C: simulateHourly(S, I, { pv: false, hp: true }, bar, true),
      D: simulateHourly(S, I, { pv: true, hp: true, buffer: hasBuf, battery: hasBat }, bar, true),
      D0: simulateHourly(S, I, { pv: true, hp: true, buffer: false, battery: hasBat }, bar, true)
    };
    var prixGaz = def(I.prixGaz, en.gaz), prixMazout = def(I.prixMazout, en.mazoutL);
    var pel = def(I.price, en.achat), pinj = def(I.market, en.surplus);
    var gf = def(I.hausseFossile, en.hausseFossile), ge = def(I.growth, en.hausseElec);
    var fuelPrice = isOil ? prixMazout / c.pciMazoutKwhL : (isEl ? 0 : prixGaz);
    var fCO2 = isOil ? def(I.co2Mazout, bar.co2.mazout) : (isEl ? 0 : def(I.co2Gaz, bar.co2.gaz));
    var fEl = def(I.co2Elec, bar.co2.elec);
    // aides de l'État (fonctions photovoltaïques existantes, inchangées)
    var kbPV = def(I.kbPV, bonusPV(I.p || 0, bar));
    var kbBat = hasBat ? def(I.kbBatt, bonusBattery(I.batt, bar)) : 0;
    var kbH = hemsAid(!!I.hems, def(I.haid, bar.hems.aideMax), bar, I.hcost);
    var kp = klimabonusPAC({ commande: I.commande, facture: I.facture, remplacement: I.remplacement,
                             energie: energie, zoneEau: I.zoneEau, coutDistribution: I.coutDistribution }, bar);
    var kbPAC = def(I.kbPAC, kp.total);
    var loc = localAid(I.aidesLocales, { pac: kbPAC, pv: kbPV, batterie: kbBat, hems: kbH });
    var cPV = I.p > 0 ? (I.cost || 0) : 0, cBat = hasBat ? (I.bcost || 0) : 0;
    var cHP = (I.pacCost || 0) + (isOil ? def(I.coutCuve, c.coutCuve) : 0) + (I.coutDistribution || 0);
    var cHems = I.hems ? (I.hcost || 0) : 0, evite = I.chaudiereEvitee || 0;
    var mFuel = c.entretien[energie] || 0, mHP = c.entretien.pac;
    var lpv = loc.parBase.pv + loc.parBase.batterie;
    var sc = {
      A: { inv: 0, aideEtat: 0, aideLocale: 0, fuelKWh: isEl ? 0 : S.fuelKWh, r: R.A, maint: mFuel, pvOn: false, evite: 0 },
      B: { inv: cPV + cBat, aideEtat: kbPV + kbBat, aideLocale: lpv, fuelKWh: isEl ? 0 : S.fuelKWh, r: R.B, maint: mFuel, pvOn: true, evite: 0 },
      C: { inv: cHP, aideEtat: kbPAC, aideLocale: loc.parBase.pac, fuelKWh: 0, r: R.C, maint: mHP, pvOn: false, evite: evite },
      D: { inv: cPV + cBat + cHP + (hasBuf ? (I.ballonCost || 0) : 0) + cHems, aideEtat: kbPV + kbBat + kbPAC + kbH,
           aideLocale: lpv + loc.parBase.pac + loc.parBase.hems, fuelKWh: 0, r: R.D, maint: mHP, pvOn: true, evite: evite }
    };
    var Y = def(I.horizon, c.horizon), disc = I.disc || 0, k;
    for (k in sc) {
      var s = sc[k];
      s.net = s.inv - s.aideEtat - s.aideLocale - s.evite;
      s.fuelCost = s.fuelKWh * fuelPrice;
      s.elCost = s.r.imp * pel;
      s.sale = s.r.exp * pinj;
      s.bill = s.fuelCost + s.elCost - s.sale + s.maint;
      s.co2 = (s.fuelKWh * fCO2 + s.r.imp * fEl) / 1000;
      s.bills = [];
      s.cum = [s.net];
      for (var y = 1; y <= Y; y++) {
        var b = s.fuelCost * Math.pow(1 + gf / 100, y - 1) + s.elCost * Math.pow(1 + ge / 100, y - 1) - s.sale + s.maint;
        if (s.pvOn && y === bar.anneeOnduleur + 1) b += (I.inv || 0);
        s.bills.push(b);
        s.cum.push(s.cum[y - 1] + b);
      }
    }
    for (k in sc) {
      var t = sc[k];
      t.save = sc.A.bill - t.bill;
      t.co2Baisse = sc.A.co2 > 0 ? 1 - t.co2 / sc.A.co2 : 0;
      t.energie = t.r; delete t.r;
      if (k === 'A') { t.cf = null; t.ecart = null; t.pb = null; t.gain = 0; t.irr = null; continue; }
      t.cf = [-t.net].concat(t.bills.map(function (v, i) { return sc.A.bills[i] - v; }));
      t.ecart = cumulative(t.cf);
      t.pb = payback(t.ecart);
      t.gain = netGain(t.cf, disc);
      t.irr = irr(t.cf);
    }
    var d = R.D, d0 = R.D0;
    var ballon = {
      partSansBallon: d0.pv > 0 ? d0.self / d0.pv : 0, partAvecBallon: d.pv > 0 ? d.self / d.pv : 0,
      kWhAchatEvites: d0.imp - d.imp, kWhSurplusPerdus: d0.exp - d.exp,
      gainAchat: (d0.imp - d.imp) * pel, gainNet: (d0.imp - d.imp) * pel - (d0.exp - d.exp) * pinj,
      capaciteKWh: d.Emax, cout: hasBuf ? (I.ballonCost || 0) : 0
    };
    return { S: { fuelKWh: S.fuelKWh, useful: S.useful, heatY: S.heatY, ecsY: S.ecsY, eta: S.eta, estimated: S.estimated,
                  pvScale: pvScale },
             sc: sc, D0: R.D0, ballon: ballon, horizon: Y, fuelPrice: fuelPrice, energie: energie,
             aides: { kbPV: kbPV, kbBatt: kbBat, kbHems: kbH, pac: kp, kbPAC: kbPAC, locales: loc } };
  }

  return Object.freeze({
    BAREMES: BAREMES,
    gridYield: gridYield, yieldPerKwc: yieldPerKwc, selfShare: selfShare,
    bonusPV: bonusPV, bonusBattery: bonusBattery, hemsAid: hemsAid, feedInTariff: feedInTariff,
    annualFlows: annualFlows, cumulative: cumulative, npvAt: npvAt, netGain: netGain,
    payback: payback, irr: irr, analyse: analyse, compute: compute,
    heatPumpCOP: heatPumpCOP, klimabonusPAC: klimabonusPAC, minBufferLitres: minBufferLitres, localAid: localAid,
    heatDemand: heatDemand, simulateHourly: simulateHourly, computeHeat: computeHeat,
  });
});
