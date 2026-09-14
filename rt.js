/* rt.js : boîte à outils du lecteur, identique sur les 7 dashboards de la série open data.
   Aucune chaîne de langue ici : les libellés viennent des attributs data-l-* de #rt,
   traduits par le dictionnaire HTML de chaque site. Aucune dépendance, aucun traceur. */
(function () {
  "use strict";
  var root = document.getElementById("rt");
  if (!root) return;
  var L = root.dataset;
  var $ = function (id) { return document.getElementById(id); };
  var link = document.querySelector('link[rel="canonical"]');
  var canon = link ? link.href : location.href.split("#")[0];
  var host = new URL(canon).host;
  var path = new URL(canon).pathname;
  var lang = (document.documentElement.lang || "fr").slice(0, 2);
  var version = L.rtVersion || "";
  var year = version.slice(0, 4) || String(new Date().getFullYear());
  var title = document.title;
  var ogt = document.querySelector('meta[property="og:title"]');
  var shareTitle = ogt ? ogt.content : title;
  var pad = function (n) { return (n < 10 ? "0" : "") + n; };
  var now = new Date();
  var accessed = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());

  function flash(btn, msg) {
    var live = $("rt-live");
    if (live) live.textContent = msg;
    if (btn.classList.contains("rt-a")) {
      btn.classList.add("rt-done");
      setTimeout(function () { btn.classList.remove("rt-done"); }, 1500);
      return;
    }
    if (!btn.hasAttribute("data-label")) btn.setAttribute("data-label", btn.textContent);
    btn.textContent = msg;
    setTimeout(function () { btn.textContent = btn.getAttribute("data-label"); }, 1500);
  }
  function copy(text, btn, msg) {
    var manual = function () { window.prompt(L.lManual, text); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(function () { flash(btn, msg); }, manual);
    } else { manual(); }
  }
  function currentSection() {
    var id = "";
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { return null; }
    var el = id ? document.getElementById(id) : null;
    return el && el.matches("section[id]") ? el : null;
  }
  function citeText() {
    return "Forler, S. (" + year + "). " + title + ". " + host + ", " + L.lVersion + " " + version +
      L.lSep + L.lAccessed + " " + accessed + ". " + canon;
  }
  function bibtex() {
    var esc = function (s) { return String(s).replace(/([{}%&$#_])/g, "\\$1"); };
    return "@misc{forler" + year + host.split(".")[0] + ",\n" +
      "  author       = {Forler, Sitraka},\n" +
      "  title        = {{" + esc(title) + "}},\n" +
      "  year         = {" + year + "},\n" +
      "  howpublished = {\\url{" + canon + "}},\n" +
      "  url          = {" + canon + "},\n" +
      "  urldate      = {" + accessed + "},\n" +
      "  note         = {" + esc(L.lVersion + " " + version + L.lSep + L.lAccessed + " " + accessed) + "},\n" +
      "  language     = {" + ({ fr: "french", en: "english", lb: "luxembourgish" }[lang] || lang) + "}\n}";
  }
  function update() {
    var sec = currentSection();
    var url = canon + (sec ? "#" + sec.id : "");
    var set = function (id, href) { var a = $(id); if (a) a.href = href; };
    set("rt-li", "https://www.linkedin.com/sharing/share-offsite/?url=" + encodeURIComponent(url));
    set("rt-x", "https://x.com/intent/tweet?text=" + encodeURIComponent(shareTitle) + "&url=" + encodeURIComponent(url));
    var where = sec ? (sec.getAttribute("data-rt-title") || "") + " (#" + sec.id + ")" : "";
    set("rt-err", "mailto:hello@sitraka.lu?subject=" +
      encodeURIComponent("[" + host + path + "] " + L.lErrSubject + (sec ? " #" + sec.id : "")) +
      "&body=" + encodeURIComponent(L.lErrPage + " " + url + "\n" + L.lErrSection + " " + where +
      "\n\n" + L.lErrWhat + "\n\n\n" + L.lErrSource + "\n"));
    if ($("rt-cite-txt")) $("rt-cite-txt").textContent = citeText();
    if ($("rt-cite-bib")) $("rt-cite-bib").textContent = bibtex();
  }
  var secs = document.querySelectorAll("section[id]");
  for (var i = 0; i < secs.length; i++) (function (sec) {
    var h = sec.querySelector("h2");
    if (!h || h.querySelector(".rt-a")) return;
    sec.setAttribute("data-rt-title", h.textContent.replace(/\s+/g, " ").trim());
    var b = document.createElement("button");
    b.type = "button"; b.className = "rt-a"; b.textContent = "#";
    b.setAttribute("aria-label", L.lAnchor);
    b.addEventListener("click", function () {
      history.replaceState(null, "", "#" + sec.id);
      update();
      copy(canon + "#" + sec.id, b, L.lCopied);
    });
    h.appendChild(b);
  })(secs[i]);
  var on = function (id, fn) { var el = $(id); if (el) el.addEventListener("click", fn); };
  on("rt-copy", function (e) { var s = currentSection(); copy(canon + (s ? "#" + s.id : ""), e.currentTarget, L.lCopied); });
  on("rt-copy-txt", function (e) { copy(citeText(), e.currentTarget, L.lCiteCopied); });
  on("rt-copy-bib", function (e) { copy(bibtex(), e.currentTarget, L.lCiteCopied); });
  var nat = $("rt-native");
  if (nat && navigator.share) {
    nat.hidden = false;
    nat.addEventListener("click", function () {
      var s = currentSection();
      navigator.share({ title: shareTitle, url: canon + (s ? "#" + s.id : "") }).catch(function () {});
    });
  }
  window.addEventListener("hashchange", update);
  update();
})();
