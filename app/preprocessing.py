"""Prétraitement : du dossier validé aux variables attendues par le modèle.

Le prétraitement est une fonction pure : il ne modifie jamais son entrée et garantit
des valeurs finies en sortie (sinon il lève une erreur explicite).
"""

import numpy as np
import pandas as pd

VARIABLES_BRUTES = [
    "age",
    "revenu_mensuel",
    "montant_credit",
    "duree_mois",
    "anciennete_activite",
]
VARIABLES_MODELE = [*VARIABLES_BRUTES, "charge_mensuelle"]
CIBLE = "defaut"


def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """Retourne les variables du modèle (ordre fixe) avec `charge_mensuelle`.

    charge_mensuelle = (montant_credit / duree_mois) / revenu_mensuel
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("preprocess_data attend un DataFrame pandas.")
    if df.empty:
        raise ValueError("Données vides : aucune ligne à prétraiter.")

    manquantes = [c for c in VARIABLES_BRUTES if c not in df.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes : {manquantes}")
    if CIBLE in df.columns:
        # la cible n'est jamais une variable d'entrée : on ne la propage pas
        df = df.drop(columns=[CIBLE])

    sortie = df[VARIABLES_BRUTES].astype("float64")  # copie : l'entrée n'est pas modifiée

    if not np.isfinite(sortie.to_numpy()).all():
        raise ValueError("Valeurs non finies (NaN ou infini) dans les variables d'entrée.")
    if (sortie["revenu_mensuel"] <= 0).any() or (sortie["duree_mois"] <= 0).any():
        raise ValueError("revenu_mensuel et duree_mois doivent être strictement positifs.")

    sortie["charge_mensuelle"] = (sortie["montant_credit"] / sortie["duree_mois"]) / sortie[
        "revenu_mensuel"
    ]

    if not np.isfinite(sortie.to_numpy()).all():
        raise ValueError("Le prétraitement a produit des valeurs non finies.")
    return sortie[VARIABLES_MODELE]


def dossier_vers_dataframe(dossier: dict) -> pd.DataFrame:
    """Transforme un dossier (dict) en DataFrame d'une ligne."""
    return pd.DataFrame([dossier])
