"""Tests fonctionnels de l'API (T11 à T26, T34 à T36, T41, T42 au niveau HTTP)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.prediction import ModeleIndisponible, charger_modele

DOSSIER = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}
JSON_HEADERS = {"content-type": "application/json"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def post(client, corps):
    return client.post("/predict", json=corps)


def champs(reponse):
    return {d["champ"] for d in reponse.json()["details"]}


# ---------- requête valide (EX04, T11) ----------


def test_requete_valide(client):
    r = post(client, DOSSIER)
    assert r.status_code == 200
    corps = r.json()
    assert 0 <= corps["probabilite_defaut"] <= 1
    assert corps["prediction"] in (0, 1)
    assert corps["version_modele"] == "v1"
    assert corps["avertissements"] == []


# ---------- champs obligatoires (EX06, T15 à T18) ----------


@pytest.mark.parametrize("champ", list(DOSSIER))
def test_champ_obligatoire_absent(client, champ):  # T15
    r = post(client, {k: v for k, v in DOSSIER.items() if k != champ})
    assert r.status_code == 422
    assert champs(r) == {champ}


def test_corps_vide(client):  # T16
    r = post(client, {})
    assert r.status_code == 422
    assert champs(r) == set(DOSSIER)


@pytest.mark.parametrize("contenu", ['{"age": 35,', "pas du json", "", "[1, 2]", "null", '"texte"'])
def test_requete_mal_formee_ou_non_objet(client, contenu):  # T17
    r = client.post("/predict", content=contenu, headers=JSON_HEADERS)
    assert r.status_code == 422
    assert "erreur" in r.json()


@pytest.mark.parametrize("champ", list(DOSSIER))
def test_champ_null(client, champ):  # T18
    r = post(client, {**DOSSIER, champ: None})
    assert r.status_code == 422
    assert champs(r) == {champ}


# ---------- scénarios obligatoires de l'énoncé (EX01 à EX03) ----------


@pytest.mark.parametrize("age", [-1, 0, 17, 101])
def test_age_invalide(client, age):  # T01 (dont âge négatif)
    r = post(client, {**DOSSIER, "age": age})
    assert r.status_code == 422
    assert champs(r) == {"age"}


@pytest.mark.parametrize("age", [18, 100])
def test_age_aux_limites(client, age):  # T02
    assert post(client, {**DOSSIER, "age": age}).status_code == 200


@pytest.mark.parametrize("revenu", ["abc", "250000", True])
def test_revenu_texte(client, revenu):  # T03
    r = post(client, {**DOSSIER, "revenu_mensuel": revenu})
    assert r.status_code == 422
    assert champs(r) == {"revenu_mensuel"}


@pytest.mark.parametrize("montant", [0, -1, -1000000])
def test_montant_nul_ou_negatif(client, montant):  # T05
    r = post(client, {**DOSSIER, "montant_credit": montant})
    assert r.status_code == 422
    assert champs(r) == {"montant_credit"}


@pytest.mark.parametrize("duree", [12.5, "12", 0, 121, -6])
def test_duree_invalide(client, duree):  # T07, T08, T10
    r = post(client, {**DOSSIER, "duree_mois": duree})
    assert r.status_code == 422
    assert champs(r) == {"duree_mois"}


@pytest.mark.parametrize("duree", [1, 120])
def test_duree_aux_limites(client, duree):  # T09
    assert post(client, {**DOSSIER, "duree_mois": duree}).status_code == 200


def test_champ_supplementaire_refuse(client):  # T22
    r = post(client, {**DOSSIER, "nom": "Awa Diop"})
    assert r.status_code == 422
    assert champs(r) == {"nom"}


# ---------- valeurs extrêmes, non finies, hors domaine (EX09 à EX11) ----------


@pytest.mark.parametrize(
    ("champ", "valeur"), [("revenu_mensuel", 1e308), ("montant_credit", 1e20)]
)
def test_valeurs_extremement_elevees_rejetees(client, champ, valeur):  # T23
    r = post(client, {**DOSSIER, champ: valeur})
    assert r.status_code == 422
    assert champs(r) == {champ}


def test_valeur_elevee_mais_plausible_acceptee_avec_avertissement(client):  # T24
    r = post(client, {**DOSSIER, "montant_credit": 5_000_000_000})
    assert r.status_code == 200
    assert any("montant_credit" in a for a in r.json()["avertissements"])


@pytest.mark.parametrize("valeur", ["NaN", "Infinity", "-Infinity"])
def test_valeurs_non_finies_rejetees(client, valeur):  # T25
    contenu = (
        '{"age": 35, "revenu_mensuel": '
        + valeur
        + ', "montant_credit": 1000000, "duree_mois": 12, "anciennete_activite": 4}'
    )
    r = client.post("/predict", content=contenu, headers=JSON_HEADERS)
    assert r.status_code == 422
    assert champs(r) == {"revenu_mensuel"}


def test_hors_domaine_signale(client):  # T26
    r = post(client, {**DOSSIER, "age": 90, "duree_mois": 100})
    assert r.status_code == 200
    texte = " ".join(r.json()["avertissements"])
    assert "age" in texte
    assert "duree_mois" in texte


# ---------- contrat de la réponse d'erreur ----------


def test_erreur_422_ne_repete_pas_les_valeurs_envoyees(client):
    r = post(client, {**DOSSIER, "revenu_mensuel": "valeur-secrete-12345"})
    assert r.status_code == 422
    assert "valeur-secrete-12345" not in r.text


def test_erreur_422_sans_trace_technique(client):
    r = post(client, {**DOSSIER, "age": -1})
    for mot in ("Traceback", 'File "', ".py"):
        assert mot not in r.text


# ---------- endpoints annexes (EX17, T41, T42) ----------


def test_health(client):  # T41
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "modele_charge": True}


def test_model_info(client):  # T34, T41
    r = client.get("/model-info")
    assert r.status_code == 200
    info = r.json()
    for cle in (
        "version_modele",
        "seuil",
        "variables",
        "date_entrainement",
        "metriques_reference",
        "domaine_entrainement",
    ):
        assert cle in info
    assert 0 < info["seuil"] < 1
    assert "charge_mensuelle" in info["variables"]
    assert "synthétiques" in info["donnees"]


def test_le_seuil_expose_est_celui_utilise_par_predict(client):  # T34
    seuil = client.get("/model-info").json()["seuil"]
    assert post(client, DOSSIER).json()["seuil"] == seuil


@pytest.mark.parametrize(("methode", "chemin"), [("get", "/predict"), ("post", "/health")])
def test_methode_non_autorisee(client, methode, chemin):  # T42
    assert getattr(client, methode)(chemin).status_code == 405


def test_route_inconnue(client):  # T42
    assert client.get("/inconnu").status_code == 404


# ---------- modèle indisponible (EX05, T13, T14) ----------


@pytest.fixture
def client_sans_modele(monkeypatch):
    def echec(*_args, **_kwargs):
        raise ModeleIndisponible("Modèle indisponible.")

    monkeypatch.setattr("app.main.charger_modele", echec)
    with TestClient(app) as c:
        yield c


def test_sans_modele_health_503(client_sans_modele):  # T13
    r = client_sans_modele.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "indisponible", "modele_charge": False}


def test_sans_modele_predict_503(client_sans_modele):  # T13
    r = client_sans_modele.post("/predict", json=DOSSIER)
    assert r.status_code == 503
    assert "erreur" in r.json()


def test_sans_modele_model_info_503(client_sans_modele):  # T13
    assert client_sans_modele.get("/model-info").status_code == 503


def test_demarrage_avec_fichier_modele_absent(monkeypatch, tmp_path):  # T14
    def charge_un_fichier_absent():
        return charger_modele(tmp_path / "absent.joblib", tmp_path / "absent.json")

    monkeypatch.setattr("app.main.charger_modele", charge_un_fichier_absent)
    with TestClient(app) as c:  # l'application démarre sans planter
        assert c.get("/health").status_code == 503


# ---------- seuil configurable (EX14, T35, T36) ----------


def test_seuil_configure_change_la_classe_pas_la_probabilite(monkeypatch):  # T35
    resultats = {}
    for seuil in ("0.0001", "0.9999"):
        monkeypatch.setenv("SEUIL_DECISION", seuil)
        with TestClient(app) as c:
            resultats[seuil] = post(c, DOSSIER).json()
    bas, haut = resultats["0.0001"], resultats["0.9999"]
    assert bas["prediction"] == 1
    assert haut["prediction"] == 0
    assert bas["probabilite_defaut"] == haut["probabilite_defaut"]
    assert bas["seuil"] == 0.0001


@pytest.mark.parametrize("seuil", ["0", "1", "-0.2", "1.5", "nan", "inf", "abc", ""])
def test_seuil_invalide_empeche_le_demarrage(monkeypatch, seuil):  # T36
    monkeypatch.setenv("SEUIL_DECISION", seuil)
    with pytest.raises(ValueError, match=r"(?i)seuil"), TestClient(app):
        pass
