"""Contrôle du format Leneda : colonnes attendues et nombre de communes, avec un message clair."""
import pandas as pd
import pytest

import build


def _commune_frame(n=100):
    d = {"LAU2": range(1, n + 1), "Commune": [f"C{i}" for i in range(n)], "Canton": ["K"] * n}
    for c in build.COMMUNE_COLS[3:]:
        d[c] = [1.0] * n
    return pd.DataFrame(d)


def _ng(root):
    f = sorted((root / "archive").glob("leneda-not-grouped-*.csv.gz"))[-1]
    return pd.read_csv(f)


def test_format_attendu_passe(root):
    build.check_leneda({"2025 T1": _commune_frame(), "2 nov. 2026": _commune_frame()}, _ng(root))


def test_colonne_absente(root):
    f = _commune_frame().drop(columns=[build.PV + " Performance [kW]"])
    with pytest.raises(SystemExit, match="colonnes absentes"):
        build.check_leneda({"2 nov. 2026": f}, _ng(root))


def test_colonne_renommee_par_installation(root):
    ng = _ng(root).rename(columns={"Puissance installée [kW]": "Puissance [kW]"})
    with pytest.raises(SystemExit, match="Puissance installée"):
        build.check_leneda({"2 nov. 2026": _commune_frame()}, ng)


def test_nombre_de_communes(root):
    with pytest.raises(SystemExit, match="au lieu de 100"):
        build.check_leneda({"2 nov. 2026": _commune_frame(99)}, _ng(root))
    with pytest.raises(SystemExit, match="environ 100"):
        build.check_leneda({"2021 T1": _commune_frame(80), "2 nov. 2026": _commune_frame()}, _ng(root))


def test_type_inconnu(root):
    ng = _ng(root).copy()
    ng.loc[0, "Type d'installation"] = "Fusion froide"
    with pytest.raises(SystemExit, match="inconnus"):
        build.check_leneda({"2 nov. 2026": _commune_frame()}, ng)
