"""Barèmes du site : chargement de scripts/baremes.json (source UNIQUE) et usages.

- `engine_bar()` : l'objet de barèmes au format de sim-engine.js (BAREMES) ;
- `engine_js()` / `sync_engine()` : régénère le bloc BAREMES de sim-engine.js ;
- `kb_pv()`, `kb_batt()`, `tarif()`, `kb_pac()` : mêmes formules que le moteur JS (FAQ du simulateur, tests) ;
- `kb_edges()`, `kb_labels()` : tranches du Klimabonus Gemengen (graphiques, CSV, pages communales) ;
- `check_page()` / `check_pages()` : contrôle des chiffres de barème cités dans les pages rendues (phrases
  traduites restées dans les dictionnaires) : le build échoue si l'un d'eux ne correspond
  plus à baremes.json.
"""
import html as html_mod
import json
import re
from pathlib import Path

PATH = Path(__file__).resolve().parent / "baremes.json"
_REQUIRED = ("valeur", "source", "date_source", "date_verification")
_ENTRIES = ("klimabonus_pv", "klimabonus_batterie", "aide_hems", "tarif_injection",
            "klimabonus_gemengen", "klimabonus_pac", "prix_mazout", "prix_gaz", "prix_electricite",
            "co2_combustibles", "co2_electricite", "cop_pac", "modele_chaleur", "modele")


def load(path=PATH):
    b = json.loads(Path(path).read_text())
    missing = [f"{e}.{k}" for e in _ENTRIES for k in _REQUIRED if k not in b.get(e, {})]
    if missing:
        raise SystemExit(f"baremes.json : champs manquants {missing}")
    return b


B = load()


def engine_bar(b=None):
    """Objet de barèmes du moteur (mêmes clés et même ordre que l'ancien BAREMES)."""
    b = b or B
    tar = {k: v for k, v in b["tarif_injection"]["valeur"].items() if k != "plafondKw"}
    m = b["modele"]["valeur"]
    return {
        "version": b["version"],
        "sources": b["sources_moteur"],
        "klimabonusPV": dict(b["klimabonus_pv"]["valeur"]),
        "klimabonusBatt": dict(b["klimabonus_batterie"]["valeur"]),
        "hems": dict(b["aide_hems"]["valeur"]),
        "tarif": tar,
        "horizon": m["horizon"],
        "anneeOnduleur": m["anneeOnduleur"],
        "autoconso": dict(m["autoconso"]),
        # volet chauffage (2/11/2026) : ajouté APRÈS les clés du photovoltaïque, sans les modifier
        "klimabonusPAC": dict(b["klimabonus_pac"]["valeur"]),
        "energie": {"mazoutL": b["prix_mazout"]["valeur"]["eurParL"], "gaz": b["prix_gaz"]["valeur"]["retenu"],
                    **{k: v for k, v in b["prix_electricite"]["valeur"].items()}},
        "co2": {"gaz": b["co2_combustibles"]["valeur"]["gazPCS"], "mazout": b["co2_combustibles"]["valeur"]["mazoutPCI"],
                "elec": b["co2_electricite"]["valeur"]["reseau"]},
        "cop": dict(b["cop_pac"]["valeur"]),
        "chaleur": dict(b["modele_chaleur"]["valeur"]),
    }


_JS_BEGIN = "  /* BAREMES:DEBUT"
_JS_END = "  /* BAREMES:FIN */"


def engine_js(b=None):
    """Bloc `var BAREMES = Object.freeze({...});` de sim-engine.js, marqueurs compris."""
    eb = engine_bar(b)
    out = [_JS_BEGIN + " : bloc régénéré par scripts/build.py depuis scripts/baremes.json, "
           "ne pas éditer à la main. anneeOnduleur = indice d'année (0 = première année). */",
           "  var BAREMES = Object.freeze({"]
    for k, v in eb.items():
        if isinstance(v, dict):
            body = ", ".join(f"{kk}: {json.dumps(vv, ensure_ascii=False)}" for kk, vv in v.items())
            out.append(f"    {k}: Object.freeze({{ {body} }}),")
        else:
            out.append(f"    {k}: {json.dumps(v, ensure_ascii=False)},")
    out += ["  });", _JS_END]
    return "\n".join(out)


def sync_engine(path, b=None):
    """Réécrit le bloc BAREMES de sim-engine.js s'il diffère de baremes.json. Renvoie le texte."""
    path = Path(path)
    src = path.read_text()
    i, j = src.find(_JS_BEGIN), src.find(_JS_END)
    if i < 0 or j < 0 or j < i:
        raise SystemExit(f"{path.name} : marqueurs BAREMES:DEBUT / BAREMES:FIN introuvables")
    new = src[:i] + engine_js(b) + src[j + len(_JS_END):]
    if new != src:
        path.write_text(new)
        print(f"{path.name} : bloc BAREMES régénéré depuis baremes.json")
    return new


# ---- formules (identiques à sim-engine.js) ----
def kb_pv(p, b=None):
    k = (b or B)["klimabonus_pv"]["valeur"]
    return 0 if p < k["pMin"] else (p * (k["a"] - k["a"] / k["b"] * p) if p < k["pCap"] else k["max"])


def kb_batt(q, b=None):
    k = (b or B)["klimabonus_batterie"]["valeur"]
    return 0 if q < k["qMin"] else (q * (k["a"] - k["a"] / k["b"] * q) if q < k["qCap"] else k["max"])


def kb_pac(commande, facture=None, remplacement=True, mazout=False, zone_eau=False, cout_dist=0, b=None):
    """Klimabonus PAC air-eau (maison unifamiliale), mêmes règles que klimabonusPAC() de sim-engine.js.
    commande, facture : dates ISO « AAAA-MM-JJ » (facture facultative)."""
    k = (b or B)["klimabonus_pac"]["valeur"]
    maj = bool(commande) and k["majoreCommandeDe"] <= commande <= k["majoreCommandeA"] and \
        (not facture or facture <= k["majoreFactureA"])
    pac = (k["remplacementMajore"] if maj else k["remplacement"]) if remplacement else \
        (k["sansRemplacementMajore"] if maj else k["sansRemplacement"])
    return pac + (k["cuveMazout"] if mazout and remplacement else 0) + (k["zoneEau"] if mazout and zone_eau else 0) \
        + min(k["distMax"], k["distTaux"] * max(0, cout_dist))


def tarif(p, n, b=None):
    """€/kWh pour une puissance p (kW) et une année n de première injection."""
    k = (b or B)["tarif_injection"]["valeur"]
    return (k["petit"] if p <= k["seuilKw"] else k["grand"]) * k["baisse"] ** (n - k["anneeBase"]) / 1000


# ---- Klimabonus Gemengen ----
def gemengen(b=None):
    return (b or B)["klimabonus_gemengen"]["valeur"]


def kb_edges(b=None):
    """[0, 30, 200, 500, 5000, None] : bornes en kW des tranches (classes fermées à droite)."""
    t = gemengen(b)["tranches"]
    for x, y in zip(t, t[1:]):
        if x["aKwc"] != y["deKwc"]:
            raise SystemExit("baremes.json : tranches Gemengen non contiguës")
    return [0] + [x["deKwc"] for x in t] + [t[-1]["aKwc"], None]


def _mw(x):
    return f"{x / 1000:g}".replace(".", ",")


def kb_labels(b=None):
    """Libellés-données des tranches (FR, traduits ensuite) : « 0–30 », …, « 0,5–5 MW », « > 5 MW »."""
    e = kb_edges(b)
    out = []
    for lo, hi in zip(e, e[1:]):
        if hi is None:
            out.append(f"> {_mw(lo)} MW")
        elif hi >= 1000:
            out.append(f"{_mw(lo)}–{_mw(hi)} MW")
        else:
            out.append(f"{lo}–{hi}")
    return out


# ──────────────── contrôle des chiffres cités dans les phrases ───────────────
_N = r"(\d{1,3}(?:[   .,]\d{3})+(?![\d])|\d+(?:[.,]\d+)?)"
_CUR_L = r"(?:€\s?)?"
_CUR_R = r"(?:\s?(?:€|euros?|Euro))?"


def _num(s, lang):
    s = s.replace(" ", " ").replace(" ", " ")
    if re.fullmatch(r"\d{1,3}(?:[ .,]\d{3})+", s) and not (lang != "en" and re.fullmatch(r"\d{1,3},\d{3}", s)):
        return float(re.sub(r"[ .,]", "", s))
    return float(s.replace(",", "."))


def _text(html):
    t = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"[ \t]+", " ", html_mod.unescape(t))


def _eq(x, y, tol=0.005):
    return abs(x - y) <= tol


def check_page(html, lang, kind, b=None):
    """Problèmes (liste de chaînes) d'une page rendue. kind : 'sim', 'dash' ou 'commune'.
    Chaque motif reconnu doit porter la valeur de baremes.json ; certains motifs sont
    obligatoires (au moins une occurrence) pour que le contrôle ne devienne pas muet
    si une phrase est reformulée."""
    b = b or B
    pv, bt = b["klimabonus_pv"]["valeur"], b["klimabonus_batterie"]["valeur"]
    hm, tr, gm = b["aide_hems"]["valeur"], b["tarif_injection"]["valeur"], gemengen(b)
    t = _text(html)
    probs, seen = [], set()
    n = lambda s: _num(s, lang)

    def bad(what, m, exp):
        probs.append(f"{what} : « {m.group(0).strip()} » ne correspond pas à baremes.json ({exp})")

    if kind == "sim":
        for m in re.finditer(r"P × \(" + _N + r" − " + _N + r" × P\)", t):
            seen.add("pv_formule")
            if not (_eq(n(m.group(1)), pv["a"]) and _eq(n(m.group(2)), round(pv["a"] / pv["b"], 2), 0.5)):
                bad("Klimabonus PV", m, f"a = {pv['a']}, a/b = {pv['a'] / pv['b']:g}")
        for m in re.finditer(r"Q × \(" + _N + r" − " + _N + r"/" + _N + r" × Q\)", t):
            seen.add("batt_formule")
            if not (_eq(n(m.group(1)), bt["a"]) and _eq(n(m.group(2)), bt["a"]) and _eq(n(m.group(3)), bt["b"])):
                bad("Klimabonus batterie", m, f"a = {bt['a']}, b = {bt['b']}")
        for m in re.finditer(_CUR_L + _N + _CUR_R + r" (?:à partir de|a partir de|from|ab) " + _N + r" (kWc|kWp|kWh)\b", t):
            amount, thr = n(m.group(1)), n(m.group(2))
            if m.group(3) == "kWh":
                seen.add("batt_max")
                if not (_eq(amount, bt["max"]) and _eq(thr, bt["qCap"])):
                    bad("plafond batterie", m, f"{bt['max']} € à partir de {bt['qCap']} kWh")
            else:
                seen.add("pv_max")
                if not (_eq(amount, pv["max"]) and _eq(thr, pv["pCap"])):
                    bad("plafond Klimabonus PV", m, f"{pv['max']} € à partir de {pv['pCap']} kWc")
        for m in re.finditer(_N + r" × " + _N + r"\s?n\s?[−-]\s?(\d{4})", t):
            seen.add("tarif")
            v = n(m.group(1))
            seen.add("tarif_petit" if _eq(v, tr["petit"]) else "tarif_grand" if _eq(v, tr["grand"]) else "tarif_x")
            if not ((_eq(v, tr["petit"]) or _eq(v, tr["grand"])) and _eq(n(m.group(2)), tr["baisse"], 1e-9)
                    and int(m.group(3)) == tr["anneeBase"]):
                bad("tarif d'injection", m, f"{tr['petit']} ou {tr['grand']} × {tr['baisse']}^(n−{tr['anneeBase']})")
        for m in re.finditer(r"n\s?[−-]\s?\d{4} ?€/MWh (?:jusqu'à|up to|bis|até) " + _N + r" kW", t):
            seen.add("tarif_seuil")
            if not _eq(n(m.group(1)), tr["seuilKw"]):
                bad("seuil du tarif d'injection", m, f"{tr['seuilKw']} kW")
        # (?!\)\d) : le libellé « Klimabonus (panneaux, batterie, HEMS) » suivi du montant
        # pré-rendu de l'option A (« HEMS)5 742 € » une fois les balises retirées) n'est pas une aide HEMS
        for m in re.finditer(r"HEMS(?!\)\d)[^.;]{0,220}?" + r"(?:€\s?" + _N + r"(?![\d])|" + _N + r"\s?€)", t):
            seen.add("hems")
            v = n(m.group(1) or m.group(2))
            if not _eq(v, hm["aideMax"]):
                bad("aide HEMS", m, f"{hm['aideMax']} €")
        # outil 3 (pompe à chaleur, 2/11/2026) : montants du Klimabonus PAC et ballon tampon exigé
        kp = b["klimabonus_pac"]["valeur"]
        pairs = {(kp["remplacement"], kp["remplacementMajore"]), (kp["sansRemplacement"], kp["sansRemplacementMajore"])}
        for m in re.finditer(_CUR_L + _N + _CUR_R + r" \(" + _CUR_L + _N + _CUR_R +
                             r" (?:pour une commande|for an order|bei Bestellung|bei enger Bestellung|para uma encomenda)", t):
            seen.add("pac_montant")
            if (n(m.group(1)), n(m.group(2))) not in pairs:
                bad("Klimabonus pompe à chaleur", m, f"{sorted(pairs)}")
        for m in re.finditer(_N + r" L (?:par|per|pro|por) kW", t):
            seen.add("pac_ballon")
            if not _eq(n(m.group(1)), kp["ballonLParKw"]):
                bad("ballon tampon exigé", m, f"{kp['ballonLParKw']} L par kW thermique")
        need = ["pv_formule", "batt_formule", "pv_max", "batt_max", "tarif_petit", "tarif_grand", "tarif_seuil", "hems",
                "pac_montant", "pac_ballon"]
    else:
        tranches = {(x["taux"], x["plafond"]) for x in gm["tranches"]}
        full = {(x["taux"], x["deKwc"], x["aKwc"], x["plafond"]) for x in gm["tranches"]}
        omb = (gm["ombriere"]["taux"], gm["ombriere"]["plafond"])
        for m in re.finditer(_N + r"\s?% (?:des coûts |of costs |der Kosten |vun de Käschten )?"
                             r"(?:entre|between|zwischen|tëscht) " + _N + r" (?:et|and|und|an|a) " + _N +
                             r" (kWc|kWp|MWc|MWp) \((?:plafond |cap |Obergrenze |Plafong |max\. )?"
                             + _CUR_L + _N + r"\s?€?/kW[cp]\)", t):
            seen.add("gem_tranche")
            f = 1000 if m.group(4).startswith("M") else 1
            key = (n(m.group(1)), n(m.group(2)) * f, n(m.group(3)) * f, n(m.group(5)))
            if key not in full:
                bad("Klimabonus Gemengen", m, "tranches " + ", ".join(
                    f"{x['taux']} % de {x['deKwc']} à {x['aKwc']} kWc ≤ {x['plafond']} €/kWc" for x in gm["tranches"]))
            else:
                seen.add(("gem", key))
        for m in re.finditer(_N + r"\s?% \((?:plafond |cap |Obergrenze |Plafong |max\. )?" + _CUR_L + _N + r"\s?€?/kW[cp]\)", t):
            seen.add("gem_taux")
            if (n(m.group(1)), n(m.group(2))) not in tranches | {omb}:
                bad("taux et plafond Gemengen", m, f"{sorted(tranches)} ou ombrière {omb}")
        for m in re.finditer(r"(?:ombrière|canopy|Parkplatzüberdachung|Parkplazendaach)[^.]{0,40}?" + _N +
                             r"\s?% \(" + _CUR_L + _N + r"\s?€?/kW[cp]\)", t):
            seen.add("gem_omb")
            if (n(m.group(1)), n(m.group(2))) != omb:
                bad("ombrière Gemengen", m, f"{omb[0]} % ≤ {omb[1]} €/kWc")
        for m in re.finditer(r"(?:[Bb]arème|Bareem|Stand) (\d{4})|(\d{4}) (?:Klimabonus Gemengen )?scale", t):
            ctx = t[max(0, m.start() - 160):m.end() + 160]
            if "Gemengen" not in ctx:
                continue
            seen.add("gem_annee")
            if int(m.group(1) or m.group(2)) != gm["bareme"]:
                bad("année du barème Gemengen", m, f"barème {gm['bareme']}")
        need = []
        if kind == "dash":
            need = ["gem_tranche", "gem_omb", "gem_annee"] + [("gem", k) for k in sorted(full)]
        elif kind == "commune":
            need = ["gem_taux", "gem_annee"]
    for k in need:
        if k not in seen:
            probs.append(f"motif attendu absent : {k} (phrase reformulée ? adapter baremes.check_page)")
    return probs


def check_pages(pages, b=None):
    """pages : itérable de (nom, html, lang, kind). Renvoie la liste des problèmes."""
    out = []
    for name, html, lang, kind in pages:
        out += [f"{name} : {p}" for p in check_page(html, lang, kind, b)]
    return out
