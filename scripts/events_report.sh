#!/bin/sh
# Rapport du compteur d'événements anonyme (D1 lux-solaire-events), 30 derniers jours par défaut.
DAYS=${1:-30}
q() { npx --yes wrangler@3 d1 execute lux-solaire-events --remote --command "$1" 2>/dev/null | sed -n '/┌/,/┘/p'; }
echo "== Totaux par type ($DAYS j)"
q "SELECT type, SUM(n) AS n FROM ev WHERE day >= date('now','-$DAYS day') GROUP BY type ORDER BY n DESC"
echo "== Téléchargements"
q "SELECT target, SUM(n) AS n FROM ev WHERE type='dl' AND day >= date('now','-$DAYS day') GROUP BY target ORDER BY n DESC"
echo "== Communes consultées (sélecteur et clics vers les pages communales)"
q "SELECT target, SUM(n) AS n FROM ev WHERE type IN ('commune','page') AND day >= date('now','-$DAYS day') GROUP BY target ORDER BY n DESC LIMIT 25"
echo "== Pages communales d'arrivée et sites d'origine"
q "SELECT page, ref, SUM(n) AS n FROM ev WHERE type='land' AND day >= date('now','-$DAYS day') GROUP BY page, ref ORDER BY n DESC LIMIT 25"
echo "== Contacts"
q "SELECT day, page, SUM(n) AS n FROM ev WHERE type='contact' AND day >= date('now','-$DAYS day') GROUP BY day, page ORDER BY day DESC"
