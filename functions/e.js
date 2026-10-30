// Compteur d'événements anonyme (sans cookie, sans adresse IP, sans identifiant).
// Le navigateur envoie {t, l, p, x} par navigator.sendBeacon ; on incrémente un
// compteur agrégé par jour dans D1 (binding DB, base lux-solaire-events).
const TYPES = new Set(["dl", "commune", "classes", "copy", "contact", "sim", "land", "page"]);
const clean = (v, max) => String(v ?? "").slice(0, max).replace(/[^\p{L}\p{N} ._\/:-]/gu, "");

export async function onRequestPost({ request, env }) {
  let b;
  try { b = JSON.parse(await request.text()); } catch { return new Response(null, { status: 204 }); }
  const type = clean(b.t, 12);
  if (!TYPES.has(type) || !env.DB) return new Response(null, { status: 204 });
  const day = new Date().toISOString().slice(0, 10);
  await env.DB.prepare(
    "INSERT INTO ev (day, type, lang, page, target, ref, n) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1) " +
    "ON CONFLICT (day, type, lang, page, target, ref) DO UPDATE SET n = n + 1"
  ).bind(day, type, clean(b.l, 3), clean(b.p, 80), clean(b.x, 80), clean(b.r, 60)).run();
  return new Response(null, { status: 204 });
}

export const onRequestGet = () => new Response(null, { status: 405 });
