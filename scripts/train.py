"""Entraîne le modèle de test et le sauvegarde (models/model_v1.joblib + .json).

- séparation stratifiée 60 / 20 / 20 AVANT tout ajustement (graine fixe) ;
- scaler et régression logistique ajustés sur l'entraînement uniquement ;
- seuil choisi sur la VALIDATION : précision maximale sous contrainte de rappel >= 0,85 ;
- le jeu de test n'est pas utilisé ici.

Usage : python -m scripts.train [--data data/credit_synthetic.csv] [--version v1]
"""

import argparse
import hashlib
import json
import platform
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_recall_curve, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.preprocessing import CIBLE, VARIABLES_BRUTES, preprocess_data

SEED = 42
RAPPEL_MIN = 0.85


def charger_donnees(chemin: Path) -> pd.DataFrame:
    if not chemin.exists():
        raise FileNotFoundError(
            f"Données introuvables : {chemin}. Lancez : python scripts/generate_data.py"
        )
    df = pd.read_csv(chemin)
    manquantes = [c for c in [*VARIABLES_BRUTES, CIBLE] if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans {chemin} : {manquantes}")
    if not set(df[CIBLE].unique()) <= {0, 1}:
        raise ValueError("La cible doit valoir 0 ou 1.")
    return df


def separer(df: pd.DataFrame, seed: int = SEED):
    """60 / 20 / 20 stratifié, avant tout ajustement."""
    train, reste = train_test_split(df, test_size=0.4, stratify=df[CIBLE], random_state=seed)
    val, test = train_test_split(reste, test_size=0.5, stratify=reste[CIBLE], random_state=seed)
    return train, val, test


def construire_pipeline(seed: int = SEED) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "modele",
                LogisticRegression(class_weight="balanced", max_iter=1000, random_state=seed),
            ),
        ]
    )


def choisir_seuil(y_val, proba_val, rappel_min: float = RAPPEL_MIN) -> float:
    """Seuil de précision maximale parmi ceux qui garantissent rappel >= rappel_min (validation).

    precision_recall_curve renvoie une probabilité observée comme seuil : la décision du dossier
    situé exactement sur ce seuil dépendrait alors du moindre arrondi (anomalie A09). On retourne
    donc le milieu entre ce seuil et la probabilité observée immédiatement en dessous : mêmes
    décisions sur la validation, avec une marge de sécurité.
    """
    proba_val = np.asarray(proba_val, dtype=float)
    precision, rappel, seuils = precision_recall_curve(y_val, proba_val)
    # precision/rappel ont un point de plus que seuils
    points = zip(precision[:-1], rappel[:-1], seuils, strict=True)
    ok = [(p, t) for p, r, t in points if r >= rappel_min]
    if not ok:
        raise ValueError(f"Aucun seuil n'atteint un rappel de {rappel_min} sur la validation.")
    choisi = float(max(ok)[1])
    en_dessous = proba_val[proba_val < choisi]
    return float((choisi + en_dessous.max()) / 2) if en_dessous.size else choisi

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/credit_synthetic.csv")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--out-dir", default="models")
    args = parser.parse_args()

    chemin = Path(args.data)
    df = charger_donnees(chemin)
    train, val, _test = separer(df)

    x_train, y_train = preprocess_data(train), train[CIBLE]
    x_val, y_val = preprocess_data(val), val[CIBLE]

    pipeline = construire_pipeline().fit(x_train, y_train)
    proba_val = pipeline.predict_proba(x_val)[:, 1]
    seuil = choisir_seuil(y_val, proba_val)
    pred_val = (proba_val >= seuil).astype(int)

    metriques = {
        "rappel": round(float(recall_score(y_val, pred_val)), 4),
        "precision": round(float(precision_score(y_val, pred_val, zero_division=0)), 4),
        "f1": round(float(f1_score(y_val, pred_val, zero_division=0)), 4),
    }

    domaine = {c: [float(train[c].min()), float(train[c].max())] for c in VARIABLES_BRUTES}
    meta = {
        "version_modele": args.version,
        "date_entrainement": datetime.now(UTC).strftime("%Y-%m-%d"),
        "graine": SEED,
        "variables": list(x_train.columns),
        "seuil": seuil,
        "rappel_min_vise": RAPPEL_MIN,
        "metriques_validation": metriques,
        "domaine_entrainement": domaine,
        "tailles": {"train": len(train), "validation": len(val)},
        "donnees_sha256": hashlib.sha256(chemin.read_bytes()).hexdigest(),
        "bibliotheques": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
    }

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, out / f"model_{args.version}.joblib")
    (out / f"model_{args.version}.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Modèle sauvegardé : {out / f'model_{args.version}.joblib'}")
    print(f"Seuil (choisi sur la validation) : {seuil:.4f}")
    print(f"Métriques validation : {metriques}")


if __name__ == "__main__":
    main()
