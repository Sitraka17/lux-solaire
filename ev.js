/* Compteur d'événements anonyme de solaire.sitraka.lu : aucun cookie, aucun
   identifiant, aucune adresse IP enregistrée ; seulement des totaux par jour. */
(function () {
  var L = document.documentElement.lang || '', P = location.pathname;
  function send(t, x, r) {
    try {
      var body = JSON.stringify({ t: t, l: L, p: P, x: x || '', r: r || '' });
      if (navigator.sendBeacon) navigator.sendBeacon('/e', body);
      else fetch('/e', { method: 'POST', body: body, keepalive: true });
    } catch (e) {}
  }
  window.solEv = send;
  try {
    var ref = document.referrer ? new URL(document.referrer).hostname : '';
    if (ref && ref !== location.hostname) send('land', '', ref);
  } catch (e) {}
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a,button');
    if (!a) return;
    var h = a.getAttribute('href') || '';
    if (/\/data\/.+\.(csv|json)$/.test(h)) send('dl', h.split('/').pop());
    else if (h.indexOf('mailto:') === 0) send('contact', h.slice(7).split('?')[0]);
    else if (/\/(simulateur|simulator|rechner)\//.test(h)) send('sim');
    else if (/\/(commune|municipality|gemeinde|gemeng)\/[^/]+\/$/.test(h)) send('page', h.split('/').slice(-2)[0]);
    else if (a.id === 'rt-copy' || a.id === 'rt-copy-txt' || a.id === 'rt-copy-bib') send('copy', a.id);
  }, true);
})();
