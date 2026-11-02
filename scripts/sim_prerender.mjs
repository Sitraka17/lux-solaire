// Pré-rendu statique du simulateur : calcule, avec le MÊME moteur que la page
// (/sim-engine.js et ses barèmes), le scénario par défaut et trois profils
// types, et imprime le résultat en JSON pour build.py, qui l'injecte dans le
// HTML servi (les robots et les aperçus voient des chiffres, pas des tirets ;
// le JS de la page recalcule ensuite à l'identique).
//
// Usage : node scripts/sim_prerender.mjs
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';

const require = createRequire(import.meta.url);
const E = require('../sim-engine.js');
const pv = JSON.parse(readFileSync(new URL('../data/pvgis.json', import.meta.url), 'utf8'));

// valeurs par défaut des champs de template_simulateur.html (coût = kWc × 1 800 €, batterie × 900 €)
const base = { az: 0, tilt: 35, canton: 'Luxembourg', batt: 0, sc: 30, scAuto: true, bcost: 0,
               hcost: 1000, haid: 500, hems: false, inv: 1400, year: 2027, price: 0.2, growth: 1,
               market: 0.05, deg: 0.5, disc: 0 };
const cases = {
  defaut: { ...base, p: 6, cons: 3900, cost: 10800 },
  p1: { ...base, p: 3, az: 45, cons: 2500, cost: 5400 },
  p2: { ...base, p: 6, cons: 4500, cost: 10800 },
  p3: { ...base, p: 10, cons: 10000, batt: 7, bcost: 6300, cost: 18000 },
};
const pick = (r) => ({ y1: r.y1, pb: r.pb, npv: r.npv, irr: r.irr });
const out = {};
for (const [k, I] of Object.entries(cases)) {
  const R = E.compute(I, pv, E.BAREMES);
  out[k] = { I, P: R.P, cons: R.cons, ey: R.ey, prod: R.prod, sc: R.sc, self: R.self, inj: R.inj,
             bonus: R.bonus, capexGross: R.capexGross, tar: R.tar, lcoeA: R.lcoeA, lcoeB: R.lcoeB,
             A: pick(R.A), B: pick(R.B) };
}
process.stdout.write(JSON.stringify(out));
