"""Tests de l'analyse par profil (Activité 7) : calcul correct, et exigence d'équité de détection.

L'exigence « aucune tranche ne dépasse le taux de faux négatifs maximal » est aujourd'hui NON
tenue : anomalie A11 (ouverte), documentée par un test xfail strict.
"""

import numpy as np
import pandas as pd
import pytest

from app.preprocessing import CIBLE
from scripts import analyse_sous_groupes as sg
from scripts.regression import jeux_evaluation


@pytest.fixture(scope="module")
def analyse():
    donnees, decisions = sg.jeu_de_test_avec_decisions()
    return donnees, decisions, sg.analyser(donnees, decisions)


def test_wilson_cas_connus():
    bas, haut = sg.wilson(0, 10)
    assert bas == 0.0
    assert haut == pytest.approx(0.2775, abs=1e-3)
    bas, haut = sg.wilson(13, 14)
    assert (round(bas, 2), round(haut, 2)) == (0.69, 0.99)
    assert sg.wilson(0, 0) == (0.0, 1.0)
    for k, n in [(1, 2), (5, 50), (50, 50)]:
        bas, haut = sg.wilson(k, n)
        assert 0.0 <= bas <= k / n <= haut <= 1.0


def test_calcul_sur_un_exemple_construit():
    donnees = pd.DataFrame(
        {
            "age": [20, 22, 40, 41, 60],
            "revenu_mensuel": [150_000.0] * 5,
            "montant_credit": [1_000_000.0] * 5,
            "duree_mois": [12] * 5,
            "anciennete_activite": [1.0] * 5,
            "charge_mensuelle": [0.3] * 5,
            CIBLE: [1, 1, 1, 0, 1],
        }
    )
    decisions = np.array([True, False, False, False, True])
    resultat = sg.analyser(donnees, decisions).set_index(["variable", "tranche"])
    jeunes = resultat.loc[("age", "18-25")]
    assert (jeunes.effectif, jeunes.defauts, jeunes.faux_negatifs) == (2, 2, 1)
    assert jeunes.fnr == pytest.approx(0.5)
    assert jeunes.non_concluant  # moins de 10 défauts : on ne conclut pas
    assert not jeunes.signalee


def test_les_tranches_couvrent_tous_les_dossiers(analyse):
    donnees, _decisions, resultat = analyse
    for variable in sg.TRANCHES:
        sous = resultat[resultat["variable"] == variable]
        assert sous["effectif"].sum() == len(donnees), variable
        assert sous["defauts"].sum() == int(donnees[CIBLE].sum()), variable


def test_coherence_avec_le_rappel_global_de_la_baseline(analyse):
    _donnees, _decisions, resultat = analyse
    sous = resultat[resultat["variable"] == "age"]
    rappel = 1 - sous["faux_negatifs"].sum() / sous["defauts"].sum()
    assert rappel == pytest.approx(0.87037, abs=1e-4)


def test_une_tranche_peu_peuplee_n_est_jamais_signalee(analyse):
    _donnees, _decisions, resultat = analyse
    peu = resultat[resultat["defauts"] < sg.MIN_DEFAUTS]
    assert not peu["signalee"].any()
    assert peu["non_concluant"].all()


def test_le_rapport_liste_les_tranches(analyse):
    donnees, decisions, resultat = analyse
    texte = sg.rediger(resultat, donnees, decisions)
    assert "37-48 mois" in texte
    assert "SIGNALÉE" in texte


def test_les_donnees_sont_celles_du_jeu_de_test(analyse):
    donnees, _decisions, _resultat = analyse
    _val, test = jeux_evaluation()
    assert len(donnees) == len(test) == 2000


@pytest.mark.xfail(
    strict=True,
    reason="A11 (ouverte) : le taux de faux négatifs dépasse le maximum pour certains profils",
)
def test_aucune_tranche_ne_depasse_le_taux_de_faux_negatifs_maximal(analyse):
    _donnees, _decisions, resultat = analyse
    assert not resultat["signalee"].any()
