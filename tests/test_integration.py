"""Tests d'intégration (Activité 3) : validation, prétraitement, modèle et API ensemble."""

import json
import logging
import shutil

import joblib
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.prediction import CHEMIN_META, CHEMIN_MODELE, charger_modele
from app.preprocessing import VARIABLES_MODELE

DOSSIER = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}
ERREUR_GENERIQUE = {"erreur": "Erreur interne."}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def assert_500_generique(reponse, *mots_interdits):
    assert reponse.status_code == 500
    assert reponse.json() == ERREUR_GENERIQUE
    for mot in ("Traceback", 'File "', ".py", *mots_interdits):
        assert mot not in reponse.text


# ---------- scénario principal ----------


def test_scenario_principal_de_bout_en_bout(client, monkeypatch):
    appels = []
    capture = {}
    import app.prediction as pred

    vrai_valider, vrai_pretraiter = pred.valider_dossier, pred.preprocess_data

    def espion_valider(dossier):
        appels.append("validation")
        return vrai_valider(dossier)

    def espion_pretraiter(df):
        appels.append("pretraitement")
        capture["x"] = vrai_pretraiter(df)
        return capture["x"]

    pipeline = client.app.state.modele.pipeline
    vrai_predict_proba = pipeline.predict_proba

    def espion_modele(x):
        appels.append("modele")
        return vrai_predict_proba(x)

    monkeypatch.setattr("app.prediction.valider_dossier", espion_valider)
    monkeypatch.setattr("app.prediction.preprocess_data", espion_pretraiter)
    monkeypatch.setattr(pipeline, "predict_proba", espion_modele)

    r = client.post("/predict", json=DOSSIER)

    assert r.status_code == 200
    # 1. validation, 2. transformation, 3. prédiction, dans cet ordre
    assert appels == ["validation", "pretraitement", "modele"]
    # transformation des variables : colonnes du modèle et variable dérivée correcte
    x = capture["x"]
    assert list(x.columns) == VARIABLES_MODELE
    assert x["charge_mensuelle"].iloc[0] == pytest.approx((1_000_000 / 12) / 250_000)
    # structure de la réponse et cohérence avec le modèle
    corps = r.json()
    assert set(corps) == {
        "prediction",
        "probabilite_defaut",
        "seuil",
        "version_modele",
        "avertissements",
    }
    assert corps["probabilite_defaut"] == pytest.approx(vrai_predict_proba(x)[0, 1])


def test_metadonnees_du_modele_coherentes(client):
    info = client.get("/model-info").json()
    pipeline = client.app.state.modele.pipeline
    reponse = client.post("/predict", json=DOSSIER).json()

    assert reponse["version_modele"] == info["version_modele"]
    assert reponse["seuil"] == info["seuil"]
    assert info["variables"] == VARIABLES_MODELE
    assert list(pipeline.feature_names_in_) == info["variables"]
    assert pipeline[0].n_features_in_ == len(info["variables"])
    assert info["metriques_reference"]["rappel"] >= 0.85


# ---------- scénarios complémentaires : pannes maîtrisées ----------


def test_modele_non_chargeable(monkeypatch, tmp_path):
    (tmp_path / "m.joblib").write_bytes(b"fichier corrompu")
    (tmp_path / "m.json").write_text("{}", encoding="utf-8")

    def charge_un_fichier_corrompu():
        return charger_modele(tmp_path / "m.joblib", tmp_path / "m.json")

    monkeypatch.setattr("app.main.charger_modele", charge_un_fichier_corrompu)
    with TestClient(app) as c:
        r = c.post("/predict", json=DOSSIER)
    assert r.status_code == 503
    for mot in (str(tmp_path), "joblib", "pickle", "Traceback"):
        assert mot not in r.text


def test_variable_attendue_absente_apres_pretraitement(client, monkeypatch):
    import app.prediction as pred

    vrai = pred.preprocess_data
    monkeypatch.setattr(
        "app.prediction.preprocess_data", lambda df: vrai(df).drop(columns=["charge_mensuelle"])
    )
    assert_500_generique(client.post("/predict", json=DOSSIER), "charge_mensuelle")


def test_dimensions_inattendues_apres_pretraitement(client, monkeypatch):
    import app.prediction as pred

    vrai = pred.preprocess_data
    monkeypatch.setattr(
        "app.prediction.preprocess_data", lambda df: vrai(df).assign(colonne_intruse=1.0)
    )
    assert_500_generique(client.post("/predict", json=DOSSIER), "colonne_intruse")


def test_erreur_de_pretraitement(client, monkeypatch):
    def casse(_df):
        raise ValueError("détail technique du prétraitement")

    monkeypatch.setattr("app.prediction.preprocess_data", casse)
    assert_500_generique(client.post("/predict", json=DOSSIER), "détail")


def test_erreur_interne_pendant_la_prediction(client, monkeypatch):
    def panne(_x):
        raise RuntimeError("secret interne : /home/prod/modele.bin")

    monkeypatch.setattr(client.app.state.modele.pipeline, "predict_proba", panne)
    assert_500_generique(client.post("/predict", json=DOSSIER), "secret", "/home")


def test_exception_inattendue_hors_logique_metier(client, monkeypatch):
    def explose(*_args, **_kwargs):
        raise RuntimeError("bug imprévu")

    monkeypatch.setattr("app.main.predire", explose)
    assert_500_generique(client.post("/predict", json=DOSSIER), "bug")


def test_le_service_reste_utilisable_apres_une_erreur_interne(client, monkeypatch):
    pipeline = client.app.state.modele.pipeline
    vrai = pipeline.predict_proba

    def panne(_x):
        raise RuntimeError("panne ponctuelle")

    monkeypatch.setattr(pipeline, "predict_proba", panne)
    assert client.post("/predict", json=DOSSIER).status_code == 500
    monkeypatch.setattr(pipeline, "predict_proba", vrai)
    assert client.post("/predict", json=DOSSIER).status_code == 200


# ---------- journaux : aucune donnée personnelle ----------


def test_journaux_sans_donnees_personnelles(client, monkeypatch, caplog):
    def panne(_x):
        raise RuntimeError("panne")

    with caplog.at_level(logging.DEBUG):
        client.post("/predict", json=DOSSIER)
        client.post("/predict", json={**DOSSIER, "revenu_mensuel": "valeur-secrete-12345"})
        monkeypatch.setattr(client.app.state.modele.pipeline, "predict_proba", panne)
        client.post("/predict", json=DOSSIER)
    assert caplog.records
    for valeur in ("250000", "1000000", "valeur-secrete-12345"):
        assert valeur not in caplog.text


# ---------- reproductibilité du pipeline sauvegardé et rechargé ----------


def test_memes_predictions_apres_redemarrage_et_rechargement(client, monkeypatch, tmp_path):
    avant = client.post("/predict", json=DOSSIER).json()

    # copie du modèle sauvegardé, rechargée comme le ferait un nouveau déploiement
    copie_modele, copie_meta = tmp_path / "copie.joblib", tmp_path / "copie.json"
    joblib.dump(client.app.state.modele.pipeline, copie_modele)
    shutil.copy(CHEMIN_META, copie_meta)
    monkeypatch.setattr(
        "app.main.charger_modele", lambda: charger_modele(copie_modele, copie_meta)
    )
    with TestClient(app) as redemarre:
        apres = redemarre.post("/predict", json=DOSSIER).json()

    assert apres == avant


def test_les_fichiers_du_modele_versionne_sont_presents_et_coherents():
    assert CHEMIN_MODELE.exists()
    meta = json.loads(CHEMIN_META.read_text(encoding="utf-8"))
    assert meta["variables"] == VARIABLES_MODELE
