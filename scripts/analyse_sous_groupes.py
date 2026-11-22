# ruff: noqa: E501
"""Analyse des faux négatifs par profil de demandeur (Activité 7, question de synthèse).

Un rappel global correct peut cacher des profils pour lesquels le modèle laisse passer presque tous
les défauts. Ce script découpe le jeu de test (celui de la baseline) en tranches fixes, puis donne
pour chacune : effectif, défauts réels, faux négatifs, taux de faux négatifs avec intervalle de
confiance à 95 % (méthode de Wilson) et taux d'alerte.

Règle : une tranche contenant au moins MIN_DEFAUTS défauts est SIGNALÉE si son taux de faux
négatifs dépasse FNR_MAX_PAR_GROUPE. Sous MIN_DEFAUTS, on ne conclut pas (trop peu de défauts).

Usage : python -m scripts.analyse_sous_groupes [--rapport reports/analyse_sous_groupes.md]
Code de sortie : 0 si aucune tranche signalée, 1 sinon.
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.prediction import charger_modele
from app.preprocessing import CIBLE, preprocess_data
from scripts.regression import CHEMIN_META_REFERENCE, CHEMIN_REFERENCE, jeux_evaluation

FNR_MAX_PAR_GROUPE = 0.30  # fixé avant l'analyse : un peu plus de 2 fois le taux global (0,13)
MIN_DEFAUTS = 10  # en dessous, l'intervalle est trop large pour conclure

INF = float("inf")
# variable -> (bornes [min, max[ , étiquettes). Tranches FIXES, choisies avant de voir les résultats.
TRANCHES = {
    "age": ([18, 26, 36, 51, 101], ["18-25", "26-35", "36-50", "51+"]),
    "revenu_mensuel": (
        [0, 100_000, 200_000, 350_000, INF],
        ["< 100 000", "100 000-200 000", "200 000-350 000", "≥ 350 000"],
    ),
    "montant_credit": (
        [0, 750_000, 1_500_000, 3_000_000, INF],
        ["< 0,75 M", "0,75-1,5 M", "1,5-3 M", "≥ 3 M"],
    ),
    "duree_mois": ([0, 13, 25, 37, 121], ["6-12 mois", "13-24 mois", "25-36 mois", "37-48 mois"]),
    "anciennete_activite": ([0, 2, 5, 10, 101], ["< 2 ans", "2-5 ans", "5-10 ans", "≥ 10 ans"]),
    "charge_mensuelle": (
        [0, 0.05, 0.10, 0.20, INF],
        ["< 0,05", "0,05-0,10", "0,10-0,20", "≥ 0,20"],
    ),
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance de Wilson pour une proportion k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    demi = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - demi), min(1.0, centre + demi))


def analyser(donnees: pd.DataFrame, decisions: np.ndarray) -> pd.DataFrame:
    """Une ligne par tranche. `donnees` contient les variables brutes, charge_mensuelle et `defaut`."""
    lignes = []
    for variable, (bornes, etiquettes) in TRANCHES.items():
        tranche = pd.cut(donnees[variable], bins=bornes, labels=etiquettes, right=False)
        for etiquette in etiquettes:
            masque = (tranche == etiquette).to_numpy()
            n = int(masque.sum())
            defauts = int((masque & (donnees[CIBLE].to_numpy() == 1)).sum())
            manques = int((masque & (donnees[CIBLE].to_numpy() == 1) & ~decisions).sum())
            fnr = manques / defauts if defauts else float("nan")
            bas, haut = wilson(manques, defauts)
            lignes.append(
                {
                    "variable": variable,
                    "tranche": etiquette,
                    "effectif": n,
                    "defauts": defauts,
                    "faux_negatifs": manques,
                    "fnr": fnr,
                    "fnr_bas": bas,
                    "fnr_haut": haut,
                    "taux_alerte": float(decisions[masque].mean()) if n else float("nan"),
                    "signalee": defauts >= MIN_DEFAUTS and fnr > FNR_MAX_PAR_GROUPE,
                    "non_concluant": defauts < MIN_DEFAUTS,
                }
            )
    return pd.DataFrame(lignes)


def jeu_de_test_avec_decisions() -> tuple[pd.DataFrame, np.ndarray]:
    modele = charger_modele(CHEMIN_REFERENCE, CHEMIN_META_REFERENCE)
    _val, test = jeux_evaluation()
    x = preprocess_data(test)
    decisions = modele.pipeline.predict_proba(x)[:, 1] >= modele.seuil
    donnees = test.assign(charge_mensuelle=x["charge_mensuelle"].to_numpy())
    return donnees, decisions


def rediger(resultat: pd.DataFrame, donnees: pd.DataFrame, decisions: np.ndarray) -> str:
    defauts = int((donnees[CIBLE] == 1).sum())
    manques = int(((donnees[CIBLE] == 1).to_numpy() & ~decisions).sum())
    lignes = [
        "## Faux négatifs par profil (jeu de test, modèle de référence)",
        "",
        f"Global : {manques} faux négatifs sur {defauts} défauts réels, "
        f"soit un taux de faux négatifs de {manques / defauts:.1%} (rappel {1 - manques / defauts:.1%}).",
        f"Règle : tranche signalée si elle compte au moins {MIN_DEFAUTS} défauts et que son taux "
        f"de faux négatifs dépasse {FNR_MAX_PAR_GROUPE:.0%}. Intervalle de confiance à 95 % (Wilson).",
        "",
        "| Variable | Tranche | Dossiers | Défauts | Faux négatifs | Taux de FN | IC 95 % | Taux d'alerte | Verdict |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in resultat.itertuples():
        verdict = "SIGNALÉE" if r.signalee else ("non concluant" if r.non_concluant else "ok")
        fnr = "-" if r.defauts == 0 else f"{r.fnr:.1%}"
        ic = f"{r.fnr_bas:.0%}-{r.fnr_haut:.0%}" if r.defauts else "-"
        lignes.append(
            f"| {r.variable} | {r.tranche} | {r.effectif} | {r.defauts} | {r.faux_negatifs} "
            f"| {fnr} | {ic} | {r.taux_alerte:.1%} | {verdict} |"
        )
    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rapport")
    args = parser.parse_args(argv)
    donnees, decisions = jeu_de_test_avec_decisions()
    resultat = analyser(donnees, decisions)
    texte = rediger(resultat, donnees, decisions)
    if args.rapport:
        Path(args.rapport).parent.mkdir(parents=True, exist_ok=True)
        Path(args.rapport).write_text(texte, encoding="utf-8")
    signalees = resultat[resultat["signalee"]]
    for r in signalees.itertuples():
        print(
            f"[SIGNALÉE] {r.variable} {r.tranche} : {r.faux_negatifs}/{r.defauts} défauts manqués ({r.fnr:.0%})"
        )
    print(f"{len(signalees)} tranche(s) signalée(s) sur {len(resultat)}.")
    return 1 if len(signalees) else 0


if __name__ == "__main__":
    sys.exit(main())
