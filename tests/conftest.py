"""Tests Python de lux-solaire : `/usr/bin/python3 -m pytest tests/` depuis la racine du dépôt.
Les tests du moteur JS restent dans tests/sim-engine.test.mjs (`node --test`)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="session")
def root():
    return ROOT


@pytest.fixture(scope="session")
def commune_names():
    names = [c["c"] for c in json.loads((ROOT / "data" / "data.json").read_text())["communes"]]
    assert len(names) == 100
    return names


@pytest.fixture(scope="session")
def node():
    exe = shutil.which("node")
    if not exe:
        pytest.skip("node absent : tests croisés Python/JS sautés")

    def run(code, payload=None):
        r = subprocess.run([exe, "-e", code], input=json.dumps(payload), capture_output=True, text=True,
                           cwd=ROOT, timeout=60)
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    return run
