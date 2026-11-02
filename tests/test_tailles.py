"""Classes de taille (bornes fermées à droite, include_lowest) : une installation à 0 kW est
comptée dans la première classe, 30 kW tombe dans « 15–30 » (« 30 kW ou moins »)."""
import pandas as pd

import build


def _inst(ps):
    return pd.DataFrame({"LAU2": [101] * len(ps), "p": ps})


def test_zero_kw_compte():
    nat, per = build._grid(_inst([0.0, 0.0, 3.0]), build.BIN_EDGES, build.BIN_LABELS)
    assert nat[0][0] == 3 and sum(n for n, _ in nat) == 3
    assert per[101][0][0] == 3


def test_bornes_fermees_a_droite():
    ps = [0, 5, 5.01, 15, 30, 30.01, 100, 500, 1000, 5000, 5000.1, 90000]
    nat, _ = build._grid(_inst(ps), build.BIN_EDGES, build.BIN_LABELS)
    counts = dict(zip(build.BIN_LABELS, (n for n, _ in nat)))
    assert sum(counts.values()) == len(ps)
    assert counts["0–5"] == 2 and counts["5–10"] == 1 and counts["10–15"] == 1 and counts["15–30"] == 1
    assert counts["30–100"] == 2 and counts["100–500"] == 1 and counts["0,5–1 MW"] == 1
    assert counts["1–5 MW"] == 1 and counts[">5 MW"] == 2


def test_tranches_aides_avec_zero():
    nat, _ = build._grid(_inst([0, 30, 30.5, 200, 500, 5000, 6000]), build.KB_EDGES, build.KB_LABELS)
    assert [n for n, _ in nat] == [2, 2, 1, 1, 1]


def test_archive_reelle_tout_compte(root):
    f = sorted((root / "archive").glob("leneda-not-grouped-*.csv.gz"))[-1]
    pv = build._pv_rows(pd.read_csv(f))
    nat, _ = build._grid(pv, build.BIN_EDGES, build.BIN_LABELS)
    assert sum(n for n, _ in nat) == len(pv)
