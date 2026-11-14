// Tests du moteur du simulateur : node --test tests/sim-engine.test.mjs (ou node --test à la racine)
// Les valeurs de référence (fixtures/sim-reference.json) ont été calculées AVANT la
// refactorisation, avec l'ancien code inline de template_simulateur.html (commit d2cc47b),
// par tests/gen_reference_old.mjs : l'égalité stricte prouve que les résultats n'ont pas changé.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const E = require('../sim-engine.js');
const root = new URL('..', import.meta.url);
const G = JSON.parse(fs.readFileSync(new URL('data/pvgis.json', root), 'utf8'));
const CASES = JSON.parse(fs.readFileSync(new URL('tests/fixtures/sim-cases.json', root), 'utf8'));
const REF = JSON.parse(fs.readFileSync(new URL('tests/fixtures/sim-reference.json', root), 'utf8'));
const run = name => E.compute(CASES.find(c => c.name === name).inputs, G, E.BAREMES);
const json = v => JSON.parse(JSON.stringify(v));   // même sérialisation que les références

test('au moins 6 cas de référence, tous présents des deux côtés', () => {
  assert.ok(CASES.length >= 6);
  assert.deepEqual(Object.keys(REF).sort(), CASES.map(c => c.name).sort());
});

for (const c of CASES) {
  test(`identique à l'ancien code : ${c.name}`, () => {
    assert.deepEqual(json(E.compute(c.inputs, G, E.BAREMES)), REF[c.name]);
  });
}

test('6 kWc, première injection 2027 : Klimabonus et tarif garanti', () => {
  const R = run('6kwc_2027_defaut');
  assert.equal(Math.round(R.bonus), 5742);                 // 6 × (1 155 − 33 × 6)
  assert.equal(Math.round(R.tar * 1000) / 10, 12.9);       // 165 × 0,97^8 / 1000 €/kWh
  assert.equal(R.A.cum.length, 26);
  assert.ok(R.A.pb > 9 && R.A.pb < 10);
});

test('8 kWc avec batterie de 10 kWh : aide batterie plafonnée à 2 250 €', () => {
  const R = run('8kwc_batterie_10kwh_esch_se');
  assert.equal(E.bonusBattery(10, E.BAREMES), 2250);
  assert.equal(R.bonus, E.bonusPV(8, E.BAREMES) + 2250);
  assert.equal(R.capexGross, 14400 + 9000);
  assert.ok(R.sc > run('6kwc_2027_defaut').sc);            // la batterie relève l'autoconsommation
});

test('15 kWc et plus : Klimabonus PV plafonné à 10 000 €, tarif des 10 à 30 kW', () => {
  assert.equal(E.bonusPV(15, E.BAREMES), 10000);
  assert.equal(E.bonusPV(18, E.BAREMES), 10000);
  assert.ok(E.bonusPV(14.5, E.BAREMES) < 10000);
  const R = run('18kwc_plafonds_2029');
  assert.equal(R.bonus, 10000 + 2250);
  assert.equal(R.tar, E.feedInTariff(30, 2029, E.BAREMES));
  assert.ok(E.feedInTariff(10, 2029, E.BAREMES) > R.tar);
});

test("l'année de première injection ne change que l'option B", () => {
  const a = run('6kwc_2026_tarif'), b = run('6kwc_2029_tarif');
  assert.deepEqual(json(a.A), json(b.A));
  assert.ok(a.tar > b.tar && a.B.npv > b.B.npv);
  assert.equal(Math.round(a.tar / b.tar * 1e6) / 1e6, Math.round(0.97 ** -3 * 1e6) / 1e6);
});

test('actualisation 0 % puis 3 % : seul le gain net change', () => {
  const r0 = run('6kwc_2027_defaut'), r3 = run('6kwc_2027_actualise_3pct');
  assert.equal(r0.A.npv, r0.A.cum[25]);                     // non actualisé = trésorerie cumulée
  assert.ok(r3.A.npv < r0.A.npv && r3.B.npv < r0.B.npv);
  assert.deepEqual(r3.A.cum, r0.A.cum);
  assert.equal(r3.A.pb, r0.A.pb);
  assert.equal(r3.A.irr, r0.A.irr);
});

test('aide HEMS : option A seulement, plafonnée par le barème', () => {
  assert.equal(E.hemsAid(false, 500, E.BAREMES), 0);
  assert.equal(E.hemsAid(true, 300, E.BAREMES), 300);
  assert.equal(E.hemsAid(true, 900, E.BAREMES), 500);
});

test('aide HEMS plafonnée au coût saisi du HEMS', () => {
  assert.equal(E.hemsAid(true, 500, E.BAREMES, 0), 0);
  assert.equal(E.hemsAid(true, 500, E.BAREMES, 300), 300);
  assert.equal(E.hemsAid(true, 500, E.BAREMES, 1000), 500);
  // dans compute : un HEMS gratuit ne fait rien gagner en option A
  const base = CASES[0].inputs;
  const sans = E.compute({ ...base, hems: false }, G, E.BAREMES);
  const gratuit = E.compute({ ...base, hems: true, hcost: 0, haid: 500 }, G, E.BAREMES);
  assert.equal(gratuit.A.npv, sans.A.npv);
  const moitie = E.compute({ ...base, hems: true, hcost: 300, haid: 500 }, G, E.BAREMES);
  assert.equal(moitie.A.npv, sans.A.npv);   // coût 300 €, aide 300 € : neutre en option A
});

test('jamais remboursé : retour sur investissement null', () => {
  const R = run('2kwc_facade_est_clervaux_jamais');
  assert.equal(R.A.pb, null);
  assert.equal(R.B.pb, null);
});

test('les barèmes viennent bien du paramètre', () => {
  const bar = { ...E.BAREMES, klimabonusPV: { ...E.BAREMES.klimabonusPV, max: 8000 } };
  assert.equal(E.bonusPV(20, bar), 8000);
  const c = CASES.find(x => x.name === '18kwc_plafonds_2029').inputs;
  assert.equal(E.compute(c, G, bar).bonus, 8000 + 2250);
});

/* ===================== Volet chauffage (computeHeat, 2/11/2026) =====================
 * Série horaire : data/annee_type.json (PVGIS 5.3, Luxembourg-Ville, année type 2017), passée en
 * paramètre (le moteur ne lit aucun fichier). Cas type = maison de 140 m² des années 1980 au gaz
 * (2 000 m³/an), 8 kWc à 1 800 €/kWc, PAC 9 kW à 22 000 €, ballon 300 L à 1 800 €, HEMS 1 000 €
 * (aide 500 €), commande le 15/11/2026, aide locale GÉNÉRIQUE aux valeurs FICTIVES (30 % de l'aide
 * de l'État sur la PAC plafonnés à 2 000 €, 20 % sur les panneaux plafonnés à 1 000 €) : aucun
 * barème communal réel dans ce dépôt public. Sans aide locale, D se rembourse en ≈ 9,2 ans.
 * Conversion du gaz : 1 m³ = 10,99 kWh (fiche Enovos 2026, depuis le 9/11/2026 ; 10,6 auparavant). */
const SERIE = JSON.parse(fs.readFileSync(new URL('data/annee_type.json', root), 'utf8'));
const BAR = E.BAREMES;
const LOCALE = [
  { nom: 'aide locale (exemple fictif)', base: 'pac', taux: 0.3, plafond: 2000 },
  { nom: 'aide locale (exemple fictif)', base: 'pv', taux: 0.2, plafond: 1000 },
];
const TYPE = {
  energie: 'gaz', conso: 2000, unite: 'm3', occupants: 4, emetteurs: 'radiateurs', elecBase: 3900,
  p: 8, cost: 8 * 1800, batt: 0, bcost: 0, hems: true, hcost: 1000, haid: 500, inv: 1500,
  pac: 9, pacCost: 22000, ballon: 300, ballonCost: 1800, commande: '2026-11-15', aidesLocales: LOCALE,
  prixGaz: 0.095, prixMazout: 1.60, price: 0.20, market: 0.07, hausseFossile: 3, growth: 1,
};
const heat = (o = {}) => E.computeHeat({ ...TYPE, ...o }, SERIE, BAR);

test('chauffage : cas type gaz, remboursement de D ≈ 8,0 ans (9,2 sans aide locale) et CO2 −73 %', () => {
  const R = heat();
  assert.ok(R.sc.D.pb > 7.9 && R.sc.D.pb < 8.05, `pb D = ${R.sc.D.pb}`);
  assert.ok(R.sc.D.co2Baisse > 0.725 && R.sc.D.co2Baisse < 0.735, `CO2 D = ${R.sc.D.co2Baisse}`);
  assert.ok(R.sc.C.pb > 7.4 && R.sc.C.pb < 7.55, `pb C = ${R.sc.C.pb}`);
  assert.ok(R.sc.B.pb > 7.6 && R.sc.B.pb < 7.9);
  assert.ok(Math.abs(heat({ aidesLocales: [] }).sc.D.pb - 9.24) < 0.05);
  assert.equal(R.sc.D.cum.length, 21);                           // horizon de 20 ans
  assert.equal(R.sc.D.net, 14400 + 22000 + 1800 + 1000 - (7128 + 12000 + 500) - (1000 + 2000));
  assert.ok(R.sc.C.energie.scop > 2.9 && R.sc.C.energie.scop < 3.1);
});

test('chauffage : Klimabonus PAC, majoration selon les dates de commande et de facture', () => {
  const kb = o => E.klimabonusPAC({ energie: 'gaz', ...o }, BAR).pac;
  assert.equal(kb({ commande: '2026-01-01' }), 12000);
  assert.equal(kb({ commande: '2027-06-30', facture: '2028-12-31' }), 12000);
  assert.equal(kb({ commande: '2027-07-01' }), 10000);
  assert.equal(kb({ commande: '2025-12-31' }), 10000);
  assert.equal(kb({ commande: '2026-11-15', facture: '2029-01-02' }), 10000);
  assert.equal(kb({}), 10000);                                   // sans date : pas de majoration
  assert.equal(kb({ commande: '2026-11-15', remplacement: false }), 8000);
  assert.equal(kb({ remplacement: false }), 6000);
});

test('chauffage : bonus mazout (cuve, zone de protection d\'eau) et adaptation de la distribution', () => {
  const k = E.klimabonusPAC({ energie: 'mazout', commande: '2026-11-15', zoneEau: true, coutDistribution: 3000 }, BAR);
  assert.deepEqual([k.pac, k.cuve, k.zone, k.distribution, k.total], [12000, 1500, 2000, 1500, 17000]);
  assert.equal(E.klimabonusPAC({ energie: 'mazout', coutDistribution: 10000 }, BAR).distribution, 2000);
  assert.equal(E.klimabonusPAC({ energie: 'gaz', zoneEau: true }, BAR).zone, 0);
  assert.equal(E.minBufferLitres(9, false, BAR), 270);
  assert.equal(E.minBufferLitres(9, true, BAR), 0);              // PAC à modulation : dispensée
});

test('chauffage : aide locale générique en paramètre, aucun barème communal dans le moteur', () => {
  const L = E.localAid(LOCALE, { pac: 12000, pv: 7128, batterie: 3000, hems: 500 });
  assert.equal(L.parBase.pac, 2000);                             // 30 % de 12 000 = 3 600, plafonné
  assert.equal(L.parBase.pv, 1000);                              // 20 % de 7 128 = 1 425,6, plafonné
  assert.equal(L.parBase.batterie, 0);
  assert.equal(L.total, 3000);
  assert.equal(E.localAid(LOCALE, { pac: 6000 }).parBase.pac, 1800);
  assert.equal(E.localAid([], { pac: 12000 }).total, 0);
  assert.equal(heat({ aidesLocales: [] }).sc.D.aideLocale, 0);
  // garde public / privé : aucun nom ni barème communal dans le moteur ; aucun plafond du barème
  // privé ni renvoi à la maquette privée dans les tests, la documentation et les barèmes
  const eng = fs.readFileSync(new URL('sim-engine.js', root), 'utf8');
  assert.ok(!new RegExp(['Differdange', 'Diff ?Primes', 'maquette'].join('|'), 'i').test(eng));
  for (const f of ['sim-engine.js', 'tests/sim-engine.test.mjs', 'CONTEXT.md', 'scripts/baremes.json']) {
    const src = fs.readFileSync(new URL(f, root), 'utf8');
    assert.ok(!new RegExp(['maquette' + '-pac', 'maquette ' + 'PAC', '1[  ]?' + '125\\b'].join('|'), 'i').test(src), f);
  }
});

test('chauffage : COP horaire (Ruhnau et al. 2019)', () => {
  assert.ok(Math.abs(E.heatPumpCOP(35, BAR) - 0.85 * (6.08 - 0.09 * 35 + 0.0005 * 35 * 35)) < 1e-12);
  assert.equal(E.heatPumpCOP(5, BAR), E.heatPumpCOP(10, BAR));  // ΔT au moins 10 K
  assert.equal(E.heatPumpCOP(40, BAR, 0.1), 1);                   // jamais sous 1
  assert.ok(E.heatPumpCOP(25, BAR) > E.heatPumpCOP(45, BAR));
});

test('chauffage : besoin depuis la consommation, le besoin annuel ou la surface', () => {
  const a = heat().S;
  assert.ok(Math.abs(a.fuelKWh - 21980) < 1e-9 && Math.abs(a.useful - 18683) < 1e-9);
  assert.equal(a.ecsY, 3200);
  const b = heat({ conso: null, besoin: 15000 }).S;
  assert.equal(b.useful, 15000);
  assert.equal(b.fuelKWh, 15000 / 0.85);
  const c = heat({ conso: null, surface: 140, epoque: 3 }).S;
  assert.equal(c.heatY, 140 * 140);
  assert.ok(c.estimated && !a.estimated);
});

test('chauffage : chauffage électrique direct comme situation actuelle', () => {
  const R = heat({ energie: 'electrique', conso: 15000, unite: 'kWh' });
  assert.equal(R.sc.A.fuelKWh, 0);
  assert.ok(Math.abs(R.sc.A.energie.imp - (3900 + 15000)) < 1e-6);
  assert.ok(Math.abs(R.sc.A.co2 - 18900 * BAR.co2.elec / 1000) < 1e-6);
  assert.equal(R.aides.pac.pac, 12000);                          // remplacement d'un chauffage électrique direct
  assert.ok(R.sc.C.energie.imp < R.sc.A.energie.imp / 2);
});

test('chauffage : ballon tampon, gain d\'autoconsommation faible (≈ 90 € d\'achats évités par an)', () => {
  const R = heat();
  assert.ok(R.ballon.partAvecBallon > R.ballon.partSansBallon);
  assert.ok(R.ballon.gainAchat > 70 && R.ballon.gainAchat < 110, `gainAchat = ${R.ballon.gainAchat}`);
  assert.ok(R.ballon.gainNet > 0 && R.ballon.gainNet < R.ballon.gainAchat);
  assert.ok(Math.abs(R.ballon.capaciteKWh - 300 * 1.163 * 15 / 1000) < 1e-9);
  const S = heat({ ballon: 0 });
  assert.equal(S.sc.D.energie.imp, S.D0.imp);
  assert.equal(S.ballon.gainAchat, 0);
});

test('chauffage : réutilise les fonctions photovoltaïques sans changer leurs résultats', () => {
  const R = heat({ batt: 6, bcost: 5400 });
  assert.equal(R.aides.kbPV, E.bonusPV(8, BAR));
  assert.equal(R.aides.kbBatt, E.bonusBattery(6, BAR));
  assert.equal(R.aides.kbHems, E.hemsAid(true, 500, BAR, 1000));
  for (const c of CASES) assert.deepEqual(json(E.compute(c.inputs, G, BAR)), REF[c.name]);
  // série PV remise à l'échelle du productible PVGIS du simulateur quand un canton est donné
  const Q = E.computeHeat({ ...TYPE, canton: 'Clervaux', az: 0, tilt: 35 }, SERIE, BAR, G);
  assert.ok(Math.abs(Q.sc.B.energie.pv - 8 * E.yieldPerKwc(G, 0, 35, 'Clervaux')) < 1e-6);
  assert.equal(heat().S.pvScale, 1);                              // sans pvgis : série telle quelle
});

test('chauffage : flux, cumul et gain cohérents ; actualisation du seul gain net', () => {
  const R = heat(), D = R.sc.D, A = R.sc.A;
  assert.ok(Math.abs(D.gain - (A.cum[20] - D.cum[20])) < 1e-6);
  assert.ok(Math.abs(D.ecart[20] - D.gain) < 1e-6);
  assert.equal(D.cf.length, 21);
  assert.ok(D.irr > 0.1 && D.irr < 0.3);
  const R3 = heat({ disc: 3 });
  assert.ok(R3.sc.D.gain < D.gain);
  assert.equal(R3.sc.D.pb, D.pb);
  // onduleur compté la 13e année dans les scénarios avec panneaux seulement
  assert.ok(Math.abs((D.cum[13] - D.cum[12]) - D.bills[12]) < 1e-9);
  assert.ok(Math.abs(D.bills[12] - D.bills[11] - 1500) < 200);
});

test('chauffage : mazout au prix maximum de baremes.json, CO2 du fioul', () => {
  const R = heat({ energie: 'mazout', conso: 2000, unite: 'L', prixMazout: undefined });
  assert.equal(R.fuelPrice, BAR.energie.mazoutL / 10);
  assert.ok(Math.abs(R.sc.A.co2 - (20000 * BAR.co2.mazout + 3900 * BAR.co2.elec) / 1000) < 1e-9);
  assert.equal(R.aides.pac.cuve, 1500);
  assert.ok(R.sc.C.pb < heat().sc.C.pb);                         // le mazout rembourse plus vite que le gaz
});

test('chauffage : barèmes et série viennent des paramètres (déterministe)', () => {
  assert.deepEqual(json(heat()), json(heat()));
  const bar = { ...BAR, klimabonusPAC: { ...BAR.klimabonusPAC, remplacementMajore: 11000 } };
  assert.equal(E.computeHeat({ ...TYPE }, SERIE, bar).aides.pac.pac, 11000);
  const doux = { ...SERIE, t2m_dixiemes: SERIE.t2m_dixiemes.map(t => t + 20) };
  const a = heat(), b = E.computeHeat({ ...TYPE }, doux, BAR);
  assert.ok(b.sc.C.energie.scop > a.sc.C.energie.scop);          // hiver plus doux : meilleur SCOP
  assert.ok(Math.abs(b.S.useful - a.S.useful) < 1e-9);           // même besoin (tiré de la facture)
});

// L3.4 (lot 3, 9/11/2026) : l'étiquette de l'option ne contredit jamais le verdict
test('verdict : profil par défaut, options à égalité (< 2 %), étiquette au retour le plus rapide', () => {
  const R = run('6kwc_2027_defaut');
  const V = E.pickOption(R.A, R.B);
  assert.equal(V.tie, true);                       // +6 975 € contre +6 950 € : écart de 0,4 %
  assert.equal(V.label, 'fast');
  assert.equal(V.tag, 'A');                        // 9,5 ans contre 11,7 ans
  assert.ok(R.A.pb <= R.B.pb);
  assert.equal(V.lead, V.tag);
});

test('verdict : sur tous les cas de référence et une grille de réglages, étiquette cohérente avec le verdict', () => {
  const base = CASES.find(c => c.name === '6kwc_2027_defaut').inputs;
  const inputs = CASES.map(c => c.inputs);
  for (const p of [2, 3, 6, 10, 15, 20, 30]) for (const cons of [2000, 3900, 8000]) for (const market of [0.02, 0.05, 0.1])
    inputs.push({ ...base, p, cons, market, cost: p * 1800 });
  for (const I of inputs) {
    const R = E.compute(I, G, E.BAREMES), V = E.pickOption(R.A, R.B);
    const T = V.tag === 'A' ? R.A : V.tag === 'B' ? R.B : null, O = V.tag === 'A' ? R.B : R.A;
    if (V.tag) assert.equal(V.lead, V.tag);
    if (!V.tie) { assert.equal(V.label, 'win'); assert.ok(T.npv >= O.npv); assert.ok(V.diff >= 100); }
    else {
      assert.equal(V.label, 'fast');
      assert.ok(V.diff < 100 || V.diff < 0.02 * Math.max(Math.abs(R.A.npv), Math.abs(R.B.npv)));
      if (T) assert.ok(O.pb === null || T.pb <= O.pb);
      else assert.ok(R.A.pb === null && R.B.pb === null);
    }
  }
});

/* ===================== Compléments du 9/11/2026 : gaz décomposé, prime fournisseur, TVA travaux ===================== */
test('gaz : prix TTC par m³ et par kWh à partir des composantes hors TVA (fiche Enovos 2026)', () => {
  const g = E.gasPrice({}, BAR);
  assert.ok(Math.abs(g.lignes.reseau - 0.248 * 0.967) < 1e-12);           // €/Nm³ ramené au m³
  assert.ok(Math.abs(g.htM3 - (0.49497 + 0.248 * 0.967 + 0.01187 + 0.10023)) < 1e-12);
  assert.ok(Math.abs(g.ttcM3 - g.htM3 * 1.08) < 1e-12);
  assert.ok(Math.abs(g.ttcKwh * 100 - 8.32) < 0.01, `c€/kWh = ${g.ttcKwh * 100}`);  // 8,32 c€/kWh TTC
  assert.ok(Math.abs(E.gasPrice({ fourniture: 0.5345 }, BAR).ttcM3 - (0.5345 + g.htM3 - 0.49497) * 1.08) < 1e-12);
  assert.ok(Math.abs(E.gasFixed({}, BAR) - 12 * (8.69 + 6) * 1.08) < 1e-9);
  // une facture en m³ coûte m³ × prix TTC du m³ : même conversion pour la consommation et le prix
  const R = heat({ prixGaz: g.ttcKwh });
  assert.ok(Math.abs(R.sc.A.fuelCost - 2000 * g.ttcM3) < 1e-6);
});

test('chauffage : frais fixes du gaz payés tant que le gaz reste raccordé (A, B), prime fournisseur (C, D)', () => {
  const base = heat(), R = heat({ fixeGaz: 190, aidePrivee: 1700 });
  assert.ok(Math.abs(R.sc.A.bill - base.sc.A.bill - 190) < 1e-9);
  assert.ok(Math.abs(R.sc.B.bill - base.sc.B.bill - 190) < 1e-9);
  assert.equal(R.sc.C.bill, base.sc.C.bill);
  assert.equal(R.sc.D.net, base.sc.D.net - 1700);
  assert.equal(R.sc.C.net, base.sc.C.net - 1700);
  assert.equal(R.sc.B.net, base.sc.B.net);
  assert.ok(R.sc.D.pb < base.sc.D.pb);
  assert.equal(heat({ energie: 'mazout', unite: 'L', fixeGaz: 190 }).fixeGaz, 0);   // mazout : pas de frais fixes du gaz
  assert.deepEqual([BAR.primeFournisseurPAC.min, BAR.primeFournisseurPAC.max, BAR.tvaTravaux.normal, BAR.tvaTravaux.reduit], [1700, 2500, 0.17, 0.03]);
});

/* ============ e-community de Differdange : même surplus, deux tarifs (14/11/2026) ============ */
const near = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} ≠ ${b}`);

test('e-community : 1 000 kWh à 2 c€ = 20 €, à 7,5 c€ = 75 €, écart +55 €', () => {
  const c = E.surplusComparison(1000, 0.02, 0.075);
  near(c.sans, 20); near(c.avec, 75); near(c.diff, 55); assert.equal(c.kWh, 1000);
});

test('e-community : surplus nul ou négatif = revenu nul dans les deux scénarios', () => {
  for (const q of [0, -50, undefined, NaN]) {
    const c = E.surplusComparison(q, 0.02, 0.075);
    assert.equal(c.kWh, 0); assert.equal(c.sans, 0); assert.equal(c.avec, 0); assert.equal(c.diff, 0);
  }
});

test('e-community : tarif habituel supérieur à 7,5 c€ = écart négatif, affiché tel quel', () => {
  const c = E.surplusComparison(1000, 0.09, 0.075);
  near(c.diff, -15); assert.ok(c.avec < c.sans);
});

test('mois de l\'année type : 8 760 heures, 1er juin = heure 3 624, juin à août = 92 jours', () => {
  assert.equal(E.monthOfHour(0), 0); assert.equal(E.monthOfHour(8759), 11);
  assert.equal(E.monthOfHour(151 * 24 - 1), 4); assert.equal(E.monthOfHour(151 * 24), 5);
  let h = 0; for (let i = 0; i < 8760; i++) if ([5, 6, 7].includes(E.monthOfHour(i))) h++;
  assert.equal(h, 92 * 24);
  assert.equal(E.sumMonths([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], [5, 6, 7]), 6 + 7 + 8);
});

test('surplus mensuel : somme des 12 mois = surplus annuel, autoconsommation exclue (pas de double comptage)', () => {
  const R = heat({ p: 8, pac: 9, ballon: 300 });
  for (const k of ['B', 'D']) {
    const r = R.sc[k].energie;
    assert.equal(r.expM.length, 12);
    near(r.expM.reduce((a, b) => a + b, 0), r.exp, 1e-6);
    near(r.self + r.exp, r.pv, 1e-6);                 // chaque kWh produit est soit consommé, soit injecté
    const ete = E.sumMonths(r.expM, [5, 6, 7]);
    assert.ok(ete > 0 && ete < r.exp);
    assert.ok(ete <= E.sumMonths(r.expM, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]));
  }
});

test('e-community : seul le tarif du surplus change, le scénario sans adhésion est inchangé', () => {
  const sans = heat({ p: 8, pac: 9, market: 0.02 }), avec = heat({ p: 8, pac: 9, market: 0.075 });
  const ref = heat({ p: 8, pac: 9, market: 0.02 });
  for (const k of ['B', 'D']) {
    assert.deepEqual(sans.sc[k].energie, avec.sc[k].energie);           // mêmes volumes
    near(avec.sc[k].sale - sans.sc[k].sale, sans.sc[k].energie.exp * 0.055, 1e-6);
    assert.deepEqual(json(sans.sc[k]), json(ref.sc[k]));                // déterministe, rien d'autre ne bouge
  }
  assert.equal(sans.sc.A.bill, avec.sc.A.bill);                         // pas de panneaux : A inchangé
  assert.equal(sans.sc.C.bill, avec.sc.C.bill);
});

test('options A/B de l\'outil 2 : non touchées par la comparaison (compute inchangé)', () => {
  const c = CASES[0];
  assert.deepEqual(json(E.compute(c.inputs, G, E.BAREMES)), REF[c.name]);
});
