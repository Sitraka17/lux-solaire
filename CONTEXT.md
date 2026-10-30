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
