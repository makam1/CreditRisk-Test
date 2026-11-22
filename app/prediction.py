"""Chargement du modèle et prédiction du risque de défaut.

Les journaux ne contiennent jamais les valeurs du dossier (données personnelles) :
seulement le type de l'erreur. Les exceptions levées ici portent des messages génériques,
adaptés à une réponse API sans trace technique.
"""

import json
import logging
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path

import joblib

from app.preprocessing import dossier_vers_dataframe, preprocess_data
from app.validation import valider_dossier

logger = logging.getLogger(__name__)

CHEMIN_MODELE = Path("models/model_v1.joblib")
CHEMIN_META = Path("models/model_v1.json")
CLES_META = ("version_modele", "seuil", "variables", "domaine_entrainement")


class ModeleIndisponible(Exception):
    """Le modèle n'a pas pu être chargé (absent, corrompu ou métadonnées invalides)."""


class ErreurPrediction(Exception):
    """Erreur interne de prétraitement ou de prédiction (message volontairement générique)."""


@dataclass(frozen=True)
class Modele:
    pipeline: object
    meta: dict

    @property
    def version(self) -> str:
        return self.meta["version_modele"]

    @property
    def seuil(self) -> float:
        return self.meta["seuil"]


def valider_seuil(seuil: object) -> float:
    """Le seuil doit être un réel fini strictement compris entre 0 et 1."""
    if isinstance(seuil, bool) or not isinstance(seuil, Real) or not math.isfinite(seuil):
        raise ValueError("Le seuil doit être un nombre fini.")
    if not 0.0 < seuil < 1.0:
        raise ValueError("Le seuil doit être strictement compris entre 0 et 1.")
    return float(seuil)


def charger_modele(
    chemin_modele: Path = CHEMIN_MODELE, chemin_meta: Path = CHEMIN_META
) -> Modele:
    """Charge le pipeline et ses métadonnées ; lève ModeleIndisponible au moindre problème."""
    try:
        pipeline = joblib.load(chemin_modele)
        meta = json.loads(Path(chemin_meta).read_text(encoding="utf-8"))
        manquantes = [cle for cle in CLES_META if cle not in meta]
        if manquantes:
            raise KeyError(f"métadonnées incomplètes : {manquantes}")
        valider_seuil(meta["seuil"])
        if not hasattr(pipeline, "predict_proba"):
            raise TypeError("l'objet chargé n'est pas un modèle de classification")
    except Exception as exc:
        logger.error("Chargement du modèle impossible (%s)", type(exc).__name__)
        raise ModeleIndisponible("Modèle indisponible.") from exc
    return Modele(pipeline=pipeline, meta=meta)


def avertissements_domaine(dossier: dict, domaine: dict) -> list[str]:
    """Signale les variables hors de la plage d'entraînement (entrée valide mais inhabituelle)."""
    avertissements = []
    for champ, (minimum, maximum) in domaine.items():
        valeur = dossier[champ]
        if valeur < minimum or valeur > maximum:
            avertissements.append(
                f"{champ} hors du domaine d'entraînement [{minimum:g} ; {maximum:g}] : "
                "prédiction moins fiable."
            )
    return avertissements


def predire(modele: Modele, dossier: dict, seuil: float | None = None) -> dict:
    """Valide le dossier, prédit la probabilité de défaut et applique le seuil.

    Lève ErreurValidation (dossier invalide, avant tout appel au modèle),
    ValueError (seuil invalide) ou ErreurPrediction (erreur interne).
    """
    valider_dossier(dossier)
    seuil_utilise = valider_seuil(modele.seuil if seuil is None else seuil)

    try:
        x = preprocess_data(dossier_vers_dataframe(dossier))
        probabilite = float(modele.pipeline.predict_proba(x)[0, 1])
    except Exception as exc:
        logger.error("Échec de la prédiction (%s)", type(exc).__name__)
        raise ErreurPrediction("Erreur interne de prédiction.") from exc

    if not math.isfinite(probabilite) or not 0.0 <= probabilite <= 1.0:
        logger.error("Probabilité hors contrat produite par le modèle")
        raise ErreurPrediction("Erreur interne de prédiction.")

    return {
        "prediction": int(probabilite >= seuil_utilise),
        "probabilite_defaut": probabilite,
        "seuil": seuil_utilise,
        "version_modele": modele.version,
        "avertissements": avertissements_domaine(dossier, modele.meta["domaine_entrainement"]),
    }
