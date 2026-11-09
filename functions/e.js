// Compteur d'événements anonyme (sans cookie, sans adresse IP, sans identifiant).
// Le navigateur envoie {t, l, p, x, r} par navigator.sendBeacon ; on incrémente un
// compteur agrégé par jour dans D1 (binding DB, base lux-solaire-events).
// Listes blanches STRICTES (type, langue, page, cible, référent) : seules les valeurs que
// ev.js peut réellement envoyer depuis le site sont écrites ; tout le reste est ignoré sans
// écriture (réponse 204 dans tous les cas, rien à apprendre côté client). Le nombre de lignes
// distinctes possibles par jour est ainsi borné (sauf le référent de « land », réduit à un nom
// d'hôte). La limite de débit reste une règle Cloudflare (aucune IP stockée ici).
import { SLUGS, FILES } from "./_allow.js";   // généré par scripts/build.py (write_ev_allowlist)

const LANGS = new Set(["en", "fr", "de", "lb", "pt"]);
// ev.js envoie document.documentElement.lang : « pt-PT » sur les pages portugaises, ramené à « pt »
const LANG_ALIAS = { "pt-PT": "pt" };
const MAX_BODY = 1024;   // un événement réel fait moins de 200 octets
// Pages qui chargent /ev.js : tableau de bord, pages communales, « Pour les communes »
// (le simulateur ne charge pas ev.js : aucun événement n'en vient).
const HOME = /^\/(?:(?:fr|de|lb|pt)\/)?$/;
const COMMUNE = /^\/(?:municipality|fr\/commune|de\/gemeinde|lb\/gemeng|pt\/municipio)\/([a-z0-9]+(?:-[a-z0-9]+)*)\/$/;
const FORM = /^\/(?:for-municipalities|fr\/pour-les-communes|de\/fuer-gemeinden|lb\/fir-gemengen|pt\/para-os-municipios)\/$/;
const HOST = /^(?=.{1,60}$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$/;
const COPY = new Set(["rt-copy", "rt-copy-txt", "rt-copy-bib"]);

const pageOk = (p) => {
  if (HOME.test(p) || FORM.test(p)) return true;
  const m = COMMUNE.exec(p);
  return !!m && SLUGS.has(m[1]);
};
// cible autorisée selon le type (x), référent seulement pour « land » (r)
const TARGET = {
  dl: (x) => FILES.has(x),
  commune: (x) => x === "lux" || SLUGS.has(x),
  classes: (x) => x === "aides" || x === "detail",
  copy: (x) => COPY.has(x),
  contact: (x) => x === "hello@sitraka.lu",
  sim: (x) => x === "",
  page: (x) => SLUGS.has(x),
  land: (x) => x === "",
};
const done = () => new Response(null, { status: 204 });

// corps lu au plus MAX_BODY octets, même sans Content-Length (envoi fragmenté)
async function readCapped(request) {
  const len = Number(request.headers.get("Content-Length"));
  if (len > MAX_BODY) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done: end, value } = await reader.read();
    if (end) break;
    size += value.byteLength;
    if (size > MAX_BODY) { reader.cancel().catch(() => {}); return null; }
    chunks.push(value);
  }
  const buf = new Uint8Array(size);
  let o = 0;
  for (const c of chunks) { buf.set(c, o); o += c.byteLength; }
  return new TextDecoder().decode(buf);
}

export async function onRequestPost({ request, env }) {
  // même origine seulement quand le navigateur l'indique (en-tête absent : ancien navigateur, accepté ;
  // les valeurs d'un script sans en-tête restent bornées par les listes blanches ci-dessus)
  const site = request.headers.get("Sec-Fetch-Site");
  if (site && site !== "same-origin") return done();
  let b;
  try {
    const raw = await readCapped(request);
    if (raw === null) return done();
    b = JSON.parse(raw);
  } catch { return done(); }
  if (!b || typeof b !== "object" || !env.DB) return done();
  const type = String(b.t ?? ""), page = String(b.p ?? "");
  const rawLang = String(b.l ?? ""), lang = LANG_ALIAS[rawLang] ?? rawLang;
  const x = String(b.x ?? ""), r = String(b.r ?? "").toLowerCase();
  if (!Object.hasOwn(TARGET, type) || !LANGS.has(lang) || page.length > 80 || !pageOk(page) || !TARGET[type](x)) {
    return done();
  }
  if (type === "land" ? !HOST.test(r) : r !== "") return done();
  const day = new Date().toISOString().slice(0, 10);
  try {
    await env.DB.prepare(
      "INSERT INTO ev (day, type, lang, page, target, ref, n) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1) " +
      "ON CONFLICT (day, type, lang, page, target, ref) DO UPDATE SET n = n + 1"
    ).bind(day, type, lang, page, x, r).run();
  } catch (e) {
    // D1 indisponible ou quota atteint : l'événement est perdu, la page n'en sait rien
    console.error("ev: écriture D1 en échec", e && e.message);
  }
  return done();
}

export const onRequestGet = () => new Response(null, { status: 405 });
