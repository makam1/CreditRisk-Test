"""Tests de non-régression (Activité 5) : référence figée, tolérances, détection de dégradations,
cohérence de la sauvegarde et du rechargement du modèle."""

import copy
import json
from pathlib import Path

import joblib
import numpy as np
import pytest

from app.prediction import Modele, charger_modele
from app.preprocessing import CIBLE, VARIABLES_MODELE, preprocess_data
from scripts import regression as reg
from scripts.candidats import construire_candidats, ecrire
from scripts.regression import ACCEPTER, INVESTIGUER, REJETER

TOL = reg.TOLERANCES


@pytest.fixture(scope="module")
def baseline():
    assert reg.CHEMIN_BASELINE.exists(), "baseline absente : python -m scripts.regression baseline"
    return reg.charger_baseline()


@pytest.fixture(scope="module")
def jeux():
    return reg.jeux_evaluation()


@pytest.fixture(scope="module")
def reference():
    return charger_modele()


@pytest.fixture(scope="module")
def candidats_ecrits(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("candidats")
    ecrire(dossier)
    return dossier


def comparer_candidat(dossier: Path, nom: str) -> dict:
    return reg.comparer(dossier / f"{nom}.joblib")


# ---------- la référence figée ----------


def test_baseline_contient_tout_ce_qu_il_faut_pour_reproduire(baseline):
    for cle in ("version_reference", "modele", "jeu_evaluation", "metriques_test", "tolerances"):
        assert cle in baseline
    assert baseline["modele"]["variables"] == VARIABLES_MODELE
    assert {"python", "scikit-learn", "numpy", "pandas"} <= set(baseline["bibliotheques"])
    assert baseline["metriques_test"]["n"] == baseline["jeu_evaluation"]["n"] == 2000


def test_tolerances_definies_dans_la_baseline_et_coherentes(baseline):
    assert baseline["tolerances"] == json.loads(json.dumps(TOL))  # figées avec la référence
    for accepter, investiguer in baseline["tolerances"]["baisse_max"].values():
        assert 0 < accepter < investiguer < 1
    assert baseline["tolerances"]["baisse_max"]["rappel"][0] <= 0.02  # le rappel prime


def test_la_baseline_ne_s_ecrase_pas_sans_force(tmp_path):
    cible = tmp_path / "baseline.json"
    reg.creer_baseline(chemin=cible)
    avant = cible.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError, match="--force"):
        reg.creer_baseline(chemin=cible)
    assert cible.read_text(encoding="utf-8") == avant
    reg.creer_baseline(chemin=cible, force=True)  # explicite : autorisé


def test_le_jeu_d_evaluation_est_celui_de_la_baseline(baseline, jeux):
    _val, test = jeux
    assert reg.empreinte(test) == baseline["jeu_evaluation"]["empreinte_sha256"]
    assert test[CIBLE].mean() == pytest.approx(baseline["jeu_evaluation"]["taux_defaut"])


def test_la_reference_rejouee_redonne_la_baseline(baseline, jeux, reference):
    _val, test = jeux
    metriques, _ = reg.evaluer(reference.pipeline, reference.seuil, test)
    for nom in ("rappel", "precision", "f1", "vp", "fp", "fn", "vn"):
        assert metriques[nom] == pytest.approx(baseline["metriques_test"][nom], abs=1e-4)
    assert reg.empreinte_modele(reference.pipeline) == baseline["modele"]["empreinte_parametres"]
    assert reference.seuil == baseline["modele"]["seuil"]

# ---------- règles de décision (tolérances) ----------


@pytest.mark.parametrize(
    ("baisse", "attendu"),
    [
        (-0.30, ACCEPTER),  # amélioration
        (0.0, ACCEPTER),
        (0.02, ACCEPTER),  # borne incluse
        (0.0201, INVESTIGUER),
        (0.05, INVESTIGUER),  # borne incluse
        (0.0501, REJETER),
        (0.50, REJETER),
    ],
)
def test_niveau_selon_la_baisse_de_rappel(baisse, attendu):
    accepter, investiguer = TOL["baisse_max"]["rappel"]
    assert reg.niveau_baisse(baisse, accepter, investiguer) == attendu


def metriques(rappel=0.87, precision=0.23, f1=0.37):
    return {"rappel": rappel, "precision": precision, "f1": f1}


def niveau_global(cand: dict, ref: dict | None = None) -> str:
    controles = reg.controles_metriques(ref or metriques(), cand, TOL)
    return reg.pire(c["niveau"] for c in controles)


def test_pas_de_regression_quand_rien_ne_change():
    assert niveau_global(metriques()) == ACCEPTER


def test_baisse_de_rappel_detectee():
    assert niveau_global(metriques(rappel=0.84)) == INVESTIGUER  # -0,03
    assert niveau_global(metriques(rappel=0.70)) == REJETER  # -0,17


def test_baisse_de_f1_detectee_meme_si_le_rappel_tient():
    assert niveau_global(metriques(f1=0.33)) == INVESTIGUER  # -0,04
    assert niveau_global(metriques(f1=0.20)) == REJETER


def test_baisse_de_precision_detectee_meme_si_le_rappel_tient():
    assert niveau_global(metriques(precision=0.17)) == INVESTIGUER  # -0,06
    assert niveau_global(metriques(precision=0.10)) == REJETER


def test_gain_trop_beau_pour_etre_vrai_declenche_une_investigation():
    assert niveau_global(metriques(f1=0.50)) == INVESTIGUER  # +0,13 : fuite possible ?


def test_la_pire_decision_l_emporte():
    assert reg.pire([ACCEPTER, INVESTIGUER, ACCEPTER]) == INVESTIGUER
    assert reg.pire([INVESTIGUER, REJETER, ACCEPTER]) == REJETER


def test_part_de_decisions_modifiees():
    base = np.zeros(100, dtype=bool)

    def niveau(nb_changes):
        cand = base.copy()
        cand[:nb_changes] = True
        return reg.controle_decisions(base, cand, TOL)["niveau"]

    assert niveau(0) == ACCEPTER
    assert niveau(5) == ACCEPTER  # 5 % inclus
    assert niveau(10) == INVESTIGUER
    assert niveau(30) == REJETER


# ---------- comparaisons de bout en bout (candidats construits par scripts.candidats) ----------


def test_la_reference_comparee_a_elle_meme_est_acceptee():
    resultat = reg.comparer(reg.CHEMIN_REFERENCE, reg.CHEMIN_META_REFERENCE)
    assert resultat["decision"] == ACCEPTER
    ecarts = {c["controle"]: c["ecart"] for c in resultat["controles"]}
    assert ecarts["décisions modifiées"] == 0.0


def test_reconstruction_a_l_identique_acceptee(candidats_ecrits):
    resultat = comparer_candidat(candidats_ecrits, "v1_reconstruit")
    assert resultat["decision"] == ACCEPTER


def test_evolution_benigne_acceptee(candidats_ecrits):
    assert comparer_candidat(candidats_ecrits, "v2_regularise")["decision"] == ACCEPTER


def test_donnees_reduites_demande_une_investigation(candidats_ecrits):
    resultat = comparer_candidat(candidats_ecrits, "v2_donnees_reduites")
    assert resultat["decision"] == INVESTIGUER
    assert {c["controle"] for c in resultat["controles"] if c["niveau"] == INVESTIGUER} >= {
        "rappel",
        "décisions modifiées",
    }


def test_seuil_oublie_rejete_car_le_rappel_s_effondre(candidats_ecrits):
    resultat = comparer_candidat(candidats_ecrits, "v2_seuil_oublie")
    assert resultat["decision"] == REJETER
    rejets = {c["controle"] for c in resultat["controles"] if c["niveau"] == REJETER}
    assert {"rappel", "exigence : rappel sur la validation"} <= rejets
    # le F1 monte alors que le modèle est moins bon pour le métier : garder le rappel comme critère
    f1 = next(c for c in resultat["controles"] if c["controle"] == "f1")
    assert f1["candidat"] > f1["reference"]


def test_contrat_de_variables_viole_rejete(candidats_ecrits):
    resultat = comparer_candidat(candidats_ecrits, "v2_sans_charge")
    assert resultat["decision"] == REJETER
    assert resultat["controles"][-1]["controle"] == "contrat : variables du modèle"


def test_candidat_illisible_rejete(tmp_path):
    (tmp_path / "x.joblib").write_bytes(b"pas un modele")
    (tmp_path / "x.json").write_text("{}", encoding="utf-8")
    assert reg.comparer(tmp_path / "x.joblib")["decision"] == REJETER

def test_fichier_reecrit_sans_changer_les_parametres_reste_accepte(reference, tmp_path):
    """Des octets différents ne sont pas une régression : seuls les paramètres comptent."""
    copie = tmp_path / "copie.joblib"
    joblib.dump(reference.pipeline, copie, compress=3)
    assert copie.read_bytes() != reg.CHEMIN_REFERENCE.read_bytes()
    assert reg.empreinte_modele(joblib.load(copie)) == reg.empreinte_modele(reference.pipeline)


def test_modele_de_reference_modifie_est_detecte(baseline, jeux, reference):
    _val, test = jeux
    modifie = copy.deepcopy(reference.pipeline)
    modifie[-1].coef_ = modifie[-1].coef_ * 1.01  # un seul paramètre légèrement changé
    candidat = Modele(pipeline=modifie, meta=reference.meta)
    controles = reg.controles_integrite(baseline, test, candidat)
    niveaux = {c["controle"]: c["niveau"] for c in controles}
    assert niveaux["intégrité : paramètres du modèle de référence"] == INVESTIGUER

def test_jeu_d_evaluation_modifie_rend_la_comparaison_douteuse(baseline, jeux, reference, tmp_path):
    _val, test = jeux
    controles = reg.controles_integrite(baseline, test.iloc[:-1], reference)  # un dossier en moins
    assert controles[0]["niveau"] == INVESTIGUER


# ---------- ligne de commande et codes de sortie ----------


def test_cli_codes_de_sortie(candidats_ecrits, tmp_path):
    def compare(nom):
        return reg.main(["compare", "--candidat", str(candidats_ecrits / f"{nom}.joblib")])

    assert compare("v1_reconstruit") == 0
    assert compare("v2_donnees_reduites") == 1
    assert compare("v2_seuil_oublie") == 2


def test_cli_ecrit_le_rapport(candidats_ecrits, tmp_path):
    rapport = tmp_path / "r.md"
    code = reg.main(
        ["compare", "--candidat", str(candidats_ecrits / "v2_seuil_oublie.joblib"),
         "--rapport", str(rapport)]
    )  # fmt: skip
    texte = rapport.read_text(encoding="utf-8")
    assert code == 2
    assert "Décision : REJETER" in texte
    assert "| rappel |" in texte


def test_cli_baseline_absente_ou_deja_figee(baseline, tmp_path, capsys):
    assert reg.main(["compare", "--candidat", "x.joblib", "--baseline", str(tmp_path / "n")]) == 3
    assert reg.main(["baseline"]) == 3  # la baseline du dépôt existe déjà : refus sans --force
    assert "--force" in capsys.readouterr().err


# ---------- cohérence sauvegarde / rechargement ----------


def test_rechargement_identique_octet_pour_octet(reference, jeux, tmp_path):
    _val, test = jeux
    x = preprocess_data(test)
    joblib.dump(reference.pipeline, tmp_path / "copie.joblib")
    recharge = joblib.load(tmp_path / "copie.joblib")
    np.testing.assert_array_equal(
        recharge.predict_proba(x)[:, 1], reference.pipeline.predict_proba(x)[:, 1]
    )


def test_seuil_conserve_sans_perte_dans_le_json(reference):  # anomalie A09
    brut = json.loads(Path(reg.CHEMIN_META_REFERENCE).read_text(encoding="utf-8"))["seuil"]
    assert brut == reference.seuil
    assert json.loads(json.dumps(brut)) == brut  # aller-retour exact


def test_le_modele_sauvegarde_tient_l_exigence_de_rappel_sur_la_validation(jeux, reference):
    val, _test = jeux
    rappel = reg.evaluer(reference.pipeline, reference.seuil, val)[0]["rappel"]
    assert rappel >= reg.RAPPEL_MIN  # anomalie A09 : le seuil arrondi donnait 0,848
    assert rappel == pytest.approx(reference.meta["metriques_validation"]["rappel"], abs=1e-4)


def test_candidats_deterministes():
    a = construire_candidats()["v2_regularise"][1]["seuil"]
    b = construire_candidats()["v2_regularise"][1]["seuil"]
    assert a == b
