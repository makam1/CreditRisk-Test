"""Tests de robustesse (Activité 4) : entrées invalides, limites, inhabituelles, schéma incorrect.

Règle de décision : une entrée INVALIDE est rejetée (422, aucune prédiction) ; une entrée
valide mais INHABITUELLE (hors du domaine d'entraînement) est traitée (200) avec un avertissement.
"""

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.main import app

DOSSIER = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}
CHAMPS = list(DOSSIER)
JSON_HEADERS = {"content-type": "application/json"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def sans(*champs):
    return {k: v for k, v in DOSSIER.items() if k not in champs}


def avec(**modifs):
    return {**DOSSIER, **modifs}


# (id, description, corps, comportement attendu)
SCENARIOS = [
    ("R01", "valeur manquante : revenu absent", sans("revenu_mensuel"), "rejet"),
    ("R02", "plusieurs valeurs manquantes", sans("age", "duree_mois", "montant_credit"), "rejet"),
    ("R03", "valeur null", avec(age=None), "rejet"),
    ("R04", "texte non numérique", avec(revenu_mensuel="abc"), "rejet"),
    ("R05", "booléen à la place d'un nombre", avec(montant_credit=True), "rejet"),
    ("R06", "liste à la place d'un nombre", avec(duree_mois=[12]), "rejet"),
    ("R07", "objet à la place d'un nombre", avec(age={"valeur": 35}), "rejet"),
    ("R08", "schéma incorrect : noms anglais", {"income": 250000, "age": 35}, "rejet"),
    ("R09", "schéma incorrect : liste de dossiers", [DOSSIER], "rejet"),
    ("R10", "schéma incorrect : champ en trop", avec(sexe="F"), "rejet"),
    ("R11", "âge juste sous la limite (17)", avec(age=17), "rejet"),
    ("R12", "ancienneté supérieure à l'âge", avec(age=20, anciennete_activite=30), "rejet"),
    ("R13", "âge limite basse (18)", avec(age=18, anciennete_activite=0), "traite"),
    ("R14", "âge limite haute (100), hors domaine", avec(age=100), "alerte"),
    ("R15", "revenu minimal autorisé (1 000)", avec(revenu_mensuel=1000), "alerte"),
    ("R16", "revenu maximal autorisé (1e8)", avec(revenu_mensuel=100_000_000), "alerte"),
    ("R17", "durée limite basse (1)", avec(duree_mois=1), "alerte"),
    ("R18", "durée limite haute (120)", avec(duree_mois=120), "alerte"),
    ("R19", "montant très éloigné de l'entraînement", avec(montant_credit=5 * 10**9), "alerte"),
    ("R20", "ancienneté nulle", avec(anciennete_activite=0), "traite"),
]


@pytest.mark.parametrize(
    ("ident", "description", "corps", "attendu"),
    SCENARIOS,
    ids=[s[0] for s in SCENARIOS],
)
def test_scenario(client, ident, description, corps, attendu):
    r = client.post("/predict", json=corps)
    if attendu == "rejet":
        assert r.status_code == 422, description
        assert "prediction" not in r.json()
    else:
        assert r.status_code == 200, description
        resultat = r.json()
        assert 0.0 <= resultat["probabilite_defaut"] <= 1.0
        if attendu == "alerte":
            assert resultat["avertissements"], f"{description} : avertissement attendu"
        else:
            assert resultat["avertissements"] == [], description


@pytest.mark.parametrize("valeur", ["NaN", "Infinity", "-Infinity"])
@pytest.mark.parametrize("champ", ["revenu_mensuel", "montant_credit", "anciennete_activite"])
def test_valeurs_non_finies_dans_chaque_champ_numerique(client, champ, valeur):
    corps = {**DOSSIER, champ: "__V__"}
    contenu = (
        "{"
        + ", ".join(f'"{k}": {valeur if v == "__V__" else v}' for k, v in corps.items())
        + "}"
    )
    r = client.post("/predict", content=contenu, headers=JSON_HEADERS)
    assert r.status_code == 422


def test_entier_gigantesque_rejete_proprement(client):  # anomalie A03
    contenu = (
        '{"age": 35, "revenu_mensuel": 1' + "0" * 400 + ', "montant_credit": 1000000, '
        '"duree_mois": 12, "anciennete_activite": 4}'
    )
    r = client.post("/predict", content=contenu, headers=JSON_HEADERS)
    assert r.status_code == 422


def test_json_profondement_imbrique_rejete_proprement(client):  # anomalie A05
    contenu = "[" * 100_000 + "]" * 100_000
    r = client.post("/predict", content=contenu, headers=JSON_HEADERS)
    assert r.status_code == 422
    assert "erreur" in r.json()


@pytest.mark.xfail(
    strict=True,
    reason="A06 (ouverte) : l'API n'impose aucune taille maximale au corps de requête",
)
def test_corps_trop_volumineux_refuse_avec_413(client):
    corps = {**DOSSIER, "commentaire": "a" * 2_000_000}
    assert client.post("/predict", json=corps).status_code == 413


# ---------- fuzzing : aucune entrée JSON ne doit provoquer d'erreur 500 ----------

scalaires = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.integers(min_value=10**300, max_value=10**400),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=20),
)
valeurs_json = st.recursive(
    scalaires,
    lambda enfants: st.one_of(
        st.lists(enfants, max_size=3),
        st.dictionaries(st.text(max_size=5), enfants, max_size=3),
    ),
    max_leaves=5,
)
corps_aleatoires = st.dictionaries(
    st.sampled_from([*CHAMPS, "autre"]), valeurs_json, max_size=6
)


@settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(corps=corps_aleatoires)
def test_aucune_entree_json_ne_provoque_d_erreur_500(client, corps):
    r = client.post("/predict", json=corps)
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert 0.0 <= r.json()["probabilite_defaut"] <= 1.0
    else:
        assert "erreur" in r.json()
