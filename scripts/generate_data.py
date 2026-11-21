"""Génère un jeu de données SYNTHÉTIQUE de demandes de crédit (FCFA).

Les données servent uniquement à tester le système. Elles ne permettent pas
de démontrer la performance réelle d'un modèle de crédit : la relation entre
variables et défaut est inventée (voir data/README.md).

Usage : python scripts/generate_data.py [--n 10000] [--seed 42] [--output data/credit_synthetic.csv]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_N = 10_000
DEFAULT_SEED = 42
DEFAULT_OUTPUT = "data/credit_synthetic.csv"


def generate(n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> pd.DataFrame:
    """Retourne n demandes synthétiques, de façon déterministe pour une graine donnée."""
    if n <= 0:
        raise ValueError("n doit être strictement positif.")
    rng = np.random.default_rng(seed)

    age = rng.integers(18, 71, size=n)
    revenu = np.round(rng.lognormal(mean=12.3, sigma=0.5, size=n), -3)
    revenu = np.clip(revenu, 50_000, 3_000_000)
    duree = rng.choice([6, 12, 18, 24, 36, 48], size=n)
    montant = np.round(revenu * rng.uniform(1.0, 12.0, size=n), -4)
    montant = np.clip(montant, 50_000, None)
    anciennete = np.round(np.minimum(rng.gamma(2.0, 2.5, size=n), age - 16), 1)

    # Défaut simulé : plus la mensualité pèse sur le revenu, plus le risque monte ;
    # l'ancienneté d'activité le réduit. Bruit logistique ajouté.
    charge = (montant / duree) / revenu
    logit = -3.2 + 3.0 * charge - 0.10 * anciennete - 0.01 * (age - 35)
    proba = 1.0 / (1.0 + np.exp(-logit))
    defaut = (rng.random(n) < proba).astype(int)

    return pd.DataFrame(
        {
            "age": age,
            "revenu_mensuel": revenu,
            "montant_credit": montant,
            "duree_mois": duree,
            "anciennete_activite": anciennete,
            "defaut": defaut,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    df = generate(args.n, args.seed)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df)} lignes écrites dans {out} (graine {args.seed})")
    print(f"Taux de défaut : {df['defaut'].mean():.3f}")
    print(df.describe().round(1).to_string())


if __name__ == "__main__":
    main()
