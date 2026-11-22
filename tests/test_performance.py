"""Tests de performance légers (Activité 6) : objectifs fixés à l'avance, mesures locales rapides.

Les seuils sont ceux de scripts.perf.OBJECTIFS. Ils sont volontairement larges par rapport aux
mesures habituelles (marge d'un facteur 20 environ) pour ne pas rendre la CI instable.
"""

import pytest

from scripts import perf
from scripts.perf import OBJECTIFS

DOSSIERS = perf.dossiers_exemples()


def test_latence_d_inference_sous_l_objectif():
    mesure = perf.latence_inference(DOSSIERS, repetitions=200)
    assert mesure["p95_ms"] <= OBJECTIFS["inference_p95_ms"]


def test_temps_de_reponse_de_l_api_sous_l_objectif():
    mesure = perf.latence_api_en_memoire(DOSSIERS, repetitions=100)
    assert mesure["p95_ms"] <= OBJECTIFS["api_p95_ms"]


def test_charge_http_legere_sans_erreur():
    with perf.ServeurUvicorn():
        mesure = perf.palier(DOSSIERS, utilisateurs=3, duree_s=1.0)
    assert mesure["erreurs"] == 0
    assert mesure["n"] > 10
    assert mesure["debit_rps"] >= OBJECTIFS["debit_min_rps"]
    assert mesure["p95_ms"] <= OBJECTIFS["api_p95_ms"]


def test_percentiles():
    m = perf.percentiles([float(i) for i in range(1, 101)])
    assert (m["n"], m["p50_ms"], m["p95_ms"], m["max_ms"]) == (100, 51.0, 96.0, 100.0)


def resultats_fictifs(p95=10.0, debit=100.0, erreurs=0, inference=2.0):
    palier = {"utilisateurs": 10, "p95_ms": p95, "debit_rps": debit, "erreurs": erreurs}
    return {"inference": {"p95_ms": inference}, "paliers": [palier]}


def verdicts(resultats):
    return [o["tenu"] for o in perf.evaluer_objectifs(resultats)]


def test_objectifs_tenus():
    assert all(verdicts(resultats_fictifs()))


@pytest.mark.parametrize(
    ("modif", "index"),
    [
        ({"inference": 80.0}, 0),
        ({"p95": 450.0}, 1),
        ({"debit": 5.0}, 2),
        ({"erreurs": 1}, 3),
    ],
)
def test_chaque_objectif_non_tenu_est_detecte(modif, index):
    resultat = verdicts(resultats_fictifs(**modif))
    assert resultat[index] is False
    assert resultat.count(False) == 1


def test_le_rapport_contient_les_tableaux():
    resultats = resultats_fictifs()
    resultats["configuration"] = perf.configuration()
    mesure = {"moyenne_ms": 1, "p50_ms": 1, "p95_ms": 2, "p99_ms": 3, "max_ms": 4, "n": 5}
    resultats["api_memoire"] = mesure
    resultats["inference"] = mesure
    resultats["paliers"][0].update(mesure)
    resultats["objectifs"] = perf.evaluer_objectifs(resultats)
    texte = perf.rediger_rapport(resultats)
    assert "Montée en charge progressive" in texte
    assert "| Objectif |" in texte
