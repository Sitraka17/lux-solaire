// Régénère tests/fixtures/sim-reference.json avec l'ANCIEN code du simulateur (avant
// l'extraction de sim-engine.js), pour prouver que la refactorisation ne change aucun résultat :
//   git show d2cc47b:template_simulateur.html > /tmp/old.html
//   node tests/gen_reference_old.mjs /tmp/old.html data/pvgis.json tests/fixtures/sim-cases.json tests/fixtures/sim-reference.json
// Valeurs générées le 2/11/2026 depuis le commit d2cc47b. Ne PAS régénérer depuis le nouveau code.
import fs from 'node:fs';
import vm from 'node:vm';
const [,, tplPath, pvgisPath, casesPath, outPath] = process.argv;
const tpl = fs.readFileSync(tplPath, 'utf8');
const a = tpl.indexOf('/* ---- productible ---- */'), b = tpl.indexOf('/* ---- rendu ---- */');
let code = tpl.slice(a, b);
const G = JSON.parse(fs.readFileSync(pvgisPath, 'utf8'));
const cases = JSON.parse(fs.readFileSync(casesPath, 'utf8'));
const fake = () => ({ append(){}, set textContent(v){} });
const out = {};
for (const c of cases) {
  const ctx = { G, Math, Array, document: { createElement: fake, getElementById: fake }, $: fake };
  vm.createContext(ctx);
  vm.runInContext(code.replace('const I = {};', 'var I = {};') + '\nvar __R = null;', ctx);
  Object.assign(ctx.I, c.inputs);
  vm.runInContext('__R = compute();', ctx);
  out[c.name] = JSON.parse(JSON.stringify(ctx.__R));
}
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
console.log(Object.keys(out).length, 'cas');
