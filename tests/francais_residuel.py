"""Détecteur de français résiduel dans une page rendue en portugais (tests/test_portugais*.py).

Texte visible, attributs lisibles, champs textuels du JSON-LD et littéraux JS (hors
commentaires) ; les URL, les noms officiels des communes et des cantons (non traduits)
et les titres de sources citées en français, signalés « em francês », sont retirés avant
la recherche. « ou », « que », « de », « a » existent en portugais et ne sont pas cherchés."""
import html
import re

FR_WORDS = ["les", "des", "du", "et(?! al\\.)", "pour", "avec", "sur", "dans", "une", "est", "au", "aux", "votre",
            "vos", "sans", "année", "ans", "chauffage", "panneaux", "toit", "coût", "prix", "sont", "qui", "pas",
            "plus", "chez", "kWc", "MWc", "Option", "Simulateur", "Tableau", "Outil", "commune", "communes",
            "relevé", "relevés", "puissance", "capacité", "filière", "habitants", "Télécharger", "Partager",
            "Copier", "données", "installations", "photovoltaïque", "Aller", "contenu", "Sources", "Méthode"]


def visible_text(page, names=()):
    body = re.sub(r"<style\b.*?</style>", " ", page, flags=re.S)
    body = re.sub(r'<script type="application/ld\+json">(.*?)</script>',
                  lambda m: " ".join(re.findall(r'"(?:name|text|description|headline|keywords|variableMeasured)": ?"((?:[^"\\]|\\.)*)"',
                                                m.group(1))),
                  body, flags=re.S)
    # blobs de données injectés (const D = {…}; const G = {…};) : libellés-données Leneda bruts,
    # identiques dans toutes les langues (« Installation photovoltaïque »), hors contrôle
    body = re.sub(r"const [DG] = \{.*?\};\n", "\n", body, flags=re.S)
    body = re.sub(r"<script\b[^>]*>(.*?)</script>",
                  lambda m: " ".join(x for x in re.findall(r"'((?:[^'\\\n]|\\.)*)'",
                                                           re.sub(r"//[^\n]*|/\*.*?\*/", "", m.group(1), flags=re.S))
                                     if not re.fullmatch(r"[a-z][a-z0-9_-]*", x)),   # identifiants (événements, classes)
                  body, flags=re.S)
    # passages explicitement marqués dans une autre langue (lang="fr", lang="lb"…) : hors contrôle
    body = re.sub(r'<(?!html\b)(\w+)[^>]*\blang="(?!pt)[a-z-]+"[^>]*>.*?</\1>', " ", body, flags=re.S)
    attrs = " ".join(re.findall(r'(?:aria-label|title|placeholder|alt|content|data-l-[a-z-]+)="([^"]*)"', body))
    txt = html.unescape(re.sub(r"<[^>]+>", " ", body) + " " + attrs)
    txt = re.sub(r"https?://\S+|\b[\w.-]+\.(?:lu|eu|pdf|csv|json)\b", " ", txt)
    for n in sorted(names, key=len, reverse=True):   # noms officiels (Esch-sur-Alzette, Lac de la Haute-Sûre…)
        txt = txt.replace(n, " ")
    return txt


def french_words(page, names=()):
    txt = visible_text(page, names)
    return [(w, txt[max(0, m.start() - 50):m.end() + 50]) for w in FR_WORDS
            for m in re.finditer(r"(?<![\wÀ-ÿ])" + w + r"(?![\wÀ-ÿ])", txt)]
