# Lux-Solaire ☀️

**Tableau de bord du photovoltaïque au Luxembourg** — une réutilisation des
données ouvertes de [Leneda](https://leneda.eu) publiées sur
[data.public.lu](https://data.public.lu/fr/datasets/la-production-denergie-electrique-au-luxembourg/).

🌐 **Live** : [solaire.sitraka.lu](https://solaire.sitraka.lu) ·
💻 **Code** : [github.com/Sitraka17/lux-solaire](https://github.com/Sitraka17/lux-solaire)

Le portail Open data luxembourgeois posait la question : *« Quelle est la part
du photovoltaïque dans la production électrique par commune ? »* — ce tableau
de bord y répond, commune par commune.

## Ce que montre le dashboard

- **Trajectoire nationale** : capacité installée par filière (PV, éolien,
  biomasse, cogénération, hydro, biogaz), du T1 2025 au relevé hebdomadaire courant
- **Mix des filières** et part du PV dans le parc décentralisé
- **Classements communaux** : capacité PV et croissance sur 15 mois
- **Le paradoxe résidentiel** : 96 % des installations font ≤ 30 kW mais ne
  représentent que 54 % de la capacité
- **Table interactive** des 100 communes (tri + filtre)

## Données

| Source | Licence | Mise à jour |
|---|---|---|
| [La production d'énergie électrique au Luxembourg](https://data.public.lu/fr/datasets/la-production-denergie-electrique-au-luxembourg/) (Leneda) | CC0 | trimestrielle + hebdomadaire |

⚠️ Les chiffres décrivent la **capacité installée** (kW raccordés), pas
l'énergie produite (kWh).

## Architecture

Une seule page statique, zéro dépendance front (SVG + JS vanille, données
inlinées). Reconstruire avec les dernières données :

```bash
pip install pandas requests pillow
python3 scripts/build.py   # régénère data/, index.html, fr/, lb/, og*.png, sitemap.xml
```

Le build s'arrête (exit 1) si un garde-fou échoue : clé i18n morte ou non
traduite, jeton `__XXX__` oublié, tiret cadratin, encadré dérivé qui ne
correspond plus aux données. `LUX_SOLAIRE_CACHE=1` met les téléchargements en
cache dans `.cache/` pour itérer sur le gabarit.

Une GitHub Action (`.github/workflows/rebuild.yml`) reconstruit le lundi à
06:00 UTC, après le dépôt hebdomadaire de Leneda, et ne commite que si
`data/data.json` a changé. Le déploiement reste manuel, depuis la racine du
repo : `vercel deploy --prod --yes`.

## Crédits

Analyse & visualisation : Sitraka Forler · juillet 2026 ·
données CC0 Leneda / data.public.lu
