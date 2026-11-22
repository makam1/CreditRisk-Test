"""Validation du contrat de données d'un dossier de crédit.

Règles (voir reports/plan_de_test.md) : 5 champs obligatoires, aucun champ en trop,
types stricts (pas de conversion silencieuse : "250000" et True sont rejetés),
valeurs finies, intervalles autorisés, cohérence ancienneté <= âge.
Le dossier reçu n'est jamais modifié."""

import math
from numbers import Integral, Real

CHAMPS_OBLIGATOIRES = (
    "age",
    "revenu_mensuel",
    "montant_credit",
    "duree_mois",
    "anciennete_activite",
)

AGE_MIN, AGE_MAX = 18, 100
DUREE_MIN, DUREE_MAX = 1, 120
REVENU_MIN = 1_000
REVENU_MAX = 100_000_000
MONTANT_MAX = 10_000_000_000


class ErreurValidation(ValueError):
    """Dossier invalide. `erreurs` liste tous les problèmes détectés (champ, message)."""

    def __init__(self, erreurs: list[tuple[str, str]]):
        self.erreurs = erreurs
        resume = "; ".join(f"{champ} : {message}" for champ, message in erreurs)
        super().__init__(resume)


def _est_entier(valeur: object) -> bool:
    return isinstance(valeur, Integral) and not isinstance(valeur, bool)


def _est_reel(valeur: object) -> bool:
    return isinstance(valeur, Real) and not isinstance(valeur, bool)


def valider_dossier(dossier: dict) -> None:
    """Lève ErreurValidation si le dossier est invalide ; ne renvoie rien sinon."""
    if not isinstance(dossier, dict):
        raise ErreurValidation([("dossier", "doit être un objet (dictionnaire)")])

    erreurs: list[tuple[str, str]] = []

    for champ in dossier:
        if champ not in CHAMPS_OBLIGATOIRES:
            erreurs.append((str(champ), "champ non autorisé"))

    for champ in CHAMPS_OBLIGATOIRES:
        if champ not in dossier or dossier[champ] is None:
            erreurs.append((champ, "champ obligatoire absent"))

    def verifier_entier(champ: str, minimum: int, maximum: int) -> None:
        if champ in dossier and dossier[champ] is not None:
            valeur = dossier[champ]
            if not _est_entier(valeur):
                erreurs.append((champ, "doit être un entier"))
            elif not minimum <= valeur <= maximum:
                erreurs.append((champ, f"doit être compris entre {minimum} et {maximum}"))

    def verifier_reel(
        champ: str,
        strictement_positif: bool,
        minimum: float | None,
        maximum: float | None,
    ) -> None:
        if champ in dossier and dossier[champ] is not None:
            valeur = dossier[champ]
            if not _est_reel(valeur):
                erreurs.append((champ, "doit être numérique"))
            elif not isinstance(valeur, Integral) and not math.isfinite(valeur):
                erreurs.append((champ, "doit être fini (ni NaN, ni infini)"))
            elif strictement_positif and valeur <= 0:
                erreurs.append((champ, "doit être strictement positif"))
            elif not strictement_positif and valeur < 0:
                erreurs.append((champ, "ne peut pas être négatif"))
            elif minimum is not None and valeur < minimum:
                erreurs.append((champ, f"est inférieur à la borne de plausibilité ({minimum:,})"))
            elif maximum is not None and valeur > maximum:
                erreurs.append((champ, f"dépasse la borne de plausibilité ({maximum:,})"))

    verifier_entier("age", AGE_MIN, AGE_MAX)
    verifier_entier("duree_mois", DUREE_MIN, DUREE_MAX)
    verifier_reel("revenu_mensuel", True, REVENU_MIN, REVENU_MAX)
    verifier_reel("montant_credit", True, None, MONTANT_MAX)
    verifier_reel("anciennete_activite", False, None, None)

    # cohérence entre variables : on ne peut pas exercer une activité plus d'années qu'on n'a vécu
    en_erreur = {champ for champ, _ in erreurs}
    if not en_erreur & {"age", "anciennete_activite"}:
        if dossier["anciennete_activite"] > dossier["age"]:
            erreurs.append(("anciennete_activite", "ne peut pas dépasser l'âge"))

    if erreurs:
        raise ErreurValidation(erreurs)
