"""Tests du modèle sauvegardé (T33, T39, T40) et de sa compatibilité avec le code d'inférence."""

import warnings

import numpy as np
import pytest
from sklearn.exceptions import InconsistentVersionWarning

from app.prediction import charger_modele
from app.preprocessing import CIBLE, preprocess_data
from scripts.generate_data import generate
from scripts.train import RAPPEL_MIN, construire_pipeline, separer


@pytest.fixture(scope="module")
def modele():
    return charger_modele()


@pytest.fixture(scope="module")
def donnees():
    return generate(n=10_000, seed=42)


def test_entrainement_reproductible_avec_la_meme_graine(donnees):  # T33
    train, _val, _test = separer(donnees)
    x, y = preprocess_data(train), train[CIBLE]
    a = construire_pipeline().fit(x, y)
    b = construire_pipeline().fit(x, y)
    np.testing.assert_array_equal(a[-1].coef_, b[-1].coef_)
    np.testing.assert_array_equal(a[-1].intercept_, b[-1].intercept_)


def test_la_separation_est_stratifiee_et_sans_chevauchement(donnees):
    train, val, test = separer(donnees)
    assert len(train) + len(val) + len(test) == len(donnees)
    assert not set(train.index) & set(val.index)
    assert not set(train.index) & set(test.index)
    assert not set(val.index) & set(test.index)
    taux = donnees[CIBLE].mean()
    for partie in (train, val, test):
        assert partie[CIBLE].mean() == pytest.approx(taux, abs=0.005)


def test_la_cible_n_est_pas_une_variable_du_modele(modele):  # T40
    assert CIBLE not in modele.meta["variables"]


def test_scaler_ajuste_sur_l_entrainement_seulement(modele, donnees):  # T40
    scaler = modele.pipeline[0]
    assert scaler.n_samples_seen_ == modele.meta["tailles"]["train"]
    assert scaler.n_samples_seen_ == int(0.6 * len(donnees))


def test_rappel_vise_atteint_sur_la_validation(modele):  # T39
    assert modele.meta["metriques_validation"]["rappel"] >= RAPPEL_MIN


def test_metriques_enregistrees_coherentes_avec_un_recalcul(modele, donnees):  # T39
    _train, val, _test = separer(donnees)
    proba = modele.pipeline.predict_proba(preprocess_data(val))[:, 1]
    pred = proba >= modele.seuil
    rappel = (pred & (val[CIBLE] == 1)).sum() / (val[CIBLE] == 1).sum()
    assert rappel == pytest.approx(modele.meta["metriques_validation"]["rappel"], abs=0.03)


def test_modele_serialise_compatible_avec_les_bibliotheques_installees():
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        charger_modele()
