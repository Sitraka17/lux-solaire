"""Arrondis Python alignés sur le navigateur : _jsround = Math.round (moitié vers +∞),
_dec1 = toLocaleString à un chiffre (moitié qui s'éloigne de zéro sur la représentation courte)."""
import build

HALVES = [0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 1234.5, 0.49999999999999994, 2.675 * 100]
DEC = [0.05, 0.15, 0.25, 0.35, 0.45, 1.05, 2.25, 9.95, 1234.45, 12345.65, -0.25, -1.35, 0.0, 1e-9]


def test_jsround_cas_points_cinq():
    assert [build._jsround(x) for x in (0.5, 1.5, 2.5, -0.5, -1.5, -2.5)] == [1, 2, 3, 0, -1, -2]


def test_jsround_comme_math_round(node):
    js = node("const xs = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              "process.stdout.write(JSON.stringify(xs.map(Math.round)));", HALVES)
    assert [build._jsround(x) for x in HALVES] == js


def test_dec1_cas_points_cinq():
    assert build._dec1(0.25, "fr") == "0,3"
    assert build._dec1(0.35, "en") == "0.4"
    assert build._dec1(2.25, "fr") == "2,3"
    assert build._dec1(9.95, "fr") == "10,0"
    assert build._dec1(1234.45, "en") == "1,234.5"
    assert build._dec1(12345.65, "fr") == "12 345,7"
    assert build._dec1(-0.25, "fr") == "-0,3"


def test_dec1_comme_tolocalestring(node):
    js = node("const xs = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
              "const o = {minimumFractionDigits: 1, maximumFractionDigits: 1};"
              "process.stdout.write(JSON.stringify(xs.map(x => [x.toLocaleString('fr-FR', o), x.toLocaleString('en-US', o)])));",
              DEC)
    for x, (fr, en) in zip(DEC, js):
        fr = fr.replace(" ", " ").replace(" ", " ").replace("−", "-")
        if fr == "-0,0":   # toLocaleString garde le signe de -0 ; sans objet ici
            continue
        assert build._dec1(x, "fr") == fr, x
        assert build._dec1(x, "en") == en.replace("−", "-"), x
