"""Non-régression (Activité 5) : compare un modèle candidat à la version de référence figée.

Principe
- La RÉFÉRENCE est figée dans reports/baseline.json, créée une seule fois (--force pour la refaire).
- Les TOLÉRANCES sont écrites dans la baseline AVANT toute comparaison : on ne les ajuste pas
  après avoir vu le résultat d'un candidat.
- Le JEU D'ÉVALUATION est fixe (partition test du jeu synthétique, graine 42) et vérifié par
  empreinte : un jeu qui change rend la comparaison invalide.
- Décision : ACCEPTER, INVESTIGUER ou REJETER (le pire niveau parmi tous les contrôles).

Usage :
    python -m scripts.regression baseline [--force]
    python -m scripts.regression compare --candidat models/candidats/x.joblib [--rapport f.md]
Codes de sortie de `compare` : 0 = ACCEPTER, 1 = INVESTIGUER, 2 = REJETER.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from app.prediction import ModeleIndisponible, charger_modele
from app.preprocessing import CIBLE, VARIABLES_MODELE, preprocess_data
from scripts.generate_data import generate
from scripts.train import RAPPEL_MIN, separer

CHEMIN_BASELINE = Path("reports/baseline.json")
CHEMIN_REFERENCE = Path("models/model_v1.joblib")
CHEMIN_META_REFERENCE = Path("models/model_v1.json")
N_LIGNES, GRAINE = 10_000, 42

ACCEPTER, INVESTIGUER, REJETER = "ACCEPTER", "INVESTIGUER", "REJETER"
RANG = {ACCEPTER: 0, INVESTIGUER: 1, REJETER: 2}
CODE_SORTIE = RANG

# Tolérances (baisse absolue par rapport à la référence) : [accepter jusqu'à, investiguer jusqu'à].
# Au-delà de la seconde valeur : REJETER. Choisies avec le métier AVANT la première comparaison :
# le rappel (défauts détectés) est l'exigence principale, donc la tolérance la plus serrée.
TOLERANCES = {
    "baisse_max": {"rappel": [0.02, 0.05], "f1": [0.02, 0.05], "precision": [0.03, 0.08]},
    "decisions_modifiees_max": [0.05, 0.15],  # part des dossiers dont la décision change
    "hausse_suspecte": 0.10,  # un gain aussi fort est suspect (fuite de données ?) : investiguer
    "rappel_validation_min": RAPPEL_MIN,  # exigence métier, recalculée sur la validation
    "ecart_integrite": 1e-4,  # la référence doit reproduire la baseline à cette précision près
}


# ---------- jeux et métriques ----------


def jeux_evaluation() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validation et test, reconstruits de façon déterministe (graine fixe, sans fichier CSV)."""
    _train, val, test = separer(generate(n=N_LIGNES, seed=GRAINE))
    return val, test


def empreinte(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv().encode("utf-8")).hexdigest()


def empreinte_fichier(chemin: Path) -> str:
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def evaluer(pipeline, seuil: float, df: pd.DataFrame) -> tuple[dict, np.ndarray]:
    """Métriques de classification et décisions (booléens) d'un modèle sur un jeu."""
    y = df[CIBLE].to_numpy() == 1
    proba = pipeline.predict_proba(preprocess_data(df))[:, 1]
    decisions = proba >= seuil
    tp = int((decisions & y).sum())
    fp = int((decisions & ~y).sum())
    fn = int((~decisions & y).sum())
    tn = int((~decisions & ~y).sum())
    rappel = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    metriques = {
        "n": len(df),
        "rappel": round(rappel, 6),
        "precision": round(precision, 6),
        "f1": round(f1, 6),
        "taux_alerte": round(float(decisions.mean()), 6),
        "vp": tp,
        "fp": fp,
        "fn": fn,
        "vn": tn,
    }
    return metriques, decisions


# ---------- baseline ----------


def _commit() -> str | None:
    try:
        sortie = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
        )
        return sortie.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def versions_bibliotheques() -> dict:
    return {
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }


def creer_baseline(
    chemin: Path = CHEMIN_BASELINE,
    chemin_modele: Path = CHEMIN_REFERENCE,
    chemin_meta: Path = CHEMIN_META_REFERENCE,
    force: bool = False,
) -> dict:
    """Fige la référence. Refuse d'écraser une baseline existante sans `force`."""
    if Path(chemin).exists() and not force:
        raise FileExistsError(
            f"{chemin} existe déjà : la référence est figée. Utilisez --force pour la refaire "
            "(décision à justifier dans le rapport)."
        )
    modele = charger_modele(chemin_modele, chemin_meta)
    val, test = jeux_evaluation()
    baseline = {
        "schema": 1,
        "cree_le": datetime.now(UTC).strftime("%Y-%m-%d"),
        "commit_code": _commit(),
        "version_reference": modele.version,
        "modele": {
            "fichier": Path(chemin_modele).as_posix(),
            "sha256": empreinte_fichier(chemin_modele),
            "seuil": modele.seuil,
            "variables": modele.meta["variables"],
        },
        "jeu_evaluation": {
            "description": "partition test (20 %, stratifiée) du jeu synthétique, graine 42",
            "n": len(test),
            "taux_defaut": round(float(test[CIBLE].mean()), 6),
            "empreinte_sha256": empreinte(test),
        },
        "metriques_test": evaluer(modele.pipeline, modele.seuil, test)[0],
        "metriques_validation": evaluer(modele.pipeline, modele.seuil, val)[0],
        "bibliotheques": versions_bibliotheques(),
        "tolerances": TOLERANCES,
    }
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    Path(chemin).write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", "utf-8")
    return baseline


def charger_baseline(chemin: Path = CHEMIN_BASELINE) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


# ---------- comparaison ----------


def niveau_baisse(baisse: float, accepter: float, investiguer: float) -> str:
    """Niveau d'une dégradation (valeur positive = dégradation). Bornes incluses."""
    baisse = round(baisse, 6)
    if baisse <= accepter:
        return ACCEPTER
    return INVESTIGUER if baisse <= investiguer else REJETER


def pire(niveaux) -> str:
    return max(niveaux, key=RANG.__getitem__, default=ACCEPTER)


def _controle(nom, reference, candidat, regle, niveau, ecart=None) -> dict:
    return {
        "controle": nom,
        "reference": reference,
        "candidat": candidat,
        "ecart": ecart,
        "regle": regle,
        "niveau": niveau,
    }


def controles_metriques(ref: dict, cand: dict, tolerances: dict) -> list[dict]:
    """Compare les métriques du candidat à celles de la baseline (jeu de test)."""
    controles = []
    for nom, (accepter, investiguer) in tolerances["baisse_max"].items():
        baisse = round(ref[nom] - cand[nom], 6)
        niveau = niveau_baisse(baisse, accepter, investiguer)
        regle = f"baisse ≤ {accepter} accepter ; ≤ {investiguer} investiguer ; sinon rejeter"
        controles.append(_controle(nom, ref[nom], cand[nom], regle, niveau, -baisse))
        gain = -baisse
        if nom in ("rappel", "f1") and gain > tolerances["hausse_suspecte"]:
            controles.append(
                _controle(
                    f"{nom} (hausse suspecte)",
                    ref[nom],
                    cand[nom],
                    f"hausse ≤ {tolerances['hausse_suspecte']} (sinon fuite de données possible)",
                    INVESTIGUER,
                    gain,
                )
            )
    return controles


def controle_decisions(dec_ref: np.ndarray, dec_cand: np.ndarray, tolerances: dict) -> dict:
    accepter, investiguer = tolerances["decisions_modifiees_max"]
    part = round(float((dec_ref != dec_cand).mean()), 6)
    return _controle(
        "décisions modifiées",
        0.0,
        part,
        f"≤ {accepter:.0%} accepter ; ≤ {investiguer:.0%} investiguer ; sinon rejeter",
        niveau_baisse(part, accepter, investiguer),
        part,
    )


def controles_integrite(baseline: dict, val_test: pd.DataFrame, modele_ref) -> list[dict]:
    """La référence rejouée aujourd'hui doit redonner la baseline (sinon comparaison douteuse)."""
    tol = baseline["tolerances"]["ecart_integrite"]
    ref = baseline["modele"]
    metriques, _ = evaluer(modele_ref.pipeline, modele_ref.seuil, val_test)
    controles = [
        _controle(
            "intégrité : jeu d'évaluation",
            baseline["jeu_evaluation"]["empreinte_sha256"][:12],
            empreinte(val_test)[:12],
            "empreinte identique à la baseline",
            ACCEPTER
            if empreinte(val_test) == baseline["jeu_evaluation"]["empreinte_sha256"]
            else INVESTIGUER,
        ),
        _controle(
            "intégrité : fichier du modèle de référence",
            ref["sha256"][:12],
            empreinte_fichier(ref["fichier"])[:12],
            "empreinte identique à la baseline",
            ACCEPTER if empreinte_fichier(ref["fichier"]) == ref["sha256"] else INVESTIGUER,
        ),
    ]
    for nom in ("rappel", "precision", "f1"):
        ecart = abs(metriques[nom] - baseline["metriques_test"][nom])
        controles.append(
            _controle(
                f"intégrité : {nom} de la référence rejouée",
                baseline["metriques_test"][nom],
                metriques[nom],
                f"écart ≤ {tol}",
                ACCEPTER if ecart <= tol else INVESTIGUER,
                round(ecart, 6),
            )
        )
    return controles


def comparer(
    chemin_candidat: Path, chemin_meta: Path | None = None, chemin_baseline: Path = CHEMIN_BASELINE
) -> dict:
    """Compare un candidat à la référence figée et rend la décision avec tous les contrôles."""
    chemin_candidat = Path(chemin_candidat)
    chemin_meta = Path(chemin_meta) if chemin_meta else chemin_candidat.with_suffix(".json")
    baseline = charger_baseline(chemin_baseline)
    tolerances = baseline["tolerances"]
    resultat = {
        "candidat": chemin_candidat.as_posix(),
        "reference": baseline["version_reference"],
        "controles": [],
    }
    controles = resultat["controles"]

    # 1. le candidat doit être chargeable et respecter le contrat de l'API
    try:
        candidat = charger_modele(chemin_candidat, chemin_meta)
    except ModeleIndisponible:
        controles.append(
            _controle("chargement du candidat", "-", "échec", "doit se charger", REJETER)
        )
        return _conclure(resultat)
    resultat["version_candidat"] = candidat.version
    contrat_ok = candidat.meta["variables"] == VARIABLES_MODELE
    controles.append(
        _controle(
            "contrat : variables du modèle",
            f"{len(VARIABLES_MODELE)} variables",
            f"{len(candidat.meta['variables'])} variables",
            "identiques à celles attendues par l'API",
            ACCEPTER if contrat_ok else REJETER,
        )
    )
    if not contrat_ok:
        return _conclure(resultat)

    # 2. intégrité de la référence, puis évaluation sur le même jeu fixe
    val, test = jeux_evaluation()
    modele_ref = charger_modele(baseline["modele"]["fichier"], CHEMIN_META_REFERENCE)
    controles += controles_integrite(baseline, test, modele_ref)
    metriques_cand, dec_cand = evaluer(candidat.pipeline, candidat.seuil, test)
    _, dec_ref = evaluer(modele_ref.pipeline, modele_ref.seuil, test)

    # 3. exigence métier absolue, puis non-régression relative
    rappel_val = evaluer(candidat.pipeline, candidat.seuil, val)[0]["rappel"]
    minimum = tolerances["rappel_validation_min"]
    controles.append(
        _controle(
            "exigence : rappel sur la validation",
            minimum,
            rappel_val,
            f"≥ {minimum}",
            ACCEPTER if rappel_val >= minimum else REJETER,
        )
    )
    controles += controles_metriques(baseline["metriques_test"], metriques_cand, tolerances)
    controles.append(controle_decisions(dec_ref, dec_cand, tolerances))
    resultat["metriques_candidat"] = metriques_cand
    return _conclure(resultat)


def _conclure(resultat: dict) -> dict:
    resultat["decision"] = pire(c["niveau"] for c in resultat["controles"])
    return resultat


# ---------- rapport et ligne de commande ----------

CONSEILS = {
    ACCEPTER: "Aucune régression au-delà des tolérances : le candidat peut être qualifié.",
    INVESTIGUER: "Dégradation ou anomalie en zone grise : analyse humaine requise avant décision.",
    REJETER: "Régression au-delà des tolérances ou contrat violé : ne pas déployer ce candidat.",
}


def _cellule(valeur) -> str:
    return f"{valeur:g}" if isinstance(valeur, float) else str(valeur)


def rediger_rapport(resultat: dict, baseline: dict) -> str:
    lignes = [
        f"## Candidat `{resultat['candidat']}` face à la référence {resultat['reference']}",
        "",
        f"**Décision : {resultat['decision']}.** {CONSEILS[resultat['decision']]}",
        "",
        "| Contrôle | Référence | Candidat | Écart | Règle | Niveau |",
        "|---|---|---|---|---|---|",
    ]
    for c in resultat["controles"]:
        ecart = "" if c["ecart"] is None else f"{c['ecart']:+g}"
        lignes.append(
            f"| {c['controle']} | {_cellule(c['reference'])} | {_cellule(c['candidat'])} "
            f"| {ecart} | {c['regle']} | {c['niveau']} |"
        )
    jeu = baseline["jeu_evaluation"]
    lignes += [
        "",
        f"Jeu d'évaluation : {jeu['description']} ({jeu['n']} dossiers, "
        f"taux de défaut {jeu['taux_defaut']}). Baseline créée le {baseline['cree_le']}.",
        "",
    ]
    return "\n".join(lignes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sous = parser.add_subparsers(dest="commande", required=True)
    b = sous.add_parser("baseline", help="figer la référence")
    b.add_argument("--force", action="store_true", help="remplacer une baseline existante")
    c = sous.add_parser("compare", help="comparer un candidat à la référence")
    c.add_argument("--candidat", required=True)
    c.add_argument("--meta", help="métadonnées du candidat (défaut : même nom en .json)")
    c.add_argument("--baseline", default=str(CHEMIN_BASELINE))
    c.add_argument("--rapport", help="écrit le rapport Markdown dans ce fichier")
    args = parser.parse_args(argv)

    if args.commande == "baseline":
        try:
            baseline = creer_baseline(force=args.force)
        except FileExistsError as exc:
            print(exc, file=sys.stderr)
            return 3
        test = baseline["metriques_test"]
        print(f"Baseline figée : {CHEMIN_BASELINE} (référence {baseline['version_reference']})")
        print(f"Test : rappel {test['rappel']} | précision {test['precision']} | F1 {test['f1']}")
        return 0

    if not Path(args.baseline).exists():
        print(
            f"Baseline introuvable : {args.baseline}. Lancez d'abord la commande baseline.",
            file=sys.stderr,
        )
        return 3
    resultat = comparer(args.candidat, args.meta, args.baseline)
    baseline = charger_baseline(args.baseline)
    rapport = rediger_rapport(resultat, baseline)
    if args.rapport:
        Path(args.rapport).parent.mkdir(parents=True, exist_ok=True)
        Path(args.rapport).write_text(rapport, encoding="utf-8")
    for c in resultat["controles"]:
        if c["niveau"] != ACCEPTER:
            print(f"  [{c['niveau']}] {c['controle']} : {c['reference']} -> {c['candidat']}")
    print(f"Décision : {resultat['decision']} ({resultat['candidat']})")
    return CODE_SORTIE[resultat["decision"]]


if __name__ == "__main__":
    sys.exit(main())
