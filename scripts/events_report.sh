#!/bin/sh
# Rapport du compteur d'événements anonyme (D1 lux-solaire-events), 30 derniers jours par défaut.
DAYS=${1:-30}
q() {
  echo "== $1"
  npx --yes wrangler@3 d1 execute lux-solaire-events --remote --json --command "$2" 2>/dev/null |
    /usr/bin/python3 -c "import json,sys
r=json.load(sys.stdin)[0]['results']
print('  (aucun)' if not r else '\n'.join('  '+' | '.join(str(v) for v in x.values()) for x in r))"
}
W="day >= date('now','-$DAYS day')"
q "Totaux par type ($DAYS j)" "SELECT type, SUM(n) AS n FROM ev WHERE $W GROUP BY type ORDER BY n DESC"
q "Téléchargements" "SELECT target, SUM(n) AS n FROM ev WHERE type='dl' AND $W GROUP BY target ORDER BY n DESC"
q "Communes consultées (sélecteur et clics vers les pages communales)" "SELECT target, SUM(n) AS n FROM ev WHERE type IN ('commune','page') AND $W GROUP BY target ORDER BY n DESC LIMIT 25"
q "Arrivées depuis un autre site (page, site d'origine)" "SELECT page, ref, SUM(n) AS n FROM ev WHERE type='land' AND $W GROUP BY page, ref ORDER BY n DESC LIMIT 25"
q "Clics vers le contact" "SELECT day, page, SUM(n) AS n FROM ev WHERE type='contact' AND $W GROUP BY day, page ORDER BY day DESC"
