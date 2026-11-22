"""Tests unitaires du prétraitement (T03, T25 côté pipeline, cohérence des dimensions)."""

import numpy as np
import pandas as pd
import pytest

from app.preprocessing import (
    VARIABLES_BRUTES,
    VARIABLES_MODELE,
    dossier_vers_dataframe,
    preprocess_data,
)

DOSSIER = {
    "age": 35,
    "revenu_mensuel": 250_000,
    "montant_credit": 1_000_000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}


def df_valide(n=3):
    return pd.DataFrame([DOSSIER] * n)


def test_sortie_a_les_colonnes_du_modele_dans_l_ordre():
    sortie = preprocess_data(df_valide())
    assert list(sortie.columns) == VARIABLES_MODELE


def test_dimensions_coherentes():
    sortie = preprocess_data(df_valide(5))
    assert sortie.shape == (5, len(VARIABLES_BRUTES) + 1)


def test_charge_mensuelle_calculee_correctement():
    sortie = preprocess_data(df_valide(1))
    attendu = (1_000_000 / 12) / 250_000
    assert sortie["charge_mensuelle"].iloc[0] == pytest.approx(attendu)


def test_sortie_finie():
    assert np.isfinite(preprocess_data(df_valide()).to_numpy()).all()


def test_entree_non_modifiee():
    df = df_valide()
    copie = df.copy(deep=True)
    preprocess_data(df)
    pd.testing.assert_frame_equal(df, copie)


def test_une_seule_observation():
    assert preprocess_data(df_valide(1)).shape == (1, 6)


def test_la_cible_n_est_pas_une_variable_d_entree():
    df = df_valide().assign(defaut=[0, 1, 0])
    sortie = preprocess_data(df)
    assert "defaut" not in sortie.columns


def test_colonne_manquante_rejetee():
    df = df_valide().drop(columns=["revenu_mensuel"])
    with pytest.raises(ValueError, match="revenu_mensuel"):
        preprocess_data(df)


def test_donnees_vides_rejetees():
    with pytest.raises(ValueError, match="vides"):
        preprocess_data(df_valide().iloc[0:0])


def test_entree_non_dataframe_rejetee():
    with pytest.raises(TypeError):
        preprocess_data([DOSSIER])


@pytest.mark.parametrize("valeur", [np.nan, np.inf, -np.inf])
def test_valeurs_non_finies_rejetees(valeur):
    df = df_valide().astype(float)
    df.loc[0, "montant_credit"] = valeur
    with pytest.raises(ValueError, match="non finies"):
        preprocess_data(df)


@pytest.mark.parametrize("champ", ["revenu_mensuel", "duree_mois"])
def test_division_par_zero_empechee(champ):
    df = df_valide()
    df.loc[0, champ] = 0
    with pytest.raises(ValueError, match="strictement positifs"):
        preprocess_data(df)


def test_dossier_vers_dataframe_une_ligne():
    df = dossier_vers_dataframe(DOSSIER)
    assert df.shape == (1, 5)
    assert df.iloc[0].to_dict() == DOSSIER
