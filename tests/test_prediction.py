"""Tests unitaires de la prédiction (T11, T12, T13, T14, T24 à T36)."""

import json
import logging
import math

import joblib
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sklearn.linear_model import LogisticRegression

from app.prediction import (
    ErreurPrediction,
    Modele,
    ModeleIndisponible,
    charger_modele,
    predire,
    valider_seuil,
)
from app.preprocessing import preprocess_data
from app.validation import REVENU_MAX, REVENU_MIN, ErreurValidation
from scripts.generate_data import generate

DOSSIER = {
    "age": 35,
    "revenu_mensuel": 250_000,
    "montant_credit": 1_000_000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}


@pytest.fixture(scope="module")
def modele():
    return charger_modele()


class PipelineEnPanne:
    def predict_proba(self, _x):
        raise RuntimeError("secret interne : /home/prod/modele.bin")


class PipelineHorsContrat:
    def predict_proba(self, _x):
        return np.array([[0.3, 1.7]])


def modele_factice(pipeline, modele_reel):
    return Modele(pipeline=pipeline, meta=modele_reel.meta)


# ---------- T11 : contrat de la réponse ----------


def test_dossier_reference_respecte_le_contrat(modele):  # T11
    r = predire(modele, DOSSIER)
    assert set(r) == {
        "prediction",
        "probabilite_defaut",
        "seuil",
        "version_modele",
        "avertissements",
    }
    assert r["prediction"] in (0, 1)
    assert math.isfinite(r["probabilite_defaut"])
    assert 0.0 <= r["probabilite_defaut"] <= 1.0
    assert r["version_modele"] == modele.version
    assert r["avertissements"] == []


# ---------- T12 : propriété sur des dossiers valides générés ----------

dossiers_valides = st.fixed_dictionaries(
    {
        "age": st.integers(18, 100),
        "revenu_mensuel": st.floats(min_value=REVENU_MIN, max_value=REVENU_MAX, allow_nan=False),
        "montant_credit": st.floats(
            min_value=0, max_value=10_000_000_000, exclude_min=True, allow_nan=False
        ),
        "duree_mois": st.integers(1, 120),
        "anciennete_activite": st.floats(min_value=0, max_value=60, allow_nan=False),
    }
)


@settings(max_examples=200, deadline=None)
@given(dossier=dossiers_valides)
def test_probabilite_toujours_valide_pour_tout_dossier_valide(modele, dossier):  # T12
    p = predire(modele, dossier)["probabilite_defaut"]
    assert math.isfinite(p)
    assert 0.0 <= p <= 1.0


# ---------- T24, T26 : avertissements hors domaine ----------


def test_montant_plausible_mais_inhabituel_accepte_avec_avertissement(modele):  # T24
    r = predire(modele, {**DOSSIER, "montant_credit": 5_000_000_000})
    assert 0.0 <= r["probabilite_defaut"] <= 1.0
    assert any("montant_credit" in a for a in r["avertissements"])


def test_hors_domaine_signale(modele):  # T26
    r = predire(modele, {**DOSSIER, "age": 90, "duree_mois": 100})
    champs = " ".join(r["avertissements"])
    assert "age" in champs
    assert "duree_mois" in champs


# ---------- T25 : un dossier invalide n'atteint jamais le modèle ----------


def test_dossier_invalide_rejete_avant_le_modele(modele):
    class NeDoitPasEtreAppele:
        def predict_proba(self, _x):
            raise AssertionError("le modèle ne doit pas être appelé")

    m = modele_factice(NeDoitPasEtreAppele(), modele)
    with pytest.raises(ErreurValidation):
        predire(m, {**DOSSIER, "revenu_mensuel": float("nan")})


# ---------- T27, T28, T29, T30 : erreurs internes maîtrisées ----------


def test_erreur_du_modele_devient_erreur_generique(modele):  # T27
    m = modele_factice(PipelineEnPanne(), modele)
    with pytest.raises(ErreurPrediction) as exc:
        predire(m, DOSSIER)
    assert "secret" not in str(exc.value)
    assert "/home" not in str(exc.value)


def test_erreur_de_pretraitement_devient_erreur_generique(modele, monkeypatch):  # T28
    def casse(_df):
        raise ValueError("détail technique du prétraitement")

    monkeypatch.setattr("app.prediction.preprocess_data", casse)
    with pytest.raises(ErreurPrediction) as exc:
        predire(modele, DOSSIER)
    assert "détail" not in str(exc.value)


def test_dimensions_incompatibles_avec_le_modele(modele):  # T29
    petit = LogisticRegression().fit(
        pd.DataFrame({"a": [0.0, 1.0, 0.0, 1.0], "b": [1.0, 0.0, 0.0, 1.0]}), [0, 1, 0, 1]
    )
    with pytest.raises(ErreurPrediction):
        predire(modele_factice(petit, modele), DOSSIER)


def test_probabilite_hors_contrat_refusee(modele):
    with pytest.raises(ErreurPrediction):
        predire(modele_factice(PipelineHorsContrat(), modele), DOSSIER)


def test_les_journaux_ne_contiennent_pas_les_valeurs_du_dossier(modele, caplog):  # T30
    m = modele_factice(PipelineEnPanne(), modele)
    with caplog.at_level(logging.DEBUG), pytest.raises(ErreurPrediction):
        predire(m, DOSSIER)
    assert caplog.records, "une erreur doit être journalisée"
    for valeur in ("250000", "1000000", "revenu_mensuel", "secret"):
        assert valeur not in caplog.text


# ---------- T13, T14 : modèle indisponible ----------


def test_modele_absent(tmp_path):  # T13 / T14
    with pytest.raises(ModeleIndisponible):
        charger_modele(tmp_path / "absent.joblib", tmp_path / "absent.json")


def test_modele_corrompu(tmp_path):  # T14
    (tmp_path / "m.joblib").write_bytes(b"pas un modele")
    (tmp_path / "m.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModeleIndisponible):
        charger_modele(tmp_path / "m.joblib", tmp_path / "m.json")


def test_metadonnees_incompletes(tmp_path, modele):
    joblib.dump(modele.pipeline, tmp_path / "m.joblib")
    (tmp_path / "m.json").write_text('{"version_modele": "v1"}', encoding="utf-8")
    with pytest.raises(ModeleIndisponible):
        charger_modele(tmp_path / "m.joblib", tmp_path / "m.json")


def test_objet_charge_qui_n_est_pas_un_modele(tmp_path, modele):
    joblib.dump("je ne suis pas un modèle", tmp_path / "m.joblib")
    (tmp_path / "m.json").write_text(json.dumps(modele.meta), encoding="utf-8")
    with pytest.raises(ModeleIndisponible):
        charger_modele(tmp_path / "m.joblib", tmp_path / "m.json")


def test_seuil_invalide_dans_les_metadonnees(tmp_path, modele):
    joblib.dump(modele.pipeline, tmp_path / "m.joblib")
    meta = {**modele.meta, "seuil": 1.5}
    (tmp_path / "m.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ModeleIndisponible):
        charger_modele(tmp_path / "m.joblib", tmp_path / "m.json")


# ---------- T31, T32 : reproductibilité ----------


def test_meme_dossier_meme_probabilite(modele):  # T31
    assert predire(modele, DOSSIER) == predire(modele, DOSSIER)


def test_predictions_identiques_apres_sauvegarde_et_rechargement(tmp_path, modele):  # T32
    joblib.dump(modele.pipeline, tmp_path / "copie.joblib")
    recharge = joblib.load(tmp_path / "copie.joblib")
    x = preprocess_data(generate(n=1000, seed=7).drop(columns=["defaut"]))
    avant = modele.pipeline.predict_proba(x)[:, 1]
    apres = recharge.predict_proba(x)[:, 1]
    assert abs(avant - apres).max() <= 1e-9


# ---------- T34, T35, T36 : seuil ----------


def test_le_seuil_du_modele_est_utilise_et_expose(modele):  # T34
    assert predire(modele, DOSSIER)["seuil"] == modele.seuil


def test_changer_le_seuil_change_la_classe_pas_la_probabilite(modele):  # T35
    bas = predire(modele, DOSSIER, seuil=0.0001)
    haut = predire(modele, DOSSIER, seuil=0.9999)
    assert bas["prediction"] == 1
    assert haut["prediction"] == 0
    assert bas["probabilite_defaut"] == haut["probabilite_defaut"]


@pytest.mark.parametrize("seuil", [0, 1, -0.2, 1.5, float("nan"), float("inf"), "0.5", True, None])
def test_seuil_invalide_rejete(seuil):  # T36
    with pytest.raises(ValueError, match="seuil"):
        valider_seuil(seuil)


def test_seuil_valide_accepte():
    assert valider_seuil(0.3) == 0.3
