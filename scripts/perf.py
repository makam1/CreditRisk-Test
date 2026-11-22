# ruff: noqa: E501
"""Mesures de performance (Activité 6) : latence d'inférence, temps de réponse de l'API,
débit et montée en charge progressive. Test LÉGER et local : aucune dépendance hors bibliothèque
standard (Locust est facultatif, voir locustfile.py).

Usage : python -m scripts.perf [--niveaux 1,2,5,10,20,50] [--duree 4]
                               [--rapport reports/resultats_performance.md]
                               [--json reports/performance.json]
Code de sortie : 0 si tous les objectifs sont tenus, 1 sinon.
"""

import argparse
import http.client
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import sklearn
from fastapi.testclient import TestClient

from app.main import app
from app.prediction import charger_modele, predire
from scripts.generate_data import generate

PORT = 8765

# Objectifs, fixés AVANT les mesures (justification dans reports/rapport_performance.md).
OBJECTIFS = {
    "inference_p95_ms": 50.0,  # modèle seul (une ligne)
    "api_p95_ms": 200.0,  # /predict via HTTP, jusqu'à 10 utilisateurs simultanés
    "debit_min_rps": 20.0,  # à 10 utilisateurs simultanés
    "erreurs_max": 0,  # jusqu'à 10 utilisateurs simultanés
    "utilisateurs_objectif": 10,
}


def dossiers_exemples(n: int = 50) -> list[dict]:
    df = generate(n=2000, seed=7).sample(n, random_state=7)
    return [
        {
            "age": int(r.age),
            "revenu_mensuel": float(r.revenu_mensuel),
            "montant_credit": float(r.montant_credit),
            "duree_mois": int(r.duree_mois),
            "anciennete_activite": float(r.anciennete_activite),
        }
        for r in df.itertuples()
    ]


def percentiles(durees_ms: list[float]) -> dict:
    tri = sorted(durees_ms)

    def p(q):
        return tri[min(len(tri) - 1, int(q * len(tri)))]

    return {
        "n": len(tri),
        "moyenne_ms": round(statistics.fmean(tri), 2),
        "p50_ms": round(p(0.50), 2),
        "p95_ms": round(p(0.95), 2),
        "p99_ms": round(p(0.99), 2),
        "max_ms": round(tri[-1], 2),
    }


def latence_inference(dossiers, repetitions: int = 500) -> dict:
    modele = charger_modele()
    for d in dossiers[:20]:  # échauffement
        predire(modele, d)
    durees = []
    for i in range(repetitions):
        debut = time.perf_counter()
        predire(modele, dossiers[i % len(dossiers)])
        durees.append((time.perf_counter() - debut) * 1000)
    return percentiles(durees)


def latence_api_en_memoire(dossiers, repetitions: int = 300) -> dict:
    durees = []
    with TestClient(app) as client:
        for d in dossiers[:20]:
            client.post("/predict", json=d)
        for i in range(repetitions):
            debut = time.perf_counter()
            reponse = client.post("/predict", json=dossiers[i % len(dossiers)])
            durees.append((time.perf_counter() - debut) * 1000)
            assert reponse.status_code == 200
    return percentiles(durees)


class ServeurUvicorn:
    """Lance l'API dans un processus séparé (comme en exploitation, un seul worker)."""

    def __enter__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PORT),
             "--log-level", "warning"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )  # fmt: skip
        for _ in range(100):
            try:
                c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=1)
                c.request("GET", "/health")
                if c.getresponse().status == 200:
                    return self
            except OSError:
                time.sleep(0.1)
        self.proc.kill()
        raise RuntimeError("L'API n'a pas démarré.")

    def __exit__(self, *_exc):
        self.proc.terminate()
        self.proc.wait(timeout=10)


def _travailleur(dossiers, fin: float, decalage: int, resultats: list, verrou) -> None:
    corps = [json.dumps(d).encode() for d in dossiers]
    connexion = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    entetes = {"Content-Type": "application/json"}
    locales, erreurs, i = [], 0, decalage
    while time.perf_counter() < fin:
        debut = time.perf_counter()
        try:
            connexion.request("POST", "/predict", body=corps[i % len(corps)], headers=entetes)
            reponse = connexion.getresponse()
            reponse.read()
            ok = reponse.status == 200
        except OSError:
            ok = False
            connexion = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        locales.append((time.perf_counter() - debut) * 1000)
        erreurs += 0 if ok else 1
        i += 1
    with verrou:
        resultats.append((locales, erreurs))


def palier(dossiers, utilisateurs: int, duree_s: float) -> dict:
    resultats, verrou = [], threading.Lock()
    debut = time.perf_counter()
    fin = debut + duree_s
    with ThreadPoolExecutor(max_workers=utilisateurs) as pool:
        for u in range(utilisateurs):
            pool.submit(_travailleur, dossiers, fin, u * 7, resultats, verrou)
    ecoule = time.perf_counter() - debut
    durees = [d for locales, _ in resultats for d in locales]
    erreurs = sum(e for _, e in resultats)
    mesure = percentiles(durees)
    mesure.update(
        utilisateurs=utilisateurs,
        debit_rps=round(len(durees) / ecoule, 1),
        erreurs=erreurs,
    )
    return mesure


def configuration() -> dict:
    return {
        "machine": platform.platform(),
        "processeurs": os.cpu_count(),
        "python": platform.python_version(),
        "scikit-learn": sklearn.__version__,
        "serveur": "uvicorn, 1 worker, 127.0.0.1 (client et serveur sur la même machine)",
        "client": "http.client, connexions persistantes, 1 thread par utilisateur",
    }


def evaluer_objectifs(resultats: dict) -> list[dict]:
    cible = OBJECTIFS["utilisateurs_objectif"]
    sous = [p for p in resultats["paliers"] if p["utilisateurs"] <= cible]
    palier_cible = next((p for p in sous if p["utilisateurs"] == cible), sous[-1])
    controles = [
        ("Latence d'inférence P95", resultats["inference"]["p95_ms"], OBJECTIFS["inference_p95_ms"], "max"),
        ("API /predict P95 (≤ 10 utilisateurs)", max(p["p95_ms"] for p in sous), OBJECTIFS["api_p95_ms"], "max"),
        (f"Débit à {palier_cible['utilisateurs']} utilisateurs (req/s)", palier_cible["debit_rps"], OBJECTIFS["debit_min_rps"], "min"),
        ("Erreurs (≤ 10 utilisateurs)", sum(p["erreurs"] for p in sous), OBJECTIFS["erreurs_max"], "max"),
    ]  # fmt: skip
    return [
        {
            "objectif": nom,
            "mesure": mesure,
            "seuil": seuil,
            "tenu": mesure <= seuil if sens == "max" else mesure >= seuil,
        }
        for nom, mesure, seuil, sens in controles
    ]


def rediger_rapport(resultats: dict) -> str:
    c = resultats["configuration"]
    lignes = [
        "## Résultats des mesures",
        "",
        f"Configuration : {c['machine']}, {c['processeurs']} processeurs, Python {c['python']}, "
        f"scikit-learn {c['scikit-learn']}. {c['serveur']} ; {c['client']}.",
        "",
        "| Mesure | Moyenne (ms) | P50 | P95 | P99 | Max |",
        "|---|---|---|---|---|---|",
    ]
    for nom, m in (
        ("Inférence seule (fonction `predire`)", resultats["inference"]),
        ("API en mémoire (TestClient, sans réseau)", resultats["api_memoire"]),
    ):
        lignes.append(
            f"| {nom} | {m['moyenne_ms']} | {m['p50_ms']} | {m['p95_ms']} | {m['p99_ms']} | {m['max_ms']} |"
        )
    lignes += [
        "",
        "### Montée en charge progressive (HTTP, `/predict`)",
        "",
        "| Utilisateurs simultanés | Requêtes | Débit (req/s) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Erreurs |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in resultats["paliers"]:
        lignes.append(
            f"| {p['utilisateurs']} | {p['n']} | {p['debit_rps']} | {p['p50_ms']} | {p['p95_ms']} "
            f"| {p['p99_ms']} | {p['max_ms']} | {p['erreurs']} |"
        )
    lignes += [
        "",
        "### Objectifs",
        "",
        "| Objectif | Mesuré | Seuil | Verdict |",
        "|---|---|---|---|",
    ]
    for o in resultats["objectifs"]:
        lignes.append(
            f"| {o['objectif']} | {o['mesure']} | {o['seuil']} | {'tenu' if o['tenu'] else 'NON tenu'} |"
        )
    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--niveaux", default="1,2,5,10,20,50")
    parser.add_argument("--duree", type=float, default=4.0, help="secondes par palier")
    parser.add_argument("--rapport")
    parser.add_argument("--json", dest="chemin_json")
    args = parser.parse_args(argv)

    dossiers = dossiers_exemples()
    resultats = {
        "configuration": configuration(),
        "inference": latence_inference(dossiers),
        "api_memoire": latence_api_en_memoire(dossiers),
        "paliers": [],
    }
    print("Inférence :", resultats["inference"])
    print("API en mémoire :", resultats["api_memoire"])
    with ServeurUvicorn():
        for niveau in (int(x) for x in args.niveaux.split(",")):
            mesure = palier(dossiers, niveau, args.duree)
            resultats["paliers"].append(mesure)
            print(
                f"{niveau:>3} utilisateurs : {mesure['debit_rps']:>7} req/s | "
                f"P95 {mesure['p95_ms']:>7} ms | erreurs {mesure['erreurs']}"
            )
    resultats["objectifs"] = evaluer_objectifs(resultats)
    for o in resultats["objectifs"]:
        print(
            f"[{'OK' if o['tenu'] else 'ÉCHEC'}] {o['objectif']} : {o['mesure']} (seuil {o['seuil']})"
        )
    if args.chemin_json:
        Path(args.chemin_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.chemin_json).write_text(
            json.dumps(resultats, indent=2, ensure_ascii=False) + "\n", "utf-8"
        )
    if args.rapport:
        Path(args.rapport).parent.mkdir(parents=True, exist_ok=True)
        Path(args.rapport).write_text(rediger_rapport(resultats), encoding="utf-8")
    return 0 if all(o["tenu"] for o in resultats["objectifs"]) else 1


if __name__ == "__main__":
    sys.exit(main())
