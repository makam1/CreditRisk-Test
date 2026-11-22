"""Modèles candidats pour la non-régression (Activité 5).

Chaque candidat simule une évolution réaliste du modèle de référence :
- v1_reconstruit        : réentraînement à l'identique (doit être accepté) ;
- v2_regularise         : régularisation plus forte, seuil recalculé (évolution bénigne) ;
- v2_donnees_reduites   : entraîné sur 1 500 dossiers au lieu de 6 000 (dégradation modérée) ;
- v2_seuil_oublie       : modèle de référence avec le seuil par défaut 0,5 (régression grave) ;
- v2_sans_charge        : variable dérivée supprimée (contrat de l'API violé).

Usage : python -m scripts.candidats [--out-dir models/candidats]
"""

import argparse
import json
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.prediction import charger_modele
from app.preprocessing import CIBLE, VARIABLES_BRUTES, VARIABLES_MODELE, preprocess_data
from scripts.generate_data import generate
from scripts.regression import CHEMIN_META_REFERENCE, CHEMIN_REFERENCE
from scripts.train import SEED, choisir_seuil, separer


def _pipeline(c: float = 1.0) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "modele",
                LogisticRegression(class_weight="balanced", C=c, max_iter=1000, random_state=SEED),
            ),
        ]
    )


def construire_candidats() -> dict[str, tuple[Pipeline, dict]]:
    """Rend {nom: (pipeline, métadonnées)} ; déterministe."""
    train, val, _test = separer(generate(n=10_000, seed=42))
    x_val, y_val = preprocess_data(val), val[CIBLE]
    reference = charger_modele(CHEMIN_REFERENCE, CHEMIN_META_REFERENCE)

    def meta(nom: str, seuil: float, variables: list[str]) -> dict:
        return {
            "version_modele": nom,
            "seuil": seuil,
            "variables": variables,
            "domaine_entrainement": reference.meta["domaine_entrainement"],
        }

    def ajuste(df, c=1.0, colonnes=None):
        x = preprocess_data(df)
        colonnes = colonnes or VARIABLES_MODELE
        return _pipeline(c).fit(x[colonnes], df[CIBLE]), colonnes

    candidats = {}
    p, cols = ajuste(train)
    candidats["v1_reconstruit"] = (
        p,
        meta("v1_reconstruit", choisir_seuil(y_val, p.predict_proba(x_val[cols])[:, 1]), cols),
    )
    p, cols = ajuste(train, c=0.01)
    candidats["v2_regularise"] = (
        p,
        meta("v2_regularise", choisir_seuil(y_val, p.predict_proba(x_val[cols])[:, 1]), cols),
    )
    p, cols = ajuste(train.sample(1500, random_state=1))
    candidats["v2_donnees_reduites"] = (
        p,
        meta("v2_donnees_reduites", choisir_seuil(y_val, p.predict_proba(x_val[cols])[:, 1]), cols),
    )
    candidats["v2_seuil_oublie"] = (
        reference.pipeline,
        meta("v2_seuil_oublie", 0.5, list(reference.meta["variables"])),
    )
    cols = [c for c in VARIABLES_MODELE if c in VARIABLES_BRUTES]
    p, cols = ajuste(train, colonnes=cols)
    candidats["v2_sans_charge"] = (
        p,
        meta("v2_sans_charge", choisir_seuil(y_val, p.predict_proba(x_val[cols])[:, 1]), cols),
    )
    return candidats


def ecrire(dossier: Path) -> list[Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    chemins = []
    for nom, (pipeline, meta) in construire_candidats().items():
        chemin = dossier / f"{nom}.joblib"
        joblib.dump(pipeline, chemin)
        chemin.with_suffix(".json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        chemins.append(chemin)
    return chemins


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out-dir", default="models/candidats")
    for chemin in ecrire(Path(parser.parse_args().out_dir)):
        print(f"Candidat écrit : {chemin}")


if __name__ == "__main__":
    main()
