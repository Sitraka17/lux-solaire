"""Garde-fou de fraîcheur du relevé Leneda (build.check_freshness) : âge maximal du relevé
hebdomadaire le plus récent et écart maximal entre les fichiers « commune » et « not-grouped »."""
from datetime import date, timedelta

import pytest

import build

TODAY = date(2026, 11, 2)


@pytest.fixture(autouse=True)
def _sans_derogation(monkeypatch):
    monkeypatch.delenv("LUX_SOLAIRE_ALLOW_STALE", raising=False)


def test_releve_du_jour():
    assert build.check_freshness(TODAY, TODAY, TODAY) == (0, 0)


def test_age_limite_accepte():
    w = TODAY - timedelta(days=build.MAX_AGE_DAYS)
    assert build.check_freshness(w, w, TODAY) == (build.MAX_AGE_DAYS, 0)


def test_releve_perime_echoue():
    w = TODAY - timedelta(days=build.MAX_AGE_DAYS + 1)
    with pytest.raises(SystemExit) as e:
        build.check_freshness(w, w, TODAY)
    assert "périmé" in str(e.value) and w.isoformat() in str(e.value)


def test_derogation_locale(monkeypatch, capsys):
    monkeypatch.setenv("LUX_SOLAIRE_ALLOW_STALE", "1")
    w = TODAY - timedelta(days=49)
    assert build.check_freshness(w, w, TODAY) == (49, 0)
    assert "périmé" in capsys.readouterr().err


def test_ecart_tolere(capsys):
    assert build.check_freshness(TODAY, TODAY - timedelta(days=7), TODAY) == (0, 7)
    assert "écart" in capsys.readouterr().out


def test_ecart_trop_grand_echoue():
    with pytest.raises(SystemExit) as e:
        build.check_freshness(TODAY, TODAY - timedelta(days=8), TODAY)
    assert "désynchronisés" in str(e.value)


def test_ecart_echoue_meme_avec_derogation(monkeypatch):
    monkeypatch.setenv("LUX_SOLAIRE_ALLOW_STALE", "1")
    with pytest.raises(SystemExit):
        build.check_freshness(TODAY - timedelta(days=20), TODAY, TODAY)
