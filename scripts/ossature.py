"""Ossature commune à tous les types de pages (lot 1 du cahier des charges du 9/11/2026).

Une seule source pour :
- le bandeau de la série (`masthead`) et la liste des sites de la série ;
- le sélecteur de langue (`lang_nav`), inséré APRÈS traduction ;
- le bloc commun du colophon (liens « Pour les communes », contact, auteur, tableau A de la série) ;
- la feuille de style de l'ossature (`CSS`).

Les textes sont écrits en FRANÇAIS, comme les gabarits : `expand()` les insère dans
template.html et template_simulateur.html AVANT traduction, et leurs traductions EN, DE, LB et
PT sont des clés des dictionnaires `scripts/i18n_*.json` (parité contrôlée par
`build.check_dicts`). Les pages communales (communes.py) reprennent le bandeau et le colophon
commun des tableaux de bord déjà rendus, donc traduits.

Marque blanche : pour une autre série ou un autre site, seules les données changent
(`SERIES`, `CURRENT`, les libellés), pas la structure.
"""

# Les huit sites de la série open-data (ordre de la série). Sujet = résumé du titre de chaque site,
# en français ; ses traductions sont des clés des dictionnaires (title des liens et tableau A).
SERIES = (
    ("lux-solaire", "https://solaire.sitraka.lu", "Photovoltaïque : capacité raccordée par commune"),
    ("lux-entreprendre", "https://entreprendre.sitraka.lu", "Créations, survie et faillites d'entreprises"),
    ("lux-conseil", "https://luxconseil.sitraka.lu", "Fonder une ESN : étude de marché chiffrée"),
    ("index-lu", "https://index.sitraka.lu", "Prochaine tranche indiciaire des salaires"),
    ("budget-lu", "https://budget.sitraka.lu", "Dette publique et finances de l'État"),
    ("lux-canicule", "https://canicule.sitraka.lu", "La chaleur, commune par commune"),
    ("lux-santé", "https://sante.sitraka.lu", "Carte sanitaire : lits, personnel, attentes"),
    ("lux-india", "https://india.sitraka.lu", "L'Inde et le Luxembourg en chiffres"),
)
CURRENT = "lux-solaire"

# Sélecteur de langue : noms natifs (texte masqué, annoncé par les lecteurs d'écran), étiquette du
# groupe dans la langue de la PAGE, codes affichés. « LB » = code de langue ISO 639-1, identique
# au hreflang publié (décision D2 du cahier des charges ; « LU » est le code du pays).
NATIVE = {"en": "English", "fr": "Français", "de": "Deutsch", "lb": "Lëtzebuergesch", "pt": "Português"}
ARIA_LANG = {"fr": "Langue de la page", "en": "Page language", "de": "Sprache der Seite",
             "lb": "Sprooch vun der Säit", "pt": "Idioma da página"}
CODE = {"en": "EN", "fr": "FR", "de": "DE", "lb": "LB", "pt": "PT"}
LANG_ATTR = {"pt": "pt-PT"}     # attribut lang des liens (portugais du Portugal, comme <html>)
# Fil d'Ariane : étiquette du <nav> pour les pages générées en Python (communes.py) ; le
# simulateur porte la même étiquette en français dans son gabarit (clé des dictionnaires).
CRUMBS_ARIA = {"fr": "Fil d'Ariane", "en": "Breadcrumb", "de": "Brotkrümelnavigation",
               "lb": "Navigatiounswee", "pt": "Trilho de navegação"}


def lang_nav(paths, lang, flags, pt_fallback=None):
    """<ul class="langs"> : une entrée par (code, chemin) de `paths`, dans l'ordre EN, FR, DE, LB, PT.
    Drapeaux = repère secondaire (aria-hidden), toujours suivis du code ; nom natif en texte masqué.
    `pt_fallback` : chemin portugais à proposer quand la page n'existe pas en portugais (404)."""
    items = list(paths)
    note = {}
    if "pt" not in dict(items) and pt_fallback:
        items.append(("pt", pt_fallback))
        note["pt"] = True
    out = []
    for code, path in items:
        cur = ' aria-current="page"' if code == lang else ""
        if note.get(code):
            extra = (f' title="{NATIVE[code]} : simulador"', '<span class="lg-note"> simulador</span>')
        else:
            extra = ("", f'<span class="vh"> {NATIVE[code]}</span>')
        out.append(f'<li><a href="{path}" lang="{LANG_ATTR.get(code, code)}" hreflang="{code}"{cur}{extra[0]}>'
                   f'{flags[code]}{CODE[code]}{extra[1]}</a></li>')
    return f'<ul class="langs" aria-label="{ARIA_LANG[lang]}">' + "".join(out) + "</ul>"


def crumbs(items, lang):
    """Fil d'Ariane des pages générées : [(libellé HTML, chemin), …, (libellé HTML, None)] ; le dernier
    élément est la page courante (aria-current)."""
    li = "".join(f'<li><a href="{p}">{t}</a></li>' if p else f'<li aria-current="page">{t}</li>' for t, p in items)
    return f'<nav class="crumbs" aria-label="{CRUMBS_ARIA[lang]}"><ol>{li}</ol></nav>'


def _series_items():
    cur, ext = ' aria-current="page"', ' target="_blank" rel="noopener"'
    return "".join(
        f'<li><a{cur if name == CURRENT else ""} href="{url}"{"" if name == CURRENT else ext} title="{subject}">{name}</a></li>'
        for name, url, subject in SERIES)


def _series_rows():
    rows = []
    for i, (name, url, subject) in enumerate(SERIES, 1):
        cur = name == CURRENT
        link = (f'<a href="{url}" aria-current="page">{name}</a>' if cur
                else f'<a href="{url}" target="_blank" rel="noopener">{name}</a>')
        tr = '<tr class="cur">' if cur else "<tr>"
        rows.append(f'{tr}<td class="n">{i}</td><th scope="row">{link}</th>'
                    f'<td>{subject}</td><td class="url">{url.split("//", 1)[1]}</td></tr>')
    return "".join(rows)


# Bandeau de la série : libellé et liste en bureau ; liste repliée dans un <details> sur mobile
# (une seule des deux copies est affichée ; display:none la retire aussi des lecteurs d'écran).
MASTHEAD = (
    '<!--MASTHEAD-->\n<div class="masthead">\n  <div class="mh-row">\n'
    '    <p class="mh-label" id="mh-l">Série open-data · Luxembourg</p>\n'
    '    <details class="mh-series">\n'
    f'      <summary aria-label="Série open-data ({len(SERIES)})"><span class="mh-long" aria-hidden="true">Série open-data</span>'
    f'<span class="mh-short" aria-hidden="true">Série</span> <span class="count" aria-hidden="true">({len(SERIES)})</span></summary>\n'
    f'      <nav aria-label="Série open-data · Luxembourg"><ul class="series">{_series_items()}</ul></nav>\n'
    '    </details>\n    <!--LANGTOGGLE-->\n  </div>\n'
    f'  <nav class="mh-desk" aria-labelledby="mh-l"><ul class="series">{_series_items()}</ul></nav>\n'
    '</div>\n<!--/MASTHEAD-->')

# Bloc commun du colophon (colonne « auteur » et tableau A), identique sur tous les types de pages.
# La colonne « données et licences » est propre à chaque type de page (gabarit ou communes.py).
COLOPHON_COMMON = (
    '<!--COLOPHON_COMMON-->\n<div class="co-b">\n'
    '  <p><a href="__FORPATH__">Pour les communes</a> : une page par commune, avec ses données.</p>\n'
    '  <p>Contact : <a href="https://sitraka.lu/fr/contact/?from=solaire">écrire à l\'auteur</a></p>\n'
    '  <p>Analyse et visualisation : <a href="https://sitraka.lu" target="_blank" rel="noopener">Sitraka Forler</a> · '
    'pandas + SVG natif, sans bibliothèque · <a href="https://github.com/Sitraka17/lux-solaire" target="_blank" '
    'rel="noopener">code source</a> · <a href="https://www.linkedin.com/in/sitraka-matthieu-forler" target="_blank" '
    'rel="noopener">LinkedIn</a>.</p>\n'
    '  <p>Agenda, newsletter et autres travaux : <a href="https://sitraka.lu" target="_blank" rel="noopener">sitraka.lu</a></p>\n'
    '  <p>Du même auteur, pour la pause : <a href="https://ratrace.sitraka.lu/">Rat Race</a>, le jeu du frontalier '
    '(65 villes, un trajet du jour).</p>\n'
    '</div>\n<div class="co-series">\n'
    '  <p>Ce site fait partie d\'une série de réutilisations des données publiques luxembourgeoises.</p>\n'
    '  <div class="tblscroll" role="region" tabindex="0" aria-labelledby="series-cap">'
    '<table class="series-t"><caption id="series-cap"><b>Tableau A.</b> La série open-data · Sitraka Forler</caption>'
    '<thead><tr><th scope="col"><span class="vh">N°</span></th><th scope="col">Site</th>'
    '<th scope="col">Sujet</th><th scope="col">Adresse</th></tr></thead>'
    f'<tbody>{_series_rows()}</tbody></table></div>\n'
    '</div>\n<!--/COLOPHON_COMMON-->')

CSS = r"""
  /* ==== OSSATURE (lot 1, scripts/ossature.py) : base, bandeau, en-tête, tableaux, colophon ==== */
  body{margin:0;background:var(--paper)}
  .wrap{padding:16px 24px 72px}
  @media(max-width:480px){.wrap{padding:12px 16px 56px}}
  html{scroll-padding-top:56px}
  :focus-visible{outline:2px solid var(--amber-text);outline-offset:2px}
  .vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
  /* bandeau de la série */
  .masthead{border-top:3px solid var(--amber);border-bottom:1px solid var(--line);padding:5px 0 6px;margin:0 0 24px;font-size:13px}
  .wrap:has(.crumbs) .masthead{margin-bottom:4px}
  .mh-row{display:flex;align-items:center;justify-content:space-between;gap:4px 16px}
  .mh-label{margin:0;font:600 14.5px/26px var(--body);font-variant-caps:all-small-caps;letter-spacing:.07em;color:var(--amber-text)}
  .series{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;align-items:center}
  .series li{display:inline-flex;align-items:center}
  .series li:not(:last-child)::after{content:"·"/"";color:var(--ink-3);padding:0 7px;font-weight:700}
  .series a{display:inline-flex;align-items:center;min-height:26px;color:var(--ink-2);text-decoration:none;font-size:13.5px}
  .series a:hover{color:var(--amber-text);text-decoration:underline;text-underline-offset:3px}
  .series a[aria-current]{color:var(--ink);font-weight:650;text-decoration:underline;text-decoration-color:var(--amber);text-decoration-thickness:2px;text-underline-offset:4px}
  .mh-desk{margin-top:2px}
  .langs{display:flex;align-items:center;gap:6px;margin:0;padding:0;list-style:none;font:600 11.5px var(--mono);letter-spacing:.04em}
  .langs li{display:flex}
  .langs a{display:inline-flex;align-items:center;gap:5px;min-height:28px;min-width:24px;padding:0 4px;color:var(--ink-3);text-decoration:none}
  .langs a:hover{color:var(--amber-text);text-decoration:underline;text-underline-offset:5px}
  .langs a[aria-current]{color:var(--ink);text-decoration:underline;text-decoration-color:var(--amber);text-decoration-thickness:2px;text-underline-offset:5px}
  .langs svg{display:block;width:16px;height:11px;flex:none;box-shadow:0 0 0 .5px rgba(29,39,52,.35)}
  .langs .lg-note{font:500 11px var(--body);letter-spacing:0;color:var(--ink-3)}
  .mh-series{display:none}
  .mh-series summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:0;font:600 13.5px var(--body);font-variant-caps:all-small-caps;letter-spacing:.05em;color:var(--amber-text);white-space:nowrap}
  .mh-series summary::-webkit-details-marker{display:none}
  .mh-series summary::before{content:"▸"/"";font-variant-caps:normal;width:10px}
  .mh-series[open] summary::before{content:"▾"/""}
  .mh-series .count{font-variant-caps:normal;font-variant-numeric:tabular-nums;color:var(--ink-3);font-weight:500;letter-spacing:0}
  .mh-short{display:none}
  @media(max-width:767px){
    .masthead{margin-bottom:16px;padding:2px 0 4px}
    .wrap:has(.crumbs) .masthead{margin-bottom:4px}
    .mh-label,.mh-desk{display:none}
    .mh-row{display:grid;grid-template-columns:1fr auto;align-items:start;column-gap:8px}
    .mh-series{display:block;grid-column:1/-1;grid-row:1}
    .mh-row>.langs{grid-column:2;grid-row:1}
    .mh-series .series{padding:2px 0 6px 16px}
    .mh-series .series a{min-height:32px}
    .langs a{min-height:32px;padding:0 3px}
    .langs .lg-note{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
  }
  @media(max-width:539px){.langs svg{display:none}}
  @media(max-width:459px){.mh-long{display:none}.mh-short{display:inline}}
  /* en-tête de page : fil d'Ariane, surtitre, H1 */
  .crumbs ol{list-style:none;margin:0 0 4px;padding:0;display:flex;flex-wrap:wrap;font:11.5px/1.5 var(--mono);color:var(--ink-3)}
  .crumbs li{display:flex;align-items:center}
  .crumbs li:not(:last-child)::after{content:"›"/"";margin:0 8px}
  .crumbs a{color:var(--amber-text);text-decoration:none;display:inline-block;padding:4px 0}
  .crumbs a:hover{text-decoration:underline}
  .crumbs li[aria-current]{padding:4px 0}
  /* téléphone : fil d'Ariane sur une ligne ; le premier libellé, long, est tronqué à l'écran (texte complet dans le DOM) */
  @media(max-width:767px){
    .crumbs ol{flex-wrap:nowrap}
    .crumbs li{flex:none;min-width:0}
    .crumbs li:first-child{flex:0 1 auto}
    .crumbs li:first-child a{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  }
  header>.eyebrow{margin:0}
  h1{max-width:20ch;margin-top:10px}
  /* tableaux : conteneur défilant (indices d'ombre seulement si le tableau dépasse), légendes */
  .tblscroll{--sc-bg:var(--card);overflow-x:auto;-webkit-overflow-scrolling:touch;scroll-padding-left:120px;
    background:linear-gradient(to right,var(--sc-bg) 30%,transparent) left/24px 100% no-repeat local,
               linear-gradient(to left,var(--sc-bg) 30%,transparent) right/24px 100% no-repeat local,
               linear-gradient(to right,rgba(29,39,52,.12),transparent) left/10px 100% no-repeat scroll,
               linear-gradient(to left,rgba(29,39,52,.12),transparent) right/10px 100% no-repeat scroll}
  .tblscroll:focus-visible{outline:2px solid var(--amber-text);outline-offset:2px}
  .tblwrap{scroll-padding-top:44px}
  #tbl{min-width:900px}
  table.bigtab th,table.bigtab td{white-space:normal}
  table.bigtab td:first-child,table.bigtab td:last-child{white-space:nowrap}
  table.bigtab small{white-space:normal;overflow-wrap:anywhere}
  td.num,th.num{white-space:nowrap;text-align:right;font-variant-numeric:tabular-nums}
  caption{caption-side:top;text-align:left;font-size:13px;color:var(--ink-2);padding:0 0 8px}
  caption b,figcaption b{font:650 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--ink);margin-right:6px}
  figcaption{font-size:13px;color:var(--ink-2);margin-top:8px}
  .src{font:11.5px/1.5 var(--mono);color:var(--ink-3);margin-top:4px}
  table.booktabs{border-collapse:collapse;border-top:1.5px solid var(--ink);border-bottom:1.5px solid var(--ink)}
  table.booktabs thead th{border-bottom:1px solid var(--ink)}
  table.booktabs td,table.booktabs th{border-left:0;border-right:0}
  /* cibles d'au moins 24 px (WCAG 2.5.8) */
  :where(summary){padding-block:5px}
  .pn a{display:inline-flex;align-items:center;min-height:32px}
  /* section Méthode (sortie du pied de page) */
  .method{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);font-size:14px;color:var(--ink-2)}
  .method h2{margin:0 0 10px}
  .method p,.method ol{max-width:75ch;margin:0 0 10px}
  .method a{color:var(--amber-text)}
  /* colophon commun */
  .colophon{margin-top:48px;padding-top:14px;border-top:1px solid var(--ink);display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:8px 40px;align-items:start;font-size:13px;color:var(--ink-2)}
  .colophon h2{grid-column:1/-1;margin:0 0 4px;font:650 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
  .colophon p{margin:0 0 8px;max-width:75ch}
  .colophon a{color:var(--amber-text)}
  .colophon .co-series{grid-column:1/-1;margin-top:10px}
  .colophon .tblscroll{--sc-bg:var(--paper)}
  table.series-t{width:100%;border-collapse:collapse;margin:6px 0 0;font-size:13px;border-top:1.5px solid var(--ink);border-bottom:1.5px solid var(--ink)}
  table.series-t th,table.series-t td{padding:5px 12px 5px 0;border-bottom:1px solid var(--line);text-align:left;vertical-align:baseline;white-space:normal}
  table.series-t thead th{font:600 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3);background:none;position:static;border-bottom:1px solid var(--ink);cursor:default}
  table.series-t td.n{font-family:var(--mono);font-size:12px;color:var(--ink-3);width:2.5em;text-align:right;padding-right:14px}
  table.series-t th[scope=row]{font-weight:650;white-space:nowrap}
  table.series-t th[scope=row] a{display:inline-block;padding:3px 0;color:var(--ink);text-decoration-color:var(--line);text-underline-offset:3px}
  table.series-t th[scope=row] a:hover{color:var(--amber-text);text-decoration-color:currentColor}
  table.series-t td.url{font-family:var(--mono);font-size:12px;color:var(--ink-3);white-space:nowrap}
  table.series-t tr.cur{background:var(--amber-soft)}
  table.series-t tr.cur td.n{box-shadow:inset 3px 0 0 var(--amber)}
  table.series-t tbody tr:hover,table.series-t thead th:hover{background:none}
  table.series-t tbody tr.cur:hover{background:var(--amber-soft)}
  table.series-t tbody td{font-family:var(--body);font-size:13px;color:var(--ink-2)}
  table.series-t tbody td.n,table.series-t tbody td.url{font-family:var(--mono);font-size:12px;color:var(--ink-3)}
  @media(max-width:640px){
    .colophon{grid-template-columns:minmax(0,1fr)}
    table.series-t thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
    table.series-t tr{display:grid;grid-template-columns:34px minmax(0,1fr);border-bottom:1px solid var(--line)}
    table.series-t th,table.series-t td{display:block;border:0;padding:0 10px 0 0}
    table.series-t td.n{grid-column:1;grid-row:1/4;width:auto;padding:8px 0 0 10px;text-align:left}
    table.series-t th[scope=row],table.series-t td:not(.n){grid-column:2}
    table.series-t th[scope=row]{padding-top:4px;white-space:normal}
    table.series-t td.url{padding-bottom:7px;font-size:11.5px}
    table.series-t tr.cur td.n{box-shadow:none}
    table.series-t tr.cur{box-shadow:inset 3px 0 0 var(--amber)}
  }
  /* mode réunion (grand écran projeté) et impression */
  @media(min-width:1600px){html{font-size:clamp(16px,.6vw + 8px,20px)}}
  @media print{.masthead,.rt,.rt-a,.cta,.contact-cta,.skip{display:none}body,html{background:#fff}a{color:inherit}.tblscroll{background:none}}
"""


def expand(tpl):
    """Insère l'ossature (en français) dans un gabarit, AVANT traduction : feuille de style à la
    place de /*@OSSATURE_CSS*/, bandeau à la place de <!--@MASTHEAD-->, bloc commun du colophon
    à la place de <!--@COLOPHON_COMMON-->. Chaque marqueur doit être présent une fois."""
    for marker, frag in (("/*@OSSATURE_CSS*/", CSS), ("<!--@MASTHEAD-->", MASTHEAD),
                         ("<!--@COLOPHON_COMMON-->", COLOPHON_COMMON)):
        if tpl.count(marker) != 1:
            raise SystemExit(f"ossature : marqueur {marker} absent ou répété dans le gabarit")
        tpl = tpl.replace(marker, frag)
    return tpl
