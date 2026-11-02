// Compteur d'événements anonyme (sans cookie, sans adresse IP, sans identifiant).
// Le navigateur envoie {t, l, p, x, r} par navigator.sendBeacon ; on incrémente un
// compteur agrégé par jour dans D1 (binding DB, base lux-solaire-events).
// Listes blanches : type, langue et page (chemins réels du site) ; tout le reste
// est ignoré sans écriture (réponse 204 dans tous les cas, rien à apprendre côté client).
const TYPES = new Set(["dl", "commune", "classes", "copy", "contact", "sim", "land", "page"]);
const LANGS = new Set(["en", "fr", "de", "lb"]);
// Pages qui chargent /ev.js : tableau de bord, simulateur, pages communales, « Pour les communes »
const PAGES = [
  /^\/(?:(?:fr|de|lb)\/)?$/,
  /^\/(?:simulator|fr\/simulateur|de\/rechner|lb\/rechner)\/$/,
  /^\/(?:municipality|fr\/commune|de\/gemeinde|lb\/gemeng)\/[a-z0-9]+(?:-[a-z0-9]+)*\/$/,
  /^\/(?:for-municipalities|fr\/pour-les-communes|de\/fuer-gemeinden|lb\/fir-gemengen)\/$/,
];
const clean = (v, max) => String(v ?? "").slice(0, max).replace(/[^\p{L}\p{N} ._\/:-]/gu, "");
const done = () => new Response(null, { status: 204 });

export async function onRequestPost({ request, env }) {
  // même origine seulement quand le navigateur l'indique (en-tête absent : ancien navigateur, accepté)
  const site = request.headers.get("Sec-Fetch-Site");
  if (site && site !== "same-origin") return done();
  let b;
  try { b = JSON.parse(await request.text()); } catch { return done(); }
  if (!b || typeof b !== "object") return done();
  const type = clean(b.t, 12), lang = String(b.l ?? ""), page = String(b.p ?? "");
  if (!TYPES.has(type) || !LANGS.has(lang) || page.length > 80 || !PAGES.some((re) => re.test(page)) || !env.DB) {
    return done();
  }
  const day = new Date().toISOString().slice(0, 10);
  try {
    await env.DB.prepare(
      "INSERT INTO ev (day, type, lang, page, target, ref, n) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1) " +
      "ON CONFLICT (day, type, lang, page, target, ref) DO UPDATE SET n = n + 1"
    ).bind(day, type, lang, page, clean(b.x, 80), clean(b.r, 60)).run();
  } catch (e) {
    // D1 indisponible ou quota atteint : l'événement est perdu, la page n'en sait rien
    console.error("ev: écriture D1 en échec", e && e.message);
  }
  return done();
}

export const onRequestGet = () => new Response(null, { status: 405 });
