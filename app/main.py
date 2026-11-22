"""API de prédiction du risque de défaut (FastAPI).

Contrat : voir reports/plan_de_test.md, section 3.
- 422 pour toute entrée invalide (JSON mal formé compris), sans conversion silencieuse ;
- 503 quand le modèle n'est pas chargé ;
- 500 générique (sans trace ni donnée personnelle) pour toute erreur interne.
Les journaux ne contiennent jamais les valeurs d'un dossier.
"""

import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.prediction import ErreurPrediction, charger_modele, predire, valider_seuil
from app.validation import ErreurValidation

logger = logging.getLogger("creditrisk.api")

EXEMPLE_DOSSIER = {
    "age": 35,
    "revenu_mensuel": 250000,
    "montant_credit": 1000000,
    "duree_mois": 12,
    "anciennete_activite": 4,
}
SCHEMA_DOSSIER = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": list(EXEMPLE_DOSSIER),
                    "additionalProperties": False,
                    "properties": {
                        "age": {"type": "integer", "minimum": 18, "maximum": 100},
                        "revenu_mensuel": {"type": "number", "minimum": 1000, "maximum": 1e8},
                        "montant_credit": {"type": "number", "exclusiveMinimum": 0},
                        "duree_mois": {"type": "integer", "minimum": 1, "maximum": 120},
                        "anciennete_activite": {"type": "number", "minimum": 0},
                    },
                    "example": EXEMPLE_DOSSIER,
                }
            }
        },
    }
}


def lire_seuil_configure() -> float | None:
    """Seuil optionnel fixé par la variable d'environnement SEUIL_DECISION.

    Un seuil invalide empêche le démarrage (échec explicite plutôt que seuil caché).
    """
    brut = os.environ.get("SEUIL_DECISION")
    if brut is None:
        return None
    try:
        valeur = float(brut)
    except ValueError as exc:
        raise ValueError("SEUIL_DECISION doit être un nombre.") from exc
    return valider_seuil(valeur)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.seuil_configure = lire_seuil_configure()
    app.state.modele = None
    try:
        app.state.modele = charger_modele()
    except Exception as exc:  # le service démarre en état « indisponible »
        logger.error("Démarrage sans modèle (%s)", type(exc).__name__)
    yield


app = FastAPI(
    title="CreditRisk-Test : API de score de risque de défaut",
    description=(
        "Prototype de test. Modèle entraîné sur des données SYNTHÉTIQUES : "
        "les résultats ne reflètent pas la performance réelle d'un modèle de crédit."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


def reponse_erreur(code: int, message: str, details: list[dict] | None = None) -> JSONResponse:
    corps: dict = {"erreur": message}
    if details is not None:
        corps["details"] = details
    return JSONResponse(status_code=code, content=corps)


def modele_indisponible() -> JSONResponse:
    return reponse_erreur(503, "Service indisponible : modèle non chargé.")


def seuil_effectif(app: FastAPI) -> float:
    if app.state.seuil_configure is not None:
        return app.state.seuil_configure
    return app.state.modele.seuil


@app.get("/health")
async def health(request: Request):
    if request.app.state.modele is None:
        return JSONResponse(
            status_code=503, content={"status": "indisponible", "modele_charge": False}
        )
    return {"status": "ok", "modele_charge": True}


@app.get("/model-info")
async def model_info(request: Request):
    modele = request.app.state.modele
    if modele is None:
        return modele_indisponible()
    meta = modele.meta
    return {
        "version_modele": modele.version,
        "seuil": seuil_effectif(request.app),
        "variables": meta["variables"],
        "date_entrainement": meta.get("date_entrainement"),
        "metriques_reference": meta.get("metriques_validation"),
        "domaine_entrainement": meta["domaine_entrainement"],
        "donnees": "synthétiques (test uniquement)",
    }


@app.post("/predict", openapi_extra=SCHEMA_DOSSIER)
async def predict(request: Request):
    modele = request.app.state.modele
    if modele is None:
        return modele_indisponible()

    try:
        dossier = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
        logger.info("Requête rejetée : JSON mal formé")
        return reponse_erreur(
            422, "Corps de requête invalide.", [{"champ": "corps", "message": "JSON mal formé"}]
        )

    try:
        return predire(modele, dossier, seuil=seuil_effectif(request.app))
    except ErreurValidation as exc:
        logger.info("Requête rejetée : %d erreur(s) de validation", len(exc.erreurs))
        details = [{"champ": champ, "message": message} for champ, message in exc.erreurs]
        return reponse_erreur(422, "Données invalides.", details)
    except ErreurPrediction:
        return reponse_erreur(500, "Erreur interne.")
    except Exception as exc:
        logger.error("Erreur inattendue (%s)", type(exc).__name__)
        return reponse_erreur(500, "Erreur interne.")
