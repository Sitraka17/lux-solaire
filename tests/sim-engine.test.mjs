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
