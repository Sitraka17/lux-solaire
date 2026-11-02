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
 * (aide 500 €), commande le 15/11/2026, aide locale GÉNÉRIQUE de 50 % de l'aide de l'État
 * (plafonds 5 000 € PAC et PV, 1 125 € batterie). Sur la série de la maquette (autre lieu), le moteur
 * reproduit la maquette à 1e-10 près ; ici, l'écart de lieu donne 5,60 ans au lieu de 5,55. */
const SERIE = JSON.parse(fs.readFileSync(new URL('data/annee_type.json', root), 'utf8'));
const BAR = E.BAREMES;
const LOCALE = [
  { nom: 'aide locale (exemple)', base: 'pac', taux: 0.5, plafond: 5000 },
  { nom: 'aide locale (exemple)', base: 'pv', taux: 0.5, plafond: 5000 },
  { nom: 'aide locale (exemple)', base: 'batterie', taux: 0.5, plafond: 1125 },
];
const TYPE = {
  energie: 'gaz', conso: 2000, unite: 'm3', occupants: 4, emetteurs: 'radiateurs', elecBase: 3900,
  p: 8, cost: 8 * 1800, batt: 0, bcost: 0, hems: true, hcost: 1000, haid: 500, inv: 1500,
  pac: 9, pacCost: 22000, ballon: 300, ballonCost: 1800, commande: '2026-11-15', aidesLocales: LOCALE,
  prixGaz: 0.095, prixMazout: 1.60, price: 0.20, market: 0.07, hausseFossile: 3, growth: 1,
};
const heat = (o = {}) => E.computeHeat({ ...TYPE, ...o }, SERIE, BAR);

test('chauffage : cas type gaz, remboursement de D ≈ 5,6 ans et CO2 −73 %', () => {
  const R = heat();
  assert.ok(R.sc.D.pb > 5.5 && R.sc.D.pb < 5.7, `pb D = ${R.sc.D.pb}`);
  assert.ok(R.sc.D.co2Baisse > 0.725 && R.sc.D.co2Baisse < 0.735, `CO2 D = ${R.sc.D.co2Baisse}`);
  assert.ok(R.sc.C.pb > 5 && R.sc.C.pb < 5.3);
  assert.ok(R.sc.B.pb > 4.4 && R.sc.B.pb < 4.8);
  assert.equal(R.sc.D.cum.length, 21);                           // horizon de 20 ans
  assert.equal(R.sc.D.net, 14400 + 22000 + 1800 + 1000 - (7128 + 12000 + 500) - (3564 + 5000));
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
  assert.equal(L.parBase.pac, 5000);
  assert.equal(L.parBase.pv, 3564);
  assert.equal(L.parBase.batterie, 1125);
  assert.equal(L.total, 9689);
  assert.equal(E.localAid([], { pac: 12000 }).total, 0);
  assert.equal(heat({ aidesLocales: [] }).sc.D.aideLocale, 0);
  const src = fs.readFileSync(new URL('sim-engine.js', root), 'utf8');
  assert.ok(!/Differdange|Diff Primes/.test(src));
});

test('chauffage : COP horaire (Ruhnau et al. 2019)', () => {
  assert.ok(Math.abs(E.heatPumpCOP(35, BAR) - 0.85 * (6.08 - 0.09 * 35 + 0.0005 * 35 * 35)) < 1e-12);
  assert.equal(E.heatPumpCOP(5, BAR), E.heatPumpCOP(10, BAR));  // ΔT au moins 10 K
  assert.equal(E.heatPumpCOP(40, BAR, 0.1), 1);                   // jamais sous 1
  assert.ok(E.heatPumpCOP(25, BAR) > E.heatPumpCOP(45, BAR));
});

test('chauffage : besoin depuis la consommation, le besoin annuel ou la surface', () => {
  const a = heat().S;
  assert.ok(Math.abs(a.fuelKWh - 21200) < 1e-9 && Math.abs(a.useful - 18020) < 1e-9);
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
