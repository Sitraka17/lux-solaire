# CONTEXT : lux-solaire (notes internes, jamais servies : hors de la liste blanche de scripts/make_dist.py)

## Lot 2 du cahier des charges UX/UI : tableau de bord, pages communales, « Pour les communes » (9/11/2026)

- **Tableau de bord** : Figures 1 à 7 (`<figure class="card">`, `<figcaption><b>Figure n.</b> constat. <span class="u">ancien
  sous-titre mono</span>`) et Tableaux 1 à 6 (`<caption>`, y compris les tableaux « Données du graphique » et la
  liste des grandes installations, numéro passé par `grandes.dashboard_section(caption=)`). Sous chaque figure :
  `<p class="src">` (source datée, traitement) + lien « Données de la figure n (CSV, x ko) », marqueur
  `<!--DL:<slug>:<F|T>:<n>-->` remplacé par `build.dl_links` (taille lue sur data/csv, libellés `DL_LABEL`).
  « Votre commune » dans l'en-tête (`form.pick`, options `<!--PRE_PICK-->`, navigation à l'envoi, sans JS : #communes).
  KPI sur 2 colonnes sous 768 px. Section « rythme » : figure pleine largeur puis les deux encadrés côte à côte.
  Méthode : 1er paragraphe visible, la suite dans `<details>`. Préfixes traduits par les clés `<b>Figure ` et
  `<b>Tableau ` des dictionnaires.
- **Pages communales** : Figure 1 (tailles), Tableau 1 (tranches Klimabonus Gemengen, aide en 2e colonne),
  Tableaux 2 et 3 (comparaisons : N°, Commune collante, W/hab., …, Canton en dernier et masqué sous 520 px dans
  le tableau du canton), puis Tableau 4 (grandes installations, présent sur 17 communes seulement : section
  DÉPLACÉE après la comparaison pour que les numéros 1 à 3 soient identiques sur les 500 pages). Lien
  « Est-ce rentable sur votre toit à X ? » sous les KPI. Note de méthode des grandes installations repliée
  (`grandes.M_SUM`). Liens de note en `--amber-text`. Impression A4 (`.commune-page`, 2 pages). Variable
  `--accent` (marque blanche) pour filets et soulignements. Textes : `L2`, `FIG_LABEL`, `TAB_LABEL` (communes.py).
- **« Pour les communes »** = page d'offre : 1. Démonstration (Figure 1 = KPI réels de Differdange, même fragment
  que sa page ; Figure 2 = simulateur préréglé sur le canton), 2. Tableau 1 des composantes (page communale,
  simulateur aux couleurs de la commune, bilan énergétique du patrimoine communal), 3. Méthode et confiance,
  4. Contact (bouton `?from=solaire-communes`, en tête et ici seulement), 5. index en grille. Textes `FOR2`.
  `check_offer` fait échouer le build sur « € », prix, tarif, devis, audit, « conseiller en énergie » (5 langues).
- Tests : `tests/test_lot2.py`. Mesures navigateur : scratchpad de la session, `pw/lot2/accept.mjs`.

## Ossature commune, lot 1 du cahier des charges UX/UI (9/11/2026)

Une seule source pour le haut et le bas de TOUS les types de pages (tableau de bord, simulateur,
pages communales, « Pour les communes ») : `scripts/ossature.py`.
- **Insertion** : `build.load_templates()` remplace dans les deux gabarits `/*@OSSATURE_CSS*/`,
  `<!--@MASTHEAD-->` et `<!--@COLOPHON_COMMON-->` par les fragments FRANÇAIS d'ossature.py, AVANT
  traduction ; leurs traductions sont des clés de `i18n_{en,de,lb,pt}.json` (parité et clés mortes
  contrôlées par `check_dicts`, qui lit les gabarits ÉTENDUS ; les tests aussi). communes.py reprend
  le bandeau (`<!--MASTHEAD-->…<!--/MASTHEAD-->`), le titre du colophon et le bloc commun
  (`<!--COLOPHON_COMMON-->…`) des tableaux de bord déjà rendus, donc traduits.
- **Bandeau** (`.masthead`, prototype A) : filet ambre de 3 px, libellé « Série open-data ·
  Luxembourg », 8 sites en une ligne (bureau) ou repliés dans un `<details>` (« ▸ Série (8) », sous
  768 px), sujet de chaque site en `title` (SERIES, à confirmer par Sitraka). Sélecteur
  `ossature.lang_nav` : `<ul class="langs">`, EN · FR · DE · LB · PT (« LB » = code de langue,
  plus « LU »), `lang`/`hreflang`, `aria-current`, nom natif en texte masqué, drapeaux
  `aria-hidden` masqués sous 540 px. Inséré APRÈS traduction ; `check_output` l'ignore.
- **En-tête** : fil d'Ariane `<nav class="crumbs"><ol>` (simulateur, communes, « Pour les
  communes » ; tronqué sur une ligne sous 768 px), surtitre (« Tableau de bord · données Leneda »
  sur le tableau de bord), H1 à 20ch partout. « Pour les communes » : 1er paragraphe en chapô, puis
  l'appel à l'action. `jsonld_sim` lit le nouveau fil d'Ariane.
- **Bas de page** : la méthode sort du pied de page sans changement de texte (`<section id="methode"
  class="method">` en fin de `<main>`, ancre conservée) ; `footer.colophon` commun : colonne
  « données et licences » propre à la page, colonne « auteur » commune (Pour les communes, contact,
  auteur, sitraka.lu, Rat Race), « Tableau A. » de la série. La ligne « Analyse : Sitraka Forler ·
  sitraka.lu · code source » des pages communales est remplacée par la ligne auteur commune (même
  information) ; « Ce tableau de bord fait partie » devient « Ce site fait partie ».
- **Débordement mobile corrigé** : `min-width:900px` réservé à `#tbl` (il fuyait sur `bigtab` et
  `cmp`), `bigtab` dans un conteneur `.tblscroll` (indices d'ombre si le tableau dépasse),
  `body{margin:0}`, gouttière de 16 px sous 480 px. Avant : 1 131 px de large à 375 px sur /fr/,
  955 px sur les pages communales, 1 302 px à 1 280 px sur /de/.
- **Divers** : mois abrégés `MONTHS_FR_ABBR` (« nov. », plus « nove. ») ; boutons `.rt` rayon 2 px ;
  focus ambre visible et `scroll-padding` ; mode réunion (≥ 1 600 px) ; impression sans bandeau ;
  classes de légende `caption`, `figcaption`, `.src`, `table.booktabs` prêtes pour les lots 2 et 3 ;
  404 à filet supérieur, codes LB/PT.
- **Contrôles** : `tests/test_ossature.py` (statique) ; mesures navigateur (débordement à 320, 360,
  375, 414, 767, 768, 1 280 et 1 920 px, cibles ≥ 24 px, une ligne sur mobile, clavier sans JS) :
  script playwright hors dépôt (scratchpad de la session du 9/11, `pw/lot1/accept.mjs`).
- **Non fait dans ce lot** : typographie française fine (L1.8 : espaces insécables des milliers,
  avant « : » et dans les guillemets) ; curseurs et cases du simulateur de 16 px (lot 3, L3.8).

## i18n : le portugais sur TOUT le site (9/11/2026)

Extension du simulateur PT (8/11, section suivante) au tableau de bord `/pt/`, aux 100 pages
communales `/pt/municipio/<slug>/` et à « Pour les communes » `/pt/para-os-municipios/` : 103 pages
PT. Ce bloc REMPLACE les points « simulateur seulement » de la section suivante (liens vers `/fr/`
« (em francês) », `check_dict_pt`, `RT_TITLES_PT`, pas de `data.pt.json`, `pt` absent de `/e`).

- **Dictionnaires** : `i18n_pt.json` + `i18n_pt_js.json` (tableau de bord), `i18n_sim_pt*.json`
  (simulateur, clés du tableau de bord retirées). `check_dicts` contrôle désormais la parité FICHIER
  PAR FICHIER pour LB, DE et PT contre EN (`I18N_FILES`, `_dict_parts`) ; `check_dict_pt` supprimé.
  Clés ajoutées le 9/11 aux quatre dictionnaires du tableau de bord : badges « Source <b>Leneda</b> »
  et « Licence <b>CC0</b> » (restés en français en DE/LB/PT jusque-là).
- **Pages communales** : `S["pt"]`, `FOR["pt"]` (communes.py), `S["pt"]` et `TYPE_NAMES["pt"]`
  (grandes.py, noms des filières = i18n_pt_js.json). `HTML_LANG = {"pt": "pt-PT"}` vit dans
  communes.py (importé par build.py). Trimestre en prose : « T1 2025 » (`_q_pt`), rang « 86.º ».
- **Données** : `data/data.pt.json` publié, titres PT dans le manifeste, `og.pt.png`.
- **Sélecteur** : substitué APRÈS traduction (avant, la clé `href="/fr/simulateur/"` réécrivait le
  lien FR du sélecteur des simulateurs EN/DE/LB/PT vers la page elle-même : bogue corrigé le 9/11).
  `check_output` ignore le sélecteur.
- **SEO** : hreflang `pt` dans `template.html`, x-default inchangé ; sitemap via `LANG_PATHS` et
  les groupes communaux.
- **Compteur `/e`** : `functions/e.js` accepte `pt` (et `pt-PT`, ce qu'envoie `ev.js`, ramené à `pt`)
  et les chemins `/pt/`, `/pt/municipio/…`, `/pt/para-os-municipios/`.
- **Barèmes** : `check_page` reconnaît « dos custos », « e », « máx. », « cobertura de parque de
  estacionamento », « tabela de AAAA ».
- **404** : lien PT ajouté. **Contact** : `sitraka.lu/fr/contact/` « (em francês) », seul lien
  interne-à-la-marque encore signalé en français.
- **Tests** : `tests/test_portugais_site.py` (103 pages, hreflang réciproques, sélecteur sur chaque
  type de page, sitemap, liens PT vers PT, français résiduel via `tests/francais_residuel.py`,
  métadonnées, manifeste, `/e` dans node).

## i18n : le portugais, SIMULATEUR d'abord (/pt/simulador/, 8/11/2026, historique)

Cinquième langue, limitée au simulateur (ni tableau de bord, ni pages communales, ni « Pour les
communes »). Public : la communauté portugaise du Luxembourg (Differdange, Esch). Portugais
européen, registre clair, 3e personne de politesse (« o seu telhado »). Commit local, pas encore
déployé ni poussé.

- **Dictionnaires** : `scripts/i18n_sim_pt.json` (HTML) + `scripts/i18n_sim_pt_js.json` (objet `L`),
  clés = texte FRANÇAIS du gabarit comme pour EN/DE/LB. Contrôle `check_dict_pt` (build.py, appelé
  juste après `check_dicts`) : PT doit couvrir EXACTEMENT les clés EN du simulateur
  (`i18n_sim_en.json` + `i18n_sim_js.json`) PLUS les clés EN du tableau de bord présentes dans
  `template_simulateur.html` (barre de série, boîte à outils `#rt`, lien d'évitement, appel à
  l'action) ; aucune clé morte. Build en échec sinon. Clé ajoutée le 8/11 aux QUATRE dictionnaires
  du simulateur : `">Option A · Klimabonus<"` (titre de l'option A et légende de la figure 2, restés
  en dur parce qu'identiques en FR/EN/DE ; valeur identique en EN/DE/LB, « Opção A » en PT).
- **Chemin** : `/pt/simulador/` (ajouté à `SIM_PATHS` ; `SIM_LANGS` = langues du simulateur,
  `LANG_PATHS` inchangé). Données : blob `data_pt = translate_data(data, _tr_str_pt)` en mémoire
  seulement, AUCUN `data.pt.json` publié.
- **Nombres** : virgule décimale, milliers séparés par une espace insécable FINE U+202F
  (`_thousands(…, "pt")`). La locale JS `'fr-FR'` est gardée telle quelle dans la page PT :
  `toLocaleString('fr-FR')` produit exactement ce format (U+202F), donc pré-rendu Python et recalcul
  JS sont identiques (test `test_milliers_comme_tolocalestring`). Les milliers écrits à la main dans
  les valeurs PT utilisent aussi U+202F. « 30 % » avec espace, comme le JS (`' %'`).
- **Dates** : `_tr_str_pt` (mois, abréviations, « 1er » → « 1 ») puis « 2 de novembro de 2026 »
  (`_PT_DATE_RE`). Trimestres « 2025 T1 » inchangés (T = trimestre en portugais).
- **SEO** : hreflang `pt` codé en dur dans `template_simulateur.html` (donc sur les 5 pages du
  simulateur), x-default inchangé (EN `/simulator/`) ; sitemap généré via `SIM_PATHS` ; og:locale
  `pt_PT`, les `og:locale:alternate` des pages simulateur suivent désormais `SIM_PATHS` (ceux du
  tableau de bord restent sur `LANG_PATHS`) ; image `og.sim.pt.png` (make_og_sim) ; FAQ JSON-LD
  relue dans la page traduite (portugais). Sélecteur de langue du simulateur : EN · FR · DE · LU · PT,
  drapeau `F_PT` simplifié (vert, rouge, disque jaune).
- **Liens sans version portugaise** : le fil d'Ariane et le lien « tableau de bord » pointent vers
  `/fr/` avec la mention « (em francês) » ; `__FORPATH__` / `__CPATH__` retombent sur les chemins FR
  (`CPATH.get(lang, CPATH["fr"])`), texte « a página para os municípios (em francês) » ; appel à
  l'action vers `sitraka.lu/fr/contact/?from=solaire` (pas de page de contact en portugais).
  Sources (guichet.lu, PVGIS, Klima-Agence) : liens FR gardés, titres de documents traduits en
  description portugaise (« página em francês » quand utile) ; licence CC BY : `deed.pt`.
- **Boîte à outils** : `rt_downloads(…, "pt")` prend les titres de `RT_TITLES_PT` (build.py, hors
  manifeste : `data/manifest.json` reste en en/fr/de/lb) et le JSON français (`data.json`, libellé
  « rótulos em francês »). `rt.js` NON modifié (kit commun à la série) : la ligne `language` du
  BibTeX vaut donc `pt`.
- **Termes** : non traduits : Klimabonus, Klima-Agence, Leneda, Diff Primes (absent de la page
  publique), HEMS, PVGIS, guichet.lu, noms de cantons (« No cantão de Luxembourg » : nom officiel
  du canton, comme en DE). Traduits : pompe à chaleur → bomba de calor ; panneaux → painéis
  fotovoltaicos ; batterie → bateria ; tarif d'injection → tarifa de injeção (garantida) ; ballon
  tampon → depósito de inércia ; onduleur → inversor ; devis → orçamento ; mazout → gasóleo de
  aquecimento ; plancher chauffant → piso radiante ; commune → município ; canton → cantão ;
  relevé → levantamento ; non actualisé → não atualizado ; TRI → TIR ; kWc → kWp.
- **Barèmes** : `baremes.check_page` reconnaît les tournures PT (« a partir de », « até »,
  « para uma encomenda », « L por kW ») ; la page PT est contrôlée comme les autres (413 pages).
- **Dist et compteur** : `pt` dans `PUBLIC_DIRS`, `og.sim.pt.png` dans `PUBLIC_FILES`
  (`scripts/make_dist.py`). Compteur `/e` : rien à changer (le simulateur ne charge pas `ev.js`,
  `functions/e.js` ne liste aucun chemin de simulateur ; `pt` absent de `LANGS` à dessein).
- **Tests** : `tests/test_portugais.py` (parité et détection d'une clé manquante, formats, dates,
  métadonnées, hreflang sur les 5 pages + sitemap, absence de mots français dans le texte visible,
  les attributs, la FAQ JSON-LD et les littéraux JS, contrôle des barèmes) ; `test_build_blanc.py`
  vérifie aussi `pt/simulador/index.html`.
- **Vérifié le 8/11/2026** (Chrome sans tête, dist par liste blanche servi en local) : 375 et
  1 280 px × 3 cas (PV seul 6 kWp ; PV 10 kWp + batterie 7 kWh + HEMS, canton d'Esch ; outil 3 gaz
  2 000 m³, PAC 9 kW, PV 8 kWp) : aucune erreur JS (hors balise Cloudflare en local), aucun
  défilement horizontal, nombres de tous les résultats (outils 1 à 3, tableaux 1 à 7, verdicts)
  identiques à la page FR pour les mêmes paramètres d'URL.
- **À faire** : relecture par un locuteur natif portugais (Portugal) avant mise en ligne ; Search
  Console après déploiement ; envisager des liens vers le simulateur PT depuis les pages FR.

## i18n : l'allemand (/de), ajouté le 26/10/2026

Quatrième langue du site, calquée sur la recette /de d'index-lu (build.py
d'index-lu, section « allemand »). Public : frontaliers et propriétaires
allemands. Vouvoiement partout.

### Mécanique

- **Dictionnaires** : `scripts/i18n_de.json` + `i18n_de_js.json` (tableau de
  bord) et `scripts/i18n_sim_de.json` + `i18n_sim_de_js.json` (simulateur),
  miroirs EXACTS des clés EN (parité vérifiée par `check_dicts`, build en
  échec sinon). Les clés sont le texte FRANÇAIS des gabarits ; traduction par
  remplacement « plus longue clé d'abord » comme EN/LB.
- **Chemins** : `/de/` (tableau de bord) et `/de/rechner/` (simulateur, même
  mot qu'en LB : il est aussi allemand). Toujours AVEC barre finale
  (Cloudflare Pages sert les dossiers ainsi).
- **Nombres** : conventions FRANÇAISES conservées, comme en LB : locale JS
  `'fr-FR'` intacte, virgule décimale, « 2,5 % » avec espace, milliers par
  espace (conforme DIN 5008 / style STATEC). `to_de()` ne touche à AUCUN
  littéral numérique.
- **Dates** : `_tr_str_de` traduit les libellés-données (mois, abréviations
  `_ABBR_DE`, trimestres T→Q) et pose l'ordinal allemand « 4. November »
  (y compris « 1er » → « 1. »), via `_DE_ORD_RE` (copié de la règle LB).
- **Données dérivées** : `data/data.de.json` (blob traduit par
  `translate_data(data, _tr_str_de)`), entrées `de` dans `CSV_TITLES`,
  `JSON_TITLE`, `CSV_NOTES`, `DATASET` (JSON-LD) et le manifeste.
- **SEO** : hreflang `de` codé en dur dans les DEUX gabarits (template.html
  et template_simulateur.html) + généré dans sitemap.xml via LANG_PATHS /
  SIM_PATHS ; x-default reste EN. og:locale `de_DE`, images `og.de.png` et
  `og.sim.de.png` (générées par make_og / make_og_sim).
- **Sélecteur de langue** : drapeau `F_DE` (SVG copié d'index-lu), libellé
  « DE », ordre EN · FR · DE · LU.

### Décisions de traduction

- « capacité installée » → **installierte Leistung** (kW) ; « installations »
  → **Anlagen** ; « communes » → **Gemeinden** ; « relevé » → **Erhebung** ;
  « injection » → **Einspeisung** ; « tarif d'injection garanti » →
  **garantierter Einspeisetarif** ; « filières » → **Technologien**
  (légende courte du mix : KWK, Windkraft, Wasserkraft…).
- kWc → **kWp** (usage allemand), déjà le cas en EN/LB.
- Liens externes localisés comme en LB : guichet.public.lu/de/,
  pvg_tools/de/, deed.de, klima-agence.lu/de ; le titre du jeu de données
  Leneda reste en français (nom propre), de même que « Administration des
  contributions directes » (institution) et « Le Quotidien ».
- Verdict de l'outil 2 reformulé pour éviter le datif après le suffixe
  `years:' Jahre'` : « Option A (Klimabonus): Amortisationszeit 9,5 Jahre,
  Nettogewinn … über 25 Jahre. »
- Jamais de tiret cadratin (garde-fou existant, inchangé).

### Pièges connus (hérités, vérifiés le 26/10/2026)

- `LUX_SOLAIRE_CACHE=1` sert des données PÉRIMÉES si `.cache/` est vieux :
  toujours finir par un build SANS cache avant de publier.
- Les valeurs EN et LB des clés `">Commune</button>"` et `">Part PV</button>"`
  se terminent par `</th>` au lieu de `</button>` (balisage boiteux dans les
  pages EN/LB, corrigé par le parseur des navigateurs). Les valeurs DE
  ferment correctement `</button>` ; EN/LB laissés tels quels (décision à
  prendre par Sitraka).
- Le libellé « inst. » du graphique « paradoxe » est codé en dur dans
  `prerender()` (toutes langues) ; le JS, lui, utilise la clé `"' inst.'"`
  (DE : « Anl. »). Divergence statique/JS préexistante (LB : « Inst. »).

## Appel à l'action vers sitraka.lu/contact (3/11/2026)

Sur CHAQUE page du site (tableau de bord, simulateur, 400 pages communales, « Pour les communes »,
4 langues), un seul lien `.contact-cta` vers la page de contact de sitraka.lu, dans la langue de la
page : `https://sitraka.lu/contact/?from=solaire` (EN et LB), `/fr/contact/` (FR), `/de/contact/`
(DE) ; le paramètre `from=solaire` fixe l'objet du courriel côté sitraka.lu. Textes : EN « Want this
for your commune? Let's talk », FR « Vous voulez ça pour votre commune ? Parlons-en » (insécable
avant « ? »), DE « Wollen Sie das für Ihre Gemeinde? Sprechen wir », LB « Wëllt Dir dat fir Är
Gemeng? Schwätze mer driwwer ». Emplacement : sous la note des chiffres clés (tableau de bord et
pages communales), sous les badges de l'en-tête (simulateur), sous le titre (« Pour les communes »).
Mécanique : une clé par dictionnaire (`i18n_en/de/lb.json`, href compris) pour les deux gabarits ;
textes dans `communes.CONTACT` pour les pages générées ; style `.contact-cta` dans les deux gabarits
(hérité par les pages communales via le `<style>` du tableau de bord), masqué à l'impression.
Tant que la branche `home-1103` de sitraka-lu n'est pas fusionnée, la cible répond 404 (constaté le
3/11/2026).

## Déploiement

Cloudflare Pages, projet `lux-solaire`, domaine solaire.sitraka.lu. Depuis le 2/11/2026, le dist
est construit par LISTE BLANCHE (`scripts/make_dist.py`), le même script en local et dans
`.github/workflows/rebuild.yml`. Déploiement local, depuis la RACINE du dépôt (wrangler y compile
`functions/`, jamais copié dans le dist) :

```sh
/usr/bin/python3 scripts/build.py                       # SANS LUX_SOLAIRE_CACHE
/usr/bin/python3 -m pytest tests/ -q && node --test tests/sim-engine.test.mjs
/usr/bin/python3 scripts/make_dist.py /tmp/lux-solaire-dist
npx --yes wrangler@3.114.17 pages deploy /tmp/lux-solaire-dist --project-name=lux-solaire --branch=main --commit-dirty=true
```

- wrangler 3.x OBLIGATOIRE (4.x convertit en Workers assets) ; version exacte 3.114.17, la même
  que le workflow (`WRANGLER_VERSION`).
- `make_dist.py` copie `PUBLIC_FILES` (racine : pages, `_headers`, og, scripts JS servis, fichiers
  de vérification GSC et IndexNow) et `PUBLIC_DIRS` (`data`, `fr`, `de`, `lb`, `pt`, `simulator`,
  `municipality`, `for-municipalities`). Il ÉCHOUE si une entrée publique manque, si une entrée
  suivie par git à la racine n'est ni publique ni dans `INTERNAL` (tout NOUVEAU fichier servi doit
  être ajouté à la liste, sinon il ne serait jamais publié), ou si un fichier interne se retrouve
  dans le dist (CONTEXT.md, README.md, scripts/, tests/, archive/, functions/, .github/, gabarits,
  `.py`, `.md`, et les motifs de `.vercelignore`, gardé comme filet de sécurité). Le dossier de
  sortie doit être hors du dépôt.
- Vérifié le 2/11/2026 : le dist par liste blanche est identique (443 fichiers) à l'ancienne copie
  rsync par exclusion, à une fuite près que l'ancienne méthode laissait passer en local :
  `.ruff_cache/`.

## Workflow du lundi et alertes (2/11/2026)

`.github/workflows/rebuild.yml` (cron lundi 06:00 UTC, en pratique lancé avec plusieurs heures de
retard par GitHub ; déclenchement manuel possible). Étapes dans l'ordre, arrêt au premier échec :
build → `pytest tests/` → `node --test tests/sim-engine.test.mjs` → dist par liste blanche →
commit + push si `data/data.json` a changé → déploiement. Donc rien n'est commité ni redéployé si
le build ou un test échoue. Bloc `concurrency` (pas deux rebuilds simultanés), `timeout-minutes: 30`.
Versions figées sur celles du poste local au 2/11/2026 : pandas 2.3.3, requests 2.32.5,
pillow 11.3.0, pytest 8.4.2, wrangler 3.114.17 (Python 3.12 et Node 22 dans le workflow,
Python 3.9 en local). Pour les monter : changer le workflow ET cette ligne, après un build local.

**Versions figées, complément du 2/11/2026 (chantier B)** :
- pip : `pip install -r scripts/requirements.txt -c scripts/constraints.txt`. `requirements.txt` =
  dépendances directes ; `constraints.txt` = arbre COMPLET figé sur le poste local (numpy 2.0.2,
  python-dateutil, pytz, tzdata, urllib3, certifi, pluggy, etc.), vérifié résoluble en roues binaires
  pour Python 3.12 / Linux avec `uv pip compile` (commande en tête du fichier). Avant, numpy n'était pas
  figé et le workflow prenait la dernière version. Pour monter une version : les deux fichiers + build
  + tests en local (`tests/test_veille.py` vérifie qu'ils ne divergent pas).
- Actions épinglées par SHA de commit, tag en commentaire, SHA vérifiés avec
  `gh api repos/actions/<nom>/git/matching-refs/tags/<tag>` : checkout v4.4.0
  `11d5960a326750d5838078e36cf38b85af677262`, setup-python v5.6.0
  `a26af69be951a213d495a4c3e4e4022e16d87065`, setup-node v4.4.0
  `49933ea5288caeca8642d1e84afbd3f7d6820020` (mêmes versions majeures qu'avant).
- apt : `fonts-dejavu-core=2.37-8` (version de Ubuntu 24.04 « noble », poche Release, vérifiée sur
  Launchpad), donc `runs-on: ubuntu-24.04` au lieu de `ubuntu-latest` (la version apt dépend de
  l'image), précédé de `apt-get update`.
- Restent non figés au patch près : Python « 3.12 » et Node « 22 » (dernière mineure de la branche).
- Jeton (2/11/2026, relecture) : `actions/checkout` avec `persist-credentials: false`, le
  GITHUB_TOKEN (droit d'écriture) n'est plus laissé dans `.git/config` pour pip, le build, les tests
  et `npx wrangler` ; seule l'étape de commit le reçoit (`env: GITHUB_TOKEN`) et pousse par
  `git push https://x-access-token:…@github.com/$GITHUB_REPOSITORY.git HEAD:main`.
- Non fait (durcissement optionnel) : verrou pip par empreintes (`uv pip compile … --generate-hashes`
  puis `pip install --require-hashes`). PyPI interdit de republier un fichier sous le même nom, le
  risque résiduel est faible ; à faire avec une mise à jour de `test_dependances_figees`.

### Garde-fou de fraîcheur (`check_freshness`, build.py)

Avant tout téléchargement lourd, le build ÉCHOUE (exit 1, message « fraîcheur des données Leneda,
build arrêté ») si le relevé hebdomadaire le plus récent du jeu Leneda a plus de 10 jours
(`MAX_AGE_DAYS`) ou si les fichiers `commune` et `not-grouped` les plus récents ont plus de 7 jours
d'écart (`MAX_GAP_DAYS` ; un écart de 1 à 7 jours reste un simple avertissement). Dérogation
locale : `LUX_SOLAIRE_ALLOW_STALE=1` ramène le contrôle d'ÂGE à un avertissement (utile avec un
`.cache/` ancien, utilisé par le build à blanc des tests) ; l'écart, lui, échoue toujours. Ne jamais
la poser dans le workflow. Tests : `tests/test_fraicheur.py`.

### Où arrive l'alerte

- **E-mail GitHub d'échec de workflow** : c'est la seule alerte en place. Pour un déclenchement par
  `schedule`, GitHub prévient l'utilisateur qui a modifié en dernier la ligne `cron` du workflow
  (ici Sitraka17) ; pour un lancement manuel, celui qui l'a lancé. Il faut que
  github.com/settings/notifications, rubrique « Actions », ait l'e-mail coché (option « Only notify
  for failed workflows » conseillée). Objet du type « [Sitraka17/lux-solaire] Run failed:
  rebuild-weekly ». Le détail est dans l'onglet Actions du dépôt (étape en rouge, message du
  garde-fou en clair).
- Ce que l'e-mail NE couvre PAS : un workflow qui ne tourne plus du tout (GitHub désactive les
  `schedule` d'un dépôt public après 60 jours sans activité ; le commit hebdomadaire du bot n'a lieu
  que si les données changent) et une panne de Cloudflare après un déploiement réussi. D'où le
  contrôle externe ci-dessous.

### Veille de fraîcheur externe : `.github/workflows/fraicheur.yml` (2/11/2026)

Remplace le contrôle Grafana prévu (essai Grafana Cloud expiré, rien n'avait été créé). Workflow
GitHub quotidien (`cron: "17 7 * * *"`, plus déclenchement manuel), lecture seule
(`permissions: contents: read`, aucun secret, `persist-credentials: false`), checkout épinglé par SHA,
5 minutes au plus. Il lance `scripts/veille_fraicheur.py` (bibliothèque standard seulement, Python 3
de l'image) qui ÉCHOUE si :
- `https://solaire.sitraka.lu/data/data.json` ne répond pas 200, n'est pas du JSON, ou si
  `meta.date_iso` a plus de 10 jours (`MAX_AGE_DAYS`, égal à `build.MAX_AGE_DAYS`, testé) ou est
  daté de plus d'un jour dans le futur ;
- `/`, `/simulator/`, `/fr/` ou `/fr/simulateur/` ne répondent pas 200.
L'échec envoie l'e-mail GitHub « Run failed: veille-fraicheur » (mêmes réglages que ci-dessus : il
part vers la personne qui a modifié en dernier la ligne `cron` de CE workflow). Lancement local :
`/usr/bin/python3 scripts/veille_fraicheur.py`. Tests hors réseau : `tests/test_veille.py` (logique,
pages contrôlées existantes, actions épinglées par SHA dans les DEUX workflows, permissions, dépendances
figées). Limite : GitHub désactive aussi ce `schedule` après 60 jours sans activité du dépôt ; le
commit hebdomadaire du robot (données changées chaque lundi en pratique) suffit à l'éviter, mais un
arrêt prolongé des relevés Leneda couperait les deux workflows : vérifier l'onglet Actions en cas de
silence anormal.

### Ajouter un contrôle Grafana / uptime sur `meta.date_iso` (non retenu : remplacé par `fraicheur.yml` le 2/11/2026, procédure gardée pour mémoire)

Cible : `https://solaire.sitraka.lu/data/data.json`, champ `meta.date_iso` (ex. `"2026-11-02"`,
date du relevé Leneda ; cache Cloudflare 1 h). Seuil conseillé : alerte au-delà de 10 jours, comme
le build (le relevé du lundi est en ligne le lundi après-midi : un âge de 8 à 10 jours le mardi
signale déjà un lundi manqué).

1. Grafana Cloud, Testing & synthetics > Synthetics > Add new check > **Scripted** (k6), fréquence
   1 h, 1 ou 2 sondes européennes (ex. Frankfurt, Paris), script :

   ```js
   import http from 'k6/http';
   import { check } from 'k6';
   export default function () {
     const r = http.get('https://solaire.sitraka.lu/data/data.json');
     const d = r.status === 200 ? r.json('meta.date_iso') : null;
     const ageJours = d ? (Date.now() - Date.parse(d + 'T00:00:00Z')) / 86400000 : Infinity;
     check(r, {
       'HTTP 200': (x) => x.status === 200,
       'relevé Leneda de 10 jours au plus': () => ageJours <= 10,
     });
   }
   ```
2. Alerte : dans le check, « Alerting » avec la sensibilité « Low » ou une règle Grafana sur
   `probe_all_success` du job (échec sur 2 évaluations de suite), vers le point de contact e-mail
   déjà utilisé par les alertes d'uptime existantes.
3. Variante sans script (datasource Infinity, déjà utilisée pour le tableau de bord d'indexation) :
   requête JSON sur la même URL, parser « Backend », sélecteur `meta`, colonne `date_iso` de type
   « Timestamp » ; règle d'alerte avec une expression Math `(now() - $A) / 86400000 > 10` (adapter à
   la syntaxe de l'instance) ; plus fragile que le check scripté.
4. Simple check d'uptime HTTP (si seul ce type est disponible) : statut 200 et expression régulière
   sur le corps `"date_iso": ?"20\d\d-` ; il détecte un fichier absent ou cassé, PAS un relevé
   périmé.

## Vue par commune des tailles d'installation (30/10/2026)

Demande de la Ville de Differdange (service Travaux neufs) : répartition des
installations PV par classe de taille, commune par commune.

- `build()` calcule `sizes_c` : `{LAU2: [[installations, kW], ...]}`, aligné
  sur les classes de `sizes` (fichier hebdomadaire `not-grouped`, une ligne par
  installation). Somme des communes = total national (vérifié : 38 065).
- Section « paradoxe » : sélecteur `#pc` (« Voir une commune »), qui redessine
  le graphique et le tableau « Données du graphique », et écrit
  `?commune=<slug>#paradoxe` dans l'adresse. Le slug = nom sans accents, en
  minuscules, tirets (`esch-sur-alzette`). Lien partageable :
  `https://solaire.sitraka.lu/fr/?commune=differdange`.
- Le prérendu (robots, sans JS) reste national ; seul le JS affiche une commune.
- Export `data/csv/solaire_communes_tailles.csv` (800 lignes, capacité en kW).

### Tranches des aides communales et historique hebdomadaire (30/10/2026, suite)

- **Sélecteur « Classes »** (`#pg`, `?classes=aides`) : bascule le graphique sur
  les tranches du Klimabonus Gemengen (`KB_EDGES` : 30 / 200 / 500 kWc / 5 MWc ;
  tranche vide à l'échelle nationale écartée), avec une note des taux du
  barème 2025 (guide pratique V1 05/2025 : 50 % ≤ 675 €/kWc, 45 % ≤ 505,
  40 % ≤ 425, ombrière 45 % ≤ 990). ⚠️ Barème révisé chaque année : vérifier
  les taux chaque janvier dans `scripts/baremes.json` (source unique, voir « Barèmes uniques et
  tests ») ; le build signale alors les phrases à corriger dans `template.html` + les 3
  dictionnaires. Export `solaire_communes_tranches_aides.csv`.
- **Archive** `archive/leneda-not-grouped-AAAA-MM-JJ.csv.gz` (~115 Ko/semaine) :
  Leneda remplace son fichier par installation chaque semaine sans garder
  d'historique. `archive_snapshot()` en garde une copie à chaque build (le
  workflow du lundi la commite via `git add -A`) ; `archive/` est exclu du
  site (.vercelignore). Première copie : 14/09/2026 (récupérée du cache local).
- **`hist`** : variation nette (installations, kW, par classe) depuis la plus
  ancienne copie de moins de 92 jours ; affichée dans la phrase de résumé et
  entre parenthèses sur les barres. Variation NETTE : une installation
  agrandie change de classe (−1 dans l'une, +1 dans l'autre).

## Grandes installations : lignes de plus de 100 kW apparues ou disparues (chantier C, 2/11/2026)

Module `scripts/grandes.py` (textes des 4 langues DANS le module, comme `communes.py`), appelé par
`build.py` (`import grandes` : le module DOIT être commité avec build.py, sinon le rebuild du lundi
échoue à l'import). Section `<section id="grandes-installations">` du tableau de bord (marqueur
`<!--PRE_BIGNEW-->` de template.html, rendu par `prerender`) et des 400 pages communales
(`communes.write_all`). Bloc `bigs` de data*.json, export `data/csv/solaire_grandes_installations.csv`
(une ligne par ligne apparue ou disparue, colonnes en anglais, `note` = `same_value_other_municipality`
ou `same_technology_changed_in_municipality`).

- **Source** : les copies archivées du fichier Leneda par installation
  (`archive/leneda-not-grouped-AAAA-MM-JJ.csv.gz`, depuis le 14/09/2026). Pas d'identifiant, pas de
  date de mise en service, pas d'exploitant : impossible de suivre une installation d'un relevé à l'autre.
- **Méthode** : comparaison en MULTI-ENSEMBLE sur la clé (LAU2, filière, kW arrondi à 3 décimales)
  des lignes de plus de 100 kW de deux copies CONSÉCUTIVES (deux lignes identiques qui deviennent
  trois = une ligne apparue). Seuil STRICT : `kW > 100`, 100 kW exactement exclus (`BIG_KW`).
- **Remarques factuelles** : « m » = même filière et même puissance disparues dans une AUTRE
  commune au même relevé (appariement un pour un) : changement de commune possible ; « r » = une
  ligne de même filière disparue ET une apparue dans la MÊME commune au même relevé : agrandissement
  ou correction possible. Jamais « a augmenté » ni « nouvelle installation » : le fichier ne permet
  pas de trancher. D'où le titre « Grandes installations : lignes apparues » (EN « Large
  installations: rows that appeared », DE « Großanlagen: hinzugekommene Zeilen », LB « Grouss
  Installatiounen: dobäikomm Zeilen »), renommé le 2/11/2026 (avant : « Nouvelles grandes
  installations », qui affirmait la nouveauté ; ex. Rambrouch éolien 12 600 kW marqué « m » avec
  Ell, Nommern biogaz 350 kW marqué « r »).
- **Période** : le chapeau du tableau de bord dit la période réelle (« Du 14 septembre 2026 au
  2 novembre 2026, sur 3 relevés archivés comparés chacun au précédent… ») et, à partir de trois
  copies, la part du dernier relevé. Au 2/11/2026 : 18 lignes apparues (16 entre le 14/09 et le
  26/10, intervalle de 42 jours dû au trou d'archive ; 2 au relevé du 2/11 : Dippach éolien
  4 260 kW, Heffingen PV 4 623,84 kW) et 3 disparues (Ell 12 600, Betzdorf 625, Nommern 300) ;
  chiffres recalculés indépendamment (pandas) lors de la relecture du 2/11/2026. Un écart de plus de
  8 jours entre deux copies est signalé dans la méthode (« 42 jours après la précédente »).
- **Allemand / luxembourgeois** : dans les pages communales, le nombre suit « je Anlage » / « pro
  Installatioun » et la date passe entre parenthèses, pour que l'année du relevé ne se colle pas au
  nombre (« 2026 16 Anlagen » se lisait comme un seul nombre).
- **Tests** : `tests/test_grandes.py` (multi-ensemble, seuil exclu, remarques m / r, rendu 4 langues,
  parité des textes, noms de filières alignés sur le mix, période réelle du chapeau, ordre DE/LB).
  Cité dans le commentaire de `.github/workflows/rebuild.yml`.

## Pages par commune, page « Pour les communes », compteur d'événements, 404 (30/10/2026)

- **`scripts/communes.py`** (appelé à la fin de `render_all`) : 100 communes × 4 langues
  (`/municipality/<slug>/`, `/fr/commune/`, `/de/gemeinde/`, `/lb/gemeng/`) + page
  « Pour les communes » (`/for-municipalities/`, `/fr/pour-les-communes/`, `/de/fuer-gemeinden/`,
  `/lb/fir-gemengen/`). Textes par langue DANS ce module (pas dans les dictionnaires des gabarits).
  Le style et la barre de série sont repris des pages déjà rendues. Contenu : 6 KPI avec rangs,
  tailles (barres + variation depuis l'archive), tranches Klimabonus Gemengen, comparaison canton
  et communes de taille comparable, liens, commune précédente/suivante. Sitemap : 412 URL.
  Le slug (`communes.slug`) est le même qu'en JS (NFD, minuscules, tirets).
- Tableau de bord : noms de communes cliquables (`__CPATH__`), lien « Page de la commune » dans
  le résumé du sélecteur, lien vers « Pour les communes » sous « Les 100 communes ».
- **Compteur sans cookie** : `ev.js` (client, sendBeacon) → Pages Function `functions/e.js` →
  D1 `lux-solaire-events` (id 6c890a2d-8a1a-40f5-b870-b1573f6e8f53), binding `DB` posé sur le
  projet Pages via l'API (pas de wrangler.toml). Table `ev(day, type, lang, page, target, ref, n)`,
  totaux par jour, aucune IP ni identifiant. Types : dl (fichier), commune, classes, copy, contact,
  sim, page (clic vers une page communale), land (arrivée depuis un autre site : hôte du référent).
  `functions/` est exclu du dist (.vercelignore) mais compilé par `wrangler pages deploy` lancé
  depuis la racine du dépôt. Rapport : `scripts/events_report.sh`.
- **404.html** : vraie page 404 (Cloudflare Pages ne sert plus la page EN pour une URL inconnue).

## Audits du 1/11/2026 (technique + sources)

Rapports : `~/differdange-pilote/audit-sources-solaire.md` (sources, vérifiées le 1/11) et le rapport
technique résumé ci-dessous. Corrigé le 1/11 : arrondi des pages communales aligné sur Math.round
(`jsround`), référence d'archive fixe (plus ancienne copie, 14/09), `_fetch` avec code HTTP et 3 essais,
commune sans relevé de référence (« n.d. »), paramètres d'URL invalides du simulateur, HTML EN/LB des
en-têtes du tableau, phrase FAUSSE « sous 30 kWc : Klimabonus des particuliers » (vrai seulement pour
des logements), installation à 0 kW hors classes (`include_lowest`), sources et population sur les pages
communales, « 1er October » en anglais, en-têtes `_headers` (HSTS, nosniff, Referrer-Policy, cache).

Reste à faire (par priorité) :
- ~~simulateur : HEMS, 2031, toiture/façade, régime transitoire B, prix 0,16/0,20, gain non actualisé~~
  FAIT le 2/11/2026 (voir « Simulateur mis à jour le 2/11/2026 » ci-dessous) ;
- ~~alerte si le relevé Leneda a plus de 10 jours (build en échec) + versions figées dans le workflow~~
  FAIT le 2/11/2026 (voir « Workflow du lundi et alertes ») ; contrôle externe FAIT le 2/11/2026 par un
  workflow GitHub quotidien (`fraicheur.yml`) à la place de Grafana ;
- ~~tests (slug Python/JS, arrondis, barèmes, build sur les archives) ; contrôle explicite des colonnes Leneda~~
  FAIT le 2/11/2026 (voir « Barèmes uniques et tests ») ;
- ~~compteur /e : listes blanches (lang, chemins)~~ FAIT le 2/11/2026 (voir « Accessibilité et compteur /e » ci-dessous) ;
  reste la limite de débit (rien de fait : pas de stockage d'IP par principe, à faire côté règles Cloudflare) ;
- ~~`scripts/baremes.json` unique~~ FAIT le 2/11/2026 ; découper build.py ;
- ~~moteur du simulateur en module pur (`sim-engine.js`) réutilisable par communes.sitraka.lu~~
  FAIT le 2/11/2026 (voir « Moteur du simulateur » ci-dessous) ;
- ~~accessibilité : contraste des barres ambre (2,1:1), `<main>` + lien d'évitement~~ FAIT le 2/11/2026 ; CSP à tester.

## Accessibilité et compteur /e (2/11/2026)

- **Contraste (WCAG 1.4.11)** : l'ambre `--amber` #EE9B05 ne fait que 2,06:1 sur `--paper` et 2,25:1 sur
  blanc. Couleur de remplissage inchangée ; un filet intérieur `box-shadow: inset 0 0 0 1px var(--amber-text)`
  (#8A5600 : 5,62:1 sur `--paper`, 6,16:1 sur blanc) entoure les barres `.hbars .fl`, `.pair .b.cnt`,
  `.minitr i`, les pastilles `.sw.am` et le segment PV de la barre du mix (`.mixbar .am`, classe posée par
  le JS ET par `prerender`). Simulateur : `stroke` `--amber-text` sur les barres ambre de la figure 1.
  La courbe de la figure 2 (#C77F00, 3,25:1 sur blanc) et le liseré de l'aire PV passaient déjà.
- **Biogaz (2/11/2026, chantier B)** : `--biogas` #8FA855 ne fait que 2,43:1 sur `--paper` et 2,66:1 sur
  blanc. Même traitement que l'ambre, couleur inchangée : filet `--biogas-line` #4F6B25 (5,54:1 sur
  `--paper`, 6,07:1 sur blanc) sur les pastilles `.sw.bg`, le segment `.mixbar .bg` (classe posée par le
  JS via `TECHS[].cl` ET par `prerender`, dict `CL` de build.py) et un liseré de 1,25 px sur le bord
  supérieur de l'aire biogaz de la figure de trajectoire. Une teinte assez foncée pour 3:1 (#7B9644,
  3,05:1) ne ferait que 1,12:1 avec la biomasse #6B8F3D : filières indiscernables, d'où le filet.
  Vérifié à 375 et 1 280 px (pastilles, barre du mix, légende ; pas de défilement horizontal).
- **Structure** : lien d'évitement `<a class="skip" href="#contenu">` (premier élément focalisable, visible
  au focus) avant la barre de série, puis `<main id="contenu" tabindex="-1">` jusqu'avant `<footer>`, sur les
  8 pages des gabarits ET les 404 pages de communes.py (`_shell`, libellés dans `SKIP`). Libellés : « Aller
  au contenu » / Skip to content / Zum Inhalt springen / Op den Inhalt sprangen (clé dans `i18n_en/de/lb.json`).
- **Mobile (375 px)** : il y avait un défilement horizontal préexistant (tableaux des `details.alt`, grille
  PVGIS et tableaux du simulateur, étiquettes du graphique des tailles). Corrigé : `.grid-2` en
  `minmax(0,1fr)`, `overflow-x:auto` sur `details.alt`, `.pair`, `figure.tab`, `.card.refs` ; sous 520 px
  l'étiquette du graphique des tailles passe sous la barre. Vérifié : 412 pages sans défilement à 375 px.
- **Échappement** : noms de communes et cantons échappés dans `prerender`, `communes.py` (`esc`) et le JS
  (`escH`, `new Option()` pour la liste des communes) ; « < » échappé en `\u003c` dans les blocs JSON inlinés
  (`/*__DATA__*/`, `/*__PVGIS__*/`, `__BAREMES_JSON__`, JSON-LD des pages communales).
- **Nombre de communes** : jeton `__NCOMMUNES__` (badge, titre de la table), rang « sur N », titres CSV
  (`{n}` = nombre de lignes). `N_COMMUNES = 100` reste le contrôle de format Leneda (build en échec si ≠ 100).
- **Compteur `functions/e.js`** : écrit seulement si type ∈ liste, lang ∈ en/fr/de/lb, page = chemin réel
  du site (accueil, simulateur, page communale `[a-z0-9-]`, « Pour les communes ») ; `Sec-Fetch-Site` doit
  valoir `same-origin` quand l'en-tête est présent ; écriture D1 dans un try/catch (erreur journalisée,
  réponse 204). Schéma de la table `ev` inchangé. Pas de limite de débit.

## Relecture mobile du 2/11/2026 (lot « 1 à 5 »)

- **FAQ batterie** : « 4 000 à 6 000 € d'investissement net » (écrit à la main) valait 2 800 à 5 600 € ;
  jetons `__BAT7LO__`/`__BAT7HI__` calculés dans `sim_numbers()` (7 kWh × 700 ou 1 100 € − `kb_batt(7)`,
  à la centaine). La fourchette 700-1 100 €/kWh est présentée comme hypothèse de l'outil sans source
  publiée (900 € par défaut) : À SOURCER (voir l'audit des sources, ligne « Coûts »).
- **Barres `.hbars` sous 520 px** : nom sur sa propre ligne, puis barre + valeur (`.vv` en `max-width:14em`,
  retour à la ligne permis). Avant : la valeur en max-content écrasait la colonne du nom à 0 px.
- **Figures SVG sur mobile** : figures 1 et 2 du simulateur (cadre < 520 px) et aire du tableau de bord
  (cadre < 620 px) dessinées à la largeur réelle du cadre (`figW`, `drawArea`), `min-width:0` en ligne,
  initiales des mois, un libellé de relevé sur k (le dernier toujours affiché), redessin au `resize`.
  Fig. 2 : si les valeurs finales A et B se chevauchent, la plus basse passe sous sa courbe.
- **Tableau PNEC** : `.card.refs{overflow-x:auto}` ajouté aussi dans `template.html`.
- Non traités dans ce lot (hors demande « 1 à 5 ») : `workflow_dispatch` hors `main` dans rebuild.yml,
  listes blanches plus strictes de `functions/e.js` (slugs réels, x/r, taille du corps). FAIT ensuite
  (voir « Relecture du 2/11/2026, lot suivant »).

## Relecture du 2/11/2026, lot suivant

- **FAQ coûts** : `sim_numbers()` calcule le net sur les coûts NON arrondis (6 × 1 600 = 9 600 et
  6 × 2 200 = 13 200 €, affichés tels quels) : « environ 3 900 à 7 500 € » (avant : 4 300 à 7 300 €,
  double arrondi).
- **Préfinancement** : optionnel, par un installateur inscrit au registre des demandeurs intermédiaires,
  ou demande classique ensuite ; 4/1/2026-31/12/2029 = période d'éligibilité des FACTURES (FR + EN/DE/LB).
- **Sources** : montant HEMS (500 €, 2 équipements) cité d'après guichet.lu, date du 1/10/2026 d'après
  gouvernement.lu ; prix de l'électricité : « loi du 22 juillet 2026 » issue du projet 8707 (le PDF de la CHD
  est cité comme exposé de l'amendement, plus comme projet en cours).
- **Tableau 4** : la note de lecture est un `<p class="hint" id="aid-note">` HORS du tableau (le `<caption>`
  défilait avec le tableau à 375 px) ; le symbole € est dans `aidNote1`/`aidNote2` (EN « €5,742 »,
  FR/DE/LB « 5 742 € »).
- **CSS simulateur** : `.tab figcaption` (la légende « Tableau 1. » avait le style par défaut),
  `.fld label.chk{justify-content:flex-start}` ; tableau de bord : `.refs a` en `--amber-text`.
- **Élision** : `communes.de_k()` (« canton d'Esch », « canton d'Echternach ») dans le texte, la meta
  description et le JSON-LD des pages communales ; simulateur : clé JS `cantonLineV`.
- **rebuild.yml** : le job ne tourne que si `github.ref == 'refs/heads/main'` (un déclenchement manuel sur
  une autre branche ne déploie plus en production).
- **Compteur `/e`** : listes blanches générées au build (`functions/_allow.js`, `write_ev_allowlist` dans
  build.py : 100 slugs réels + fichiers de données liés depuis les pages ; pas une route Pages, vérifié avec
  `wrangler pages functions build`). Cible `x` contrôlée par type (dl = fichier lié, commune = slug ou `lux`,
  classes = `aides`/`detail`, copy = ids `rt-copy*`, contact = hello@sitraka.lu, page = slug, sim/land = vide),
  `r` seulement pour `land` et réduit à un nom d'hôte, corps limité à 1 Ko (lecture plafonnée même sans
  Content-Length). Le simulateur ne charge pas ev.js : son motif de page a été retiré. Toujours sans cookie
  ni IP ; la limite de débit reste à poser en règle Cloudflare.
- **Moteur** : l'aide HEMS est plafonnée au coût saisi du HEMS (`hemsAid(hems, montant, bar, coût)`, test ajouté).

## Simulateur mis à jour le 2/11/2026

Sources relues le 2/11/2026 : guichet.lu Klimabonus 2026 installations techniques (mise à jour du
11/08/2026), communiqué gouvernement.lu du 16/07/2026, Klima-Agence « transition period » (17/12/2025),
ILR (loi du 22/07/2026), projet de loi 8707 devenu la loi du 22/07/2026 (exposé de l'amendement gouvernemental).
- **HEMS** : case « Ajouter un système de gestion de l'énergie » (ids `hems`, `hcost` 1 000 € par
  défaut = hypothèse SANS source, `haid` 500 € max), coût compté dans les deux options, aide en
  option A seulement (cumul avec le tarif garanti non précisé par guichet.lu), aucun gain
  d'autoconsommation modélisé. Factures du 1/10/2026 au 31/12/2030, hors préfinancement.
- **Délais** : factures PV/batterie du 4/1/2026 au 31/12/2029, ou 31/12/2031 si commande au plus
  tard le 31/12/2029 ; demande au plus tard le 31/12/2031. Condition toiture/façade/enveloppe, ≥ 2 kWc.
- **Option B** : régime transitoire (offres signées du 1/10/2024 au 4/3/2026, 20 % ≤ 500 €/kWc + tarif,
  facture finale ≤ 31/12/2026) cité, non simulé. Non vérifié : la disponibilité du tarif garanti SANS
  aide pour une offre signée après le 4/3/2026 (aucune source relue ne le dit explicitement).
- **Prix** : 0,16 € = août à décembre 2026 (aide ~4 c€/kWh, MDC −3,71 c€) ; 0,20 € = tarif de janvier à
  juillet 2026 (MDC −0,10 c€, qui comprend déjà une contribution de l'État : 8707 couvre toute
  l'année 2026, plafond 88 puis 107 M€). Les « 150 M€ » (presse, 12/2025) sont retirés.
- **Rentabilité** : libellé « gain net sur 25 ans (non actualisé) », curseur `disc` (0 % par défaut)
  qui n'actualise QUE le gain net ; retour sur investissement et figure 2 restent non actualisés.
  Méthode : part autoconsommée = heuristique maison, batterie ni remplacée ni dégradée.
- **Montants d'exemple** : jetons `__KB3__`, `__KB6__`, `__KB10__`, `__C6LO__`, `__C6HI__`,
  `__NET6LO__`, `__NET6HI__`, `__TAR26__`, `__TAR27__` calculés par `sim_numbers()` (build.py, mêmes
  formules que le JS) ; « 4 500 à 7 500 € » corrigé en 4 300 à 7 300 €. La légende du tableau 4 est
  générée en JS (`aidNote1..3`).
- ~~Bogue : `.fld{display:grid}` l'emporte sur l'attribut `hidden` (champ « Coût de la batterie » visible
  sans batterie)~~ CORRIGÉ le 2/11/2026 par `.fld[hidden]{display:none}`.

## Pré-rendu statique du simulateur et trois profils types (2/11/2026, SEO)

- Avant : les résultats du simulateur (KPI de l'outil 1, verdict et options A/B de l'outil 2,
  tableau 1) n'existaient qu'après exécution du JS ; le HTML servi ne contenait que des tirets.
  Depuis le 2/11/2026, `scripts/sim_prerender.mjs` (node) calcule avec le MÊME moteur
  (`/sim-engine.js` + `SimEngine.BAREMES`, régénéré juste avant) le scénario par défaut et trois
  profils types, et `build.py` (`sim_prerender()`, `sim_static()`) écrit ces chiffres dans le HTML
  à la place des tirets ; le JS recalcule ensuite les mêmes valeurs au chargement.
- Les libellés ne sont PAS dupliqués en Python : `_jsl(lang, name, tpl_sim)` relit `name:'…'` dans
  l'objet `L` du gabarit (FR) ou dans la valeur traduite de `i18n_sim_*_js.json` (EN/DE/LB). Les
  formats imitent le JS (`_thousands`/`_jsround`, `_dec1`, `maximumFractionDigits: 1` → `dmax1`,
  `%` collé en anglais).
- Section `#profils` (template_simulateur.html, entre l'outil 3 et la FAQ) : « Tableau 7 », trois
  profils (3 kWc sud-est 2 500 kWh ; 6 kWc sud 4 500 kWh ; 10 kWc + batterie 7 kWh 10 000 kWh),
  jetons `__P1_…__` à `__P3_…__`, liens `?p=…&cons=…` qui chargent le profil dans la page.
  Les cas sont définis dans `sim_prerender.mjs` (coût = kWc × 1 800 €, batterie × 900 €, comme
  `init()`). Textes traduits dans `i18n_sim_{en,de,lb}.json`.
- Pages communales : le lien vers le simulateur passe `?canton=<canton>` (présélection).
- `baremes.check_page` : le motif « aide HEMS » ignore `HEMS)` immédiatement suivi d'un chiffre
  (libellé « Klimabonus (panneaux, batterie, HEMS) » + montant pré-rendu de l'option A).
- Le build dépend désormais de node pour le pré-rendu (le workflow installe déjà Node 22).

## Moteur du simulateur (`/sim-engine.js`, 2/11/2026)

Le calcul du simulateur est sorti du gabarit dans `sim-engine.js` (racine, servi publiquement :
https://solaire.sitraka.lu/sim-engine.js). Fonctions PURES : ni DOM, ni variable globale, aucun
libellé (la mise en forme et les textes traduits restent dans `template_simulateur.html`, qui garde
`read()` et `render()` et appelle `E.compute(I, G, BAR)`).

- **Chargement** : script classique `<script src="/sim-engine.js?v=…">` placé avant le script inline
  (expose `window.SimEngine`) ; sous Node, `require()` ou `createRequire(import.meta.url)` (CommonJS,
  pas de `package.json` dans le dépôt). `?v=` = 10 premiers caractères du SHA-256 du fichier, substitué
  par build.py (jeton `__SIMENGINE_V__`) ; le fichier entre dans l'empreinte de la date de contenu des
  pages simulateur. Cache court : `Cache-Control: public, max-age=3600` (`_headers`).
- **Barèmes** : un seul objet passé en paramètre à toutes les fonctions qui en dépendent ; celui du site
  est `SimEngine.BAREMES` (gelé, `version: '2026-11-02'`) :
  `klimabonusPV {pMin 2, pCap 15, a 1155, b 35, max 10000}` (p × (a − a/b × p)),
  `klimabonusBatt {qMin 2, qCap 9, a 500, b 18, max 2250}`, `hems {aideMax 500}`,
  `tarif {seuilKw 10, petit 165, grand 155, baisse 0.97, anneeBase 2019, duree 15}` (€/MWh),
  `horizon 25`, `anneeOnduleur 12` (indice 0 = 1re année), `autoconso {base 0.30, expo −0.6, min 0.1,
  max 0.9, battGain 0.35, battJour 0.5}` (heuristique maison, pas un barème officiel). Pour une autre
  hypothèse : `{...SimEngine.BAREMES, tarif: {...SimEngine.BAREMES.tarif, baisse: 0.96}}`.
  Depuis le 2/11/2026, ce bloc est RÉGÉNÉRÉ par build.py depuis `scripts/baremes.json` (marqueurs
  `BAREMES:DEBUT` / `BAREMES:FIN`, ne pas l'éditer à la main) et `sim_numbers()` lit le même fichier.
- **API** (`pvgis` = contenu de `data/pvgis.json`, `bar` = objet de barèmes) :
  - `gridYield(pvgis, az, tilt)` : kWh/kWc/an de la grille PVGIS (0° = `0:0`, symétrie est/ouest) ;
  - `yieldPerKwc(pvgis, az, tilt, canton)` : idem × `pvgis.cantons[canton].factor` ;
  - `selfShare(prod, cons, batt, bar)` : part autoconsommée (fraction) ;
  - `bonusPV(p, bar)`, `bonusBattery(q, bar)`, `hemsAid(hems, montant, bar)` (min(montant, aideMax),
    option A seulement), `feedInTariff(p, annee, bar)` (€/kWh) ;
  - `annualFlows({capex, self, inj, price, growth, deg, inv, injPrice(y)}, bar)` → `{cf, gains}` ;
  - `cumulative(cf)`, `npvAt(cf, r)`, `netGain(cf, disc %)` (cumul non actualisé si 0),
    `payback(cum)` (années ou `null`), `irr(cf)` (fraction ou `null`), `analyse(flux, disc)` ;
  - `compute(I, pvgis, bar)` avec `I = {p, az, tilt, canton, cons, batt, scAuto, sc, cost, bcost,
    hcost, haid, hems, inv, year, price, growth, market, deg, disc}` (mêmes unités que les champs de
    la page) → `{P, cons, ey, prod, sc, self, inj, bonus, capexGross, tar, A, B, lcoeA, lcoeB}`,
    `A`/`B` = `{cum[26], pb, npv, irr, y1}` (A = Klimabonus, B = tarif garanti).
- **Tests** : `node --test tests/sim-engine.test.mjs` (19 tests à l'origine, 32 depuis le volet chauffage). `tests/fixtures/sim-reference.json`
  a été calculé AVANT l'extraction avec l'ancien code inline (commit d2cc47b) par
  `tests/gen_reference_old.mjs` sur les 10 cas de `tests/fixtures/sim-cases.json` ; le nouveau moteur
  les reproduit À L'IDENTIQUE (égalité stricte, pas de tolérance). Ne pas régénérer ces références
  depuis le nouveau code. `tests/` est exclu du dist (`.vercelignore`).
- **Réutilisation** (communes.sitraka.lu, plus tard) : charger `https://solaire.sitraka.lu/sim-engine.js`
  ou en copier une version datée ; ne jamais diverger des barèmes sans changer `version`.
- Comportement inchangé, une nuance : l'aide HEMS est désormais plafonnée par `hems.aideMax` (500 €),
  ce que le champ `haid` (max 500) imposait déjà dans la page.

## Barèmes uniques et tests (2/11/2026)

- **`scripts/baremes.json`** = source UNIQUE des barèmes : Klimabonus PV (P × (1 155 − 33 P), 2 à
  15 kWc, 10 000 €), batterie (Q × (500 − 500/18 Q), 2 250 €), HEMS (500 €), tarif d'injection (165 /
  155 €/MWh × 0,97^(n−2019), 10 kW, 15 ans), Klimabonus Gemengen (barème 2025 : 50/45/40 %,
  675/505/425 €/kWc, ombrière 45 % / 990 €/kWc), hypothèses du modèle (horizon, onduleur,
  autoconsommation, sans source). Chaque entrée : `valeur`, `source` (URL), `date_source`,
  `date_verification`. Le fichier n'est pas servi (`scripts/` exclu du dist).
- **`scripts/baremes.py`** (chargement et usages) : `engine_bar()` (objet au format du moteur),
  `sync_engine()` (régénère le bloc BAREMES de `sim-engine.js` à chaque build), `kb_pv`, `kb_batt`,
  `tarif` (FAQ), `kb_edges` / `kb_labels` (tranches Gemengen de build.py et communes.py),
  `check_page` / `check_pages` (contrôle des phrases).
- **Simulateur** : l'objet est inliné au build (`BAR = Object.freeze(__BAREMES_JSON__)` dans
  `template_simulateur.html`) ; le champ `haid` prend son maximum de `aide_hems` (`__HEMS_MAX__`).
- **Pages communales** : colonne « Aide », note et lien du guide générés depuis le fichier (communes.py).
- **Contrôle des phrases** : les phrases traduites qui citent ces chiffres restent dans les gabarits et
  les dictionnaires ; après rendu, `baremes.check_pages` relit les 412 pages (simulateur, tableau de
  bord, pages communales) et le build ÉCHOUE si un chiffre cité (formules, plafonds, seuils, tarif,
  HEMS, taux et plafonds Gemengen, ombrière, année du barème) ne correspond plus, ou si une phrase
  attendue a disparu (motif reformulé : adapter `check_page`). Non contrôlés : le régime transitoire
  de l'option B (20 %, 500 €/kWc), les « 15 ans » du tarif, les bornes « 30 / 200 / 500 kWc » des
  textes des pages « Pour les communes ».
- **Format Leneda** : `check_leneda()` (build.py, juste après le téléchargement) vérifie les colonnes
  des fichiers par commune (`COMMUNE_COLS`) et par installation (`NG_COLS`), les types d'installation
  connus, des valeurs numériques, et 100 communes (`N_COMMUNES`) dans le relevé le plus récent (95 à 105
  dans les plus anciens) ; message clair sinon.
- **Tests Python** : `/usr/bin/python3 -m pytest tests/` (pytest installé avec `--user`) : slug Python =
  `slugC` et `slug` du sélecteur de template.html exécutés par node, sur les 100 noms réels ;
  `_jsround` = Math.round et `_dec1` = toLocaleString sur des cas .5 (comparés à node) ; barèmes et
  contrôle des phrases (valeurs périmées détectées) ; classes de taille avec `include_lowest` ;
  format Leneda ; build « à blanc » (copie du dépôt en dossier temporaire, `.cache/` + archives, sans
  réseau, sauté proprement s'il manque une réponse en cache). Tests du moteur : `node --test
  tests/sim-engine.test.mjs`.
- **Test croisé des formules (2/11/2026, chantier B)** : `tests/test_croise_baremes.py` exécute node sur
  `sim-engine.js` et compare à 1e-9 près `kb_pv` / `kb_batt` / `tarif` / `kb_pac` (baremes.py) à
  `bonusPV` / `bonusBattery` / `feedInTariff` / `klimabonusPAC` : puissances 0 à 40 kWc au pas de 0,01,
  batteries 0 à 25 kWh au pas de 0,01, tarif sur 0 à 40 kW (pas de 0,1) × années 2019 à 2035, PAC sur
  2 352 combinaisons (commandes dans et hors de la période majorée, bornes comprises, factures,
  remplacement, gaz / mazout / électrique, zone d'eau, coûts de distribution autour du plafond). Les
  deux copies des formules sont GARDÉES (faire lire le moteur par node au build aurait rendu le build
  Python dépendant de node pour quatre formules d'une ligne) ; le test garantit leur égalité (vérifié :
  un `<=` au lieu de `<` sur `pCap` côté Python est détecté à 15 kWc).
- **Slug JS unique (2/11/2026, chantier B)** : `slugC` (template.html) est la SEULE fonction de slug
  côté JS ; la copie locale `slug` du sélecteur « Voir une commune » (écrite avec des caractères
  combinants LITTÉRAUX dans la classe `[...]`) est supprimée, le sélecteur, le lien « Page de la
  commune » et `?commune=` appellent `slugC`. `tests/test_slug.py` vérifie l'égalité avec
  `communes.slug` sur les 100 communes, qu'il n'y a qu'une définition, et qu'aucun caractère combinant
  littéral (U+0300 à U+036F) ne reste dans les gabarits, `sim-engine.js`, `rt.js`, `ev.js`.
- **`_jsround`** corrigé : `floor(x + 0.5)` donnait 1 pour 0.49999999999999994 (Math.round : 0).
- **`vercel.json` supprimé** (inutile sur Cloudflare Pages) : son `Cache-Control: public, max-age=3600`
  sur `/data/*` est passé dans `_headers` ; `Access-Control-Allow-Origin: *` est déjà envoyé par
  Cloudflare Pages (vérifié le 2/11/2026), donc pas répété. `.vercelignore` reste (relu par
  `scripts/make_dist.py` comme filet de sécurité : aucun de ses motifs ne doit se trouver dans le dist).

## Moteur du simulateur : chauffage (`computeHeat`, 2/11/2026)

`sim-engine.js` couvre aussi le remplacement d'une chaudière par une pompe à chaleur (PAC) air-eau,
avec ou sans panneaux, batterie, HEMS et ballon tampon. Simulation heure par heure sur une année
météo type (formules établies le 1/11/2026, hypothèses de l'outil sauf barèmes sourcés ci-dessous). **Partage public / privé** : le moteur ne contient que les règles NATIONALES
(Klimabonus PAC, prix des énergies, CO2) ; une aide locale (commune) est un paramètre GÉNÉRIQUE
(`aidesLocales`), aucun barème communal n'est écrit ici (un test le vérifie). Le barème de
Differdange, l'habillage et les textes destinés à une Ville restent dans `~/sitraka-communes`.
Depuis le 2/11/2026 (soir), l'outil 3 du simulateur l'affiche (voir la section suivante).

- **Données** : le moteur ne lit AUCUN fichier. La série horaire est passée en paramètre :
  `serie = { t2m_dixiemes[8760] (°C × 10), pv_w_par_kwc[8760] (W par kWc, plan sud 35°) }`. Celle du
  site est `data/annee_type.json` (publiée, 55 Ko) : PVGIS 5.3 seriescalc, Luxembourg-Ville (même
  point que `data/pvgis.json`), SARAH3 + ERA5, année 2017 = la plus proche de la moyenne 2005-2023 à
  la fois en production (1 038 contre 1 049 kWh/kWc) et en degrés-jours base 15 (2 158 contre 2 167),
  heure d'hiver toute l'année. Régénérer à la main, rarement : `/usr/bin/python3 scripts/fetch_annee_type.py`.
- **Barèmes** (`scripts/baremes.json`, régénérés dans `BAREMES` APRÈS les clés PV, qui ne changent pas) :
  - `klimabonus_pac` → `bar.klimabonusPAC` : maison unifamiliale, 10 000 € (12 000 € majoré)
    si une chaudière fossile ou un chauffage électrique direct est remplacé, 6 000 € (8 000 €) sinon ;
    majoration si commande du 1/1/2026 au 30/6/2027 et facture au plus tard le 31/12/2028 ; cuve à
    mazout 1 500 € ; zone de protection d'eau 2 000 € (mazout) ; distribution 50 % au plus 2 000 € ;
    ballon tampon ≥ 30 L/kWth sauf PAC à modulation ; COP ≥ 3,1 (A7/W35). guichet.lu, page du
    11/08/2026, relue le 2/11/2026.
  - `prix_mazout` (1,601 €/L TTC, prix maximum depuis le 27/10/2026, petrol.lu, relu le 2/11/2026),
    `prix_gaz` (ILR : 9,14 c€/kWh en 2025 ; 0,095 retenu = hypothèse), `prix_electricite` (0,20 achat,
    0,07 surplus, hausses 3 et 1 %/an : hypothèses de l'outil, `source: null`) → `bar.energie`
    `{mazoutL, gaz, achat, surplus, hausseFossile, hausseElec}`.
  - `co2_combustibles` (ADEME Base Carbone v23.9 via la Banque de France, 02/07/2026 : gaz
    0,2154 kgCO2e/kWh **PCS**, unité des factures, donc sans conversion ; fioul 0,3247 kgCO2e/kWh PCI),
    `co2_electricite` (Electricity Maps 2025 : 0,2122 consommé au Luxembourg, imports compris)
    → `bar.co2 {gaz, mazout, elec}`.
  - `cop_pac` → `bar.cop {a 6.08, b −0.09, c 0.0005, dTmin 10, f 0.85}` (Ruhnau et al., Scientific
    Data 6, 189, 2019, when2heat).
  - `modele_chaleur` → `bar.chaleur` (hypothèses, `source: null`) : horizon 20 ans, rendements
    (gaz 0,85 PCS, mazout 0,80, électrique 1), 10,6 kWh/m³, 10 kWh/L, 800 kWh d'eau chaude par
    personne (au plus 40 % de la chaleur utile), base 15 °C, départ 40 − T (radiateurs) ou
    30 − 0,5 T (plancher), eau chaude 50 °C, puissance 100 % à 7 °C et −25 % pour 14 K (bornée
    60-110 %), ballon 1,163 Wh/(L·K), surchauffe 15 K, pertes 1 %/h, batterie 90 % aller-retour,
    0,5 C au plus 5 kW, profils journaliers (24 h) des usages et de l'eau chaude, besoin par époque
    (TABULA DE arrondi : 190 … 40 kWh/m²), entretien (chaudière 200, PAC 150, électrique 0 €/an),
    coût d'enlèvement de la cuve 1 500 €. `scripts/baremes.py` : `kb_pac()` (même règle que le JS).
- **API** :
  - `heatPumpCOP(ΔT, bar, f?)` ; `klimabonusPAC({commande, facture, remplacement, energie, zoneEau,
    coutDistribution}, bar)` → `{pac, majore, cuve, zone, distribution, total}` (dates ISO ; sans date
    de commande, pas de majoration) ; `minBufferLitres(kW, modulante, bar)` ;
  - `localAid([{nom, base: 'pac'|'pv'|'batterie'|'hems', taux, plafond}], {pac, pv, batterie, hems})`
    → `{lignes, parBase, total}` : taux × aide de l'État du poste, plafonné ;
  - `heatDemand(I, serie, bar)` : besoin depuis `conso` + `unite` ('m3', 'L', 'kWh'), sinon `besoin`
    (chaleur utile, kWh/an), sinon `surface` + `epoque` ; séries horaires ;
  - `simulateHourly(S, I, {pv, hp, buffer, battery, direct}, bar, keep)` → `{imp, exp, pv, self, hpEl,
    backupEl, scop, hpH, Emax}` ;
  - `computeHeat(I, serie, bar, pvgis?)` : entrées décrites dans le commentaire de la fonction
    (mêmes noms que `compute` pour le PV : `p, cost, batt, bcost, hems, hcost, haid, inv, price,
    market, growth, disc` ; chauffage : `energie, conso, unite | besoin | surface, epoque, rendement,
    occupants, emetteurs, elecBase, pac, pacCost, ballon, ballonCost, surchauffe, copF,
    coutDistribution, coutCuve, chaudiereEvitee, commande, facture, remplacement, zoneEau,
    aidesLocales, prixGaz, prixMazout, hausseFossile, horizon, co2Gaz, co2Mazout, co2Elec`). Avec
    `pvgis` et `canton` (+ `az`, `tilt`), la série PV est remise à l'échelle de `yieldPerKwc`.
    Renvoie `{S, sc: {A, B, C, D}, D0, ballon, horizon, fuelPrice, energie, aides}` ; A = situation
    actuelle, B = panneaux (+ batterie), C = PAC seule, D = panneaux + PAC + ballon (+ batterie, HEMS),
    D0 = D sans ballon. Par scénario : investissement, aides État / locale, reste à payer, facture de
    la 1re année, CO2 (t/an) et baisse vs A, dépense cumulée `cum`, flux de l'écart avec A `cf`,
    `pb` (retour sur investissement, `payback`), `gain` (`netGain`, actualisé si `disc` > 0), `irr`.
  - Réutilise `bonusPV`, `bonusBattery`, `hemsAid`, `yieldPerKwc`, `cumulative`, `payback`,
    `netGain`, `irr` SANS les modifier : les 10 références PV restent identiques.
- **Ballon tampon, argument faible assumé** : cas type, 300 L chargés 15 K plus chaud = 5,2 kWh ;
  part autoconsommée 31 % → 38 %, soit ≈ 88 € d'achats évités par an (`ballon.gainAchat`), ≈ 48 €
  net du surplus qui n'est plus vendu (`ballon.gainNet`), pour 1 800 € : il ne se rembourse pas seul.
  Le Klimabonus ne l'exige d'ailleurs pas pour une PAC à modulation.
- **Cas type gaz** (maison de 140 m² des années 1980, 2 000 m³/an, 8 kWc à 1 800 €/kWc, PAC 9 kW à
  22 000 €, ballon 300 L à 1 800 €, HEMS 1 000 € aidé 500 €, commande le 15/11/2026) : sans aide
  locale, D se rembourse en **≈ 9,4 ans**, CO2 **−73 %** (série de Luxembourg-Ville, −73,1 %). Avec
  l'aide locale FICTIVE des tests (30 % de l'aide de l'État sur la PAC plafonnés à 2 000 €, 20 % sur
  les panneaux plafonnés à 1 000 €) : ≈ 8,1 ans. Aucun barème communal réel ici : le contrôle de
  concordance avec le calcul de référence privé (à 1e-10 près, 7 variantes) est dans
  `~/sitraka-communes/tests/moteur.test.mjs`. Facteur gaz retenu : 0,2154 kgCO2e par kWh PCS (Base
  Carbone v23.9), et non 0,227 par kWh PCI × 0,9 = 0,204 par kWh PCS (ce qui donnerait −72 %).
- **Limites** : une seule année météo, pas de dégradation des panneaux ni de remplacement de la
  batterie dans ce volet, factures non actualisées (seul `gain` l'est avec `disc`), maison
  unifamiliale seulement pour le Klimabonus PAC, abonnement gaz supprimé non compté.
- **Tests** : `node --test tests/sim-engine.test.mjs` (32 tests, dont 12 « chauffage ») ;
  `tests/test_baremes.py` : structure, sources datées, valeurs et `kb_pac` comparé au moteur JS.
- **Effet de bord** : l'objet `BAR` inliné dans les 4 pages du simulateur PV contient aussi ces
  barèmes (≈ 1,6 Ko de plus) ; le simulateur PV ne les lit pas.

## Simulateur : outil 3 « Chauffage : pompe à chaleur et ballon tampon » (2/11/2026)

- **Place** : section `#chauffage` APRÈS « Repères » et avant la FAQ, pour garder la numérotation dans l'ordre
  (Tableau 5, Figure 3, Tableau 6 après les tableaux 1 à 4). En-tête : « trois outils », phrase « Outil 3 » ajoutée.
- **Données** : `fetch('/data/annee_type.json')` au chargement (55 Ko) ; tant qu'elle manque, `#h-status`
  (role=status) et résultats cachés ; message d'erreur si le chargement échoue. Lien de téléchargement dans
  « Partager, citer, télécharger » et dans les sources (donc dans `functions/_allow.js`).
- **Branchement** : `renderHeat(R, npvq)` appelé à la fin de `render()` ; `E.computeHeat(…, SERIE, BAR, G)` avec
  la série PV remise à l'échelle du canton, de l'orientation et de l'inclinaison de l'outil 1. Case `hpv`
  (« Avec le photovoltaïque ci-dessus », cochée) : reprend p, cost, batt, bcost, hems, hcost, haid, inv des
  outils 1-2 (option A, Klimabonus) ; décochée, seuls A et C sont affichés. Prix de l'électricité achetée et
  vendue, hausse de l'électricité et actualisation = ceux de l'outil 2 (surplus 0,05 par défaut, pas le 0,07 du
  moteur). `remplacement` toujours vrai (l'outil part d'un chauffage existant à remplacer), `aidesLocales: []`.
  Date de commande : select `hmaj` (1 = majorée, `commande = majoreCommandeA`).
- **URL** : `hids` (20 champs) toujours écrits ; cases `hmod`, `hbufon`, `hpv` (défaut 1) et `hzone` (défaut 0)
  écrites seulement si elles diffèrent du défaut. Changer d'énergie remet la consommation et le rendement par
  défaut (gaz 2 000 m³, mazout 2 000 L, électrique 15 000 kWh ; 85/80/100 %).
- **Aucune aide communale** : une phrase renvoie à « Pour les communes » (`__FORPATH__`, lien hors clé de
  dictionnaire car le jeton est substitué avant la traduction). Diff Primes et habillage Differdange restent
  dans `~/sitraka-communes`.
- **Chiffres** : jetons `heat_numbers()` (build.py, depuis baremes.json) : `__KBPAC_*__`, `__MAZOUT_L__`,
  `__GAZ_ILR__`, `__GAZ_RET__`, `__ELEC_ACHAT__`, `__CO2_*__`, `__COP_*__`, `__HORIZON_H__`. `check_page` contrôle
  en plus les paires « 10 000 € (12 000 € pour une commande » / « 6 000 € (8 000 € … » (4 langues) et « 30 L par
  kW » (motifs obligatoires `pac_montant`, `pac_ballon`). Écrits à la main (hypothèses de l'outil ou sources
  datées non lues dans baremes.json) : fourchettes de prix PAC (Renov.lu 10/2026, 32 300 € L'essentiel
  9/6/2026), ballon 1 000-3 500 € (Reduco 2026), valeurs du paragraphe « Calcul de l'outil 3 » (modele_chaleur),
  dates de la majoration (1/1/2026-30/6/2027, facture 31/12/2028).
- **FAQ** : 3 questions (montant Klimabonus PAC, rentabilité, ballon tampon), reprises dans le JSON-LD FAQPage.
- **Vérifié** (Chrome sans tête, 2/11/2026) : 4 langues × mazout / gaz / électrique direct × 1 280 et 375 px :
  aucune erreur JS (hors balise Cloudflare en local), aucun défilement horizontal de page (le tableau 5 défile
  dans son bloc sur mobile), URL partagée = même résultat, aucun texte français resté en EN/DE/LB.
