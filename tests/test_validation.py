"""Tests unitaires du validateur (T01 à T10, T15, T16, T18, T22, T23, T25 au niveau fonction)."""

import copy
import math

import pytest

from app.validation import ErreurValidation, valider_dossier

DOSSIER_VALIDE = {
    "age": 35,
    "revenu_mensuel": 250_000,
    "montant_credit": 1_000_000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}


def avec(**modifs):
    return {**DOSSIER_VALIDE, **modifs}


def champs_en_erreur(dossier):
    with pytest.raises(ErreurValidation) as exc:
        valider_dossier(dossier)
    return {champ for champ, _ in exc.value.erreurs}


def test_dossier_valide_accepte():
    valider_dossier(DOSSIER_VALIDE)


@pytest.mark.parametrize("age", [17, 101, -1, 0])
def test_age_hors_limites_rejete(age):  # T01
    assert champs_en_erreur(avec(age=age)) == {"age"}


@pytest.mark.parametrize("age", [18, 100])
def test_age_aux_limites_accepte(age):  # T02
    valider_dossier(avec(age=age))


@pytest.mark.parametrize("age", ["35", 35.5, 35.0, True, None])
def test_age_type_invalide_rejete(age):
    assert champs_en_erreur(avec(age=age)) == {"age"}


@pytest.mark.parametrize("revenu", ["abc", "250000", True, [250000]])
def test_revenu_non_numerique_rejete(revenu):  # T03
    assert champs_en_erreur(avec(revenu_mensuel=revenu)) == {"revenu_mensuel"}


@pytest.mark.parametrize("revenu", [0, -100, 0.0])
def test_revenu_nul_ou_negatif_rejete(revenu):  # T04
    assert champs_en_erreur(avec(revenu_mensuel=revenu)) == {"revenu_mensuel"}


@pytest.mark.parametrize("montant", [0, -1, -1_000_000])
def test_montant_nul_ou_negatif_rejete(montant):  # T05
    assert champs_en_erreur(avec(montant_credit=montant)) == {"montant_credit"}


def test_montant_texte_rejete():  # T06
    assert champs_en_erreur(avec(montant_credit="1 000 000")) == {"montant_credit"}


@pytest.mark.parametrize("duree", [12.5, 12.0])
def test_duree_non_entiere_rejetee(duree):  # T07 (12.0 est aussi rejeté : pas de conversion)
    assert champs_en_erreur(avec(duree_mois=duree)) == {"duree_mois"}


@pytest.mark.parametrize("duree", [0, 121, -6])
def test_duree_hors_limites_rejetee(duree):  # T08
    assert champs_en_erreur(avec(duree_mois=duree)) == {"duree_mois"}


@pytest.mark.parametrize("duree", [1, 120])
def test_duree_aux_limites_acceptee(duree):  # T09
    valider_dossier(avec(duree_mois=duree))


def test_duree_chaine_rejetee():  # T10
    assert champs_en_erreur(avec(duree_mois="12")) == {"duree_mois"}


@pytest.mark.parametrize("champ", list(DOSSIER_VALIDE))
def test_champ_obligatoire_absent_nomme_le_champ(champ):  # T15
    dossier = {k: v for k, v in DOSSIER_VALIDE.items() if k != champ}
    assert champs_en_erreur(dossier) == {champ}


def test_dossier_vide_liste_tous_les_champs():  # T16
    assert champs_en_erreur({}) == set(DOSSIER_VALIDE)


@pytest.mark.parametrize("champ", list(DOSSIER_VALIDE))
def test_champ_null_rejete(champ):  # T18
    assert champs_en_erreur(avec(**{champ: None})) == {champ}


def test_champ_supplementaire_rejete():  # T22
    assert champs_en_erreur({**DOSSIER_VALIDE, "nom": "Awa"}) == {"nom"}


@pytest.mark.parametrize(
    ("champ", "valeur"),
    [("revenu_mensuel", 1e308), ("montant_credit", 1e20)],
)
def test_valeurs_extremes_rejetees(champ, valeur):  # T23
    assert champs_en_erreur(avec(**{champ: valeur})) == {champ}


@pytest.mark.parametrize("valeur", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("champ", ["revenu_mensuel", "montant_credit", "anciennete_activite"])
def test_valeurs_non_finies_rejetees(champ, valeur):  # T25 (niveau validateur)
    assert champs_en_erreur(avec(**{champ: valeur})) == {champ}


def test_anciennete_negative_rejetee():
    assert champs_en_erreur(avec(anciennete_activite=-1)) == {"anciennete_activite"}


def test_anciennete_zero_acceptee():
    valider_dossier(avec(anciennete_activite=0))


def test_plusieurs_erreurs_sont_toutes_rapportees():
    assert champs_en_erreur(avec(age=10, duree_mois=0, revenu_mensuel=-5)) == {
        "age",
        "duree_mois",
        "revenu_mensuel",
    }


@pytest.mark.parametrize("mauvais", [None, [], "dossier", 42])
def test_dossier_non_dictionnaire_rejete(mauvais):
    assert champs_en_erreur(mauvais) == {"dossier"}


def test_le_validateur_ne_modifie_pas_le_dossier():
    dossier = copy.deepcopy(DOSSIER_VALIDE)
    valider_dossier(dossier)
    assert dossier == DOSSIER_VALIDE


def test_erreur_validation_est_une_valueerror_lisible():
    with pytest.raises(ValueError, match="age"):
        valider_dossier(avec(age=17))
