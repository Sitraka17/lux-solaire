# CONTEXT : lux-solaire (notes internes, jamais servies : hors de la liste blanche de scripts/make_dist.py)

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
  de vérification GSC et IndexNow) et `PUBLIC_DIRS` (`data`, `fr`, `de`, `lb`, `simulator`,
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

### Ajouter un contrôle Grafana / uptime sur `meta.date_iso` (rien n'est créé à ce jour)

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
  FAIT le 2/11/2026 (voir « Workflow du lundi et alertes ») ; reste à créer le contrôle Grafana externe ;
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
- **Tests** : `node --test tests/sim-engine.test.mjs` (19 tests). `tests/fixtures/sim-reference.json`
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
- **`_jsround`** corrigé : `floor(x + 0.5)` donnait 1 pour 0.49999999999999994 (Math.round : 0).
- **`vercel.json` supprimé** (inutile sur Cloudflare Pages) : son `Cache-Control: public, max-age=3600`
  sur `/data/*` est passé dans `_headers` ; `Access-Control-Allow-Origin: *` est déjà envoyé par
  Cloudflare Pages (vérifié le 2/11/2026), donc pas répété. `.vercelignore` reste (relu par
  `scripts/make_dist.py` comme filet de sécurité : aucun de ses motifs ne doit se trouver dans le dist).
