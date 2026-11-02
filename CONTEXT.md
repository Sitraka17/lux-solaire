# CONTEXT — lux-solaire (notes internes, jamais servies : exclues par .vercelignore)

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

## Déploiement

Cloudflare Pages, projet `lux-solaire`, domaine solaire.sitraka.lu.
`npx wrangler@3 pages deploy <dist> --project-name=lux-solaire --branch=main`
(wrangler 3.x OBLIGATOIRE, 4.x convertit en Workers assets) ; `<dist>` =
copie rsync de la racine qui honore `.vercelignore` (cf.
`.github/workflows/rebuild.yml`, qui fait la même chose chaque lundi).

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
  les taux chaque janvier et mettre à jour la note dans `template.html` + les 3
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
- alerte si le relevé Leneda a plus de 10 jours (build en échec) + versions figées dans le workflow ;
- tests (slug Python/JS, arrondis, barèmes, build sur les archives) ; contrôle explicite des colonnes Leneda ;
- compteur /e : listes blanches (lang, chemins) et limite de débit ;
- `scripts/baremes.json` unique (barèmes dupliqués dans 5 endroits) ; découper build.py ;
- moteur du simulateur en module pur (`sim-engine.js`) réutilisable par communes.sitraka.lu ;
- accessibilité : contraste des barres ambre (2,1:1), `<main>` + lien d'évitement ; CSP à tester.

## Simulateur mis à jour le 2/11/2026

Sources relues le 2/11/2026 : guichet.lu Klimabonus 2026 installations techniques (mise à jour du
11/08/2026), communiqué gouvernement.lu du 16/07/2026, Klima-Agence « transition period » (17/12/2025),
ILR (loi du 22/07/2026), projet de loi 8707 (amendement gouvernemental du 21/07/2026).
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
- Bogue préexistant NON corrigé : `.fld{display:grid}` l'emporte sur l'attribut `hidden`, donc le champ
  « Coût de la batterie » (`#fld-bcost`) reste visible sans batterie.
