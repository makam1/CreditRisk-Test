CreditRisk-Test
Qualification d'une API FastAPI qui estime la probabilité de défaut de remboursement d'un demandeur de crédit (institution de microfinance). Travail individuel du module Tests Logiciels (TP 2).
> **Données synthétiques.** Le modèle est entraîné sur un jeu généré (`scripts/generate_data.py`). Les résultats décrivent le comportement du système, pas la performance sur de vrais clients.
![CI](https://github.com/makam1/CreditRisk-Test/actions/workflows/ci.yml/badge.svg)
Verdict de qualification
Tests	293 : 291 réussis, 2 `xfail` attendus (A06, A11), 0 échec ; couverture de `app/` : 100 %
Détection	rappel 0,852 (validation, exigence ≥ 0,85) ; 0,870 (test) ; précision 0,232
Point faible	5 profils sur 24 au-delà de 30 % de défauts manqués (jusqu'à 93 % pour les crédits de 37 à 48 mois)
Décision	pilote encadré (revue humaine, mode ombre) : accepté sous conditions ; décision automatisée : non recommandée en l'état
Détails : `reports/` et le rapport final de qualification.
Installation
Python 3.14 recommandé (versions figées dans `requirements.txt`).
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py      # crée data/credit_synthetic.csv (non versionné)
```
Le modèle de test (`models/model_v1.joblib` et `.json`) est versionné : il n'est pas nécessaire de le réentraîner. Pour le refaire : `python -m scripts.train` (puis, si la référence change, refaire la baseline avec `--force` et le justifier).
Lancer l'API
```bash
uvicorn app.main:app --port 8000
curl -s -X POST localhost:8000/predict -H 'content-type: application/json' \
  -d '{"age":35,"revenu_mensuel":250000,"montant_credit":1000000,"duree_mois":12,"anciennete_activite":4}'
```
Documentation interactive : http://127.0.0.1:8000/docs. Le seuil de décision (0,2858 par défaut) peut être changé par la variable d'environnement `SEUIL_DECISION` ; une valeur invalide empêche le démarrage.
Route	Rôle	Codes
`GET /health`	état du service et du modèle	200, 503
`GET /model-info`	version, seuil, variables, métriques de référence	200, 503
`POST /predict`	prédiction pour un dossier	200, 422 (entrée invalide), 503 (modèle indisponible), 500 (erreur interne générique)
Entrée de `/predict` : `age` (entier, 18-100), `revenu_mensuel` (≥ 1 000), `montant_credit`, `duree_mois` (entier, 1-120), `anciennete_activite` (≤ âge). Une entrée valide mais hors du domaine d'entraînement est traitée avec un avertissement.
Tests et contrôles
```bash
ruff check .
pytest --cov=app --cov-report=term-missing
```
Commande	Rôle
`python -m scripts.regression compare --candidat models/model_v1.joblib`	non-régression face à la baseline figée (codes 0 accepter, 1 investiguer, 2 rejeter)
`python -m scripts.candidats`	génère cinq candidats de démonstration dans `models/candidats/`
`python -m scripts.perf --rapport reports/resultats_performance.md`	latence, débit, montée en charge de 1 à 50 utilisateurs
`python -m scripts.analyse_sous_groupes --rapport reports/analyse_sous_groupes.md`	faux négatifs par profil (code 1 si une tranche est signalée)
`locust -f locustfile.py --host http://127.0.0.1:8000`	test de charge facultatif (`requirements-load.txt`)
Intégration continue
`.github/workflows/ci.yml` s'exécute sur chaque pull request et sur `main` : Ruff, pytest avec couverture (seuil 85 %), non-régression du modèle de référence. Un test volontairement faux dans une pull request fait passer le workflow au rouge (preuve dans le rapport).
Structure
```
app/          API (main), validation, prétraitement, prédiction
scripts/      génération des données, entraînement, non-régression, candidats, performance, profils
models/       modèle de référence versionné (v1)
tests/        validation, prétraitement, prédiction, modèle, API, intégration, robustesse,
              non-régression, performance, profils
reports/      plan de test, registre des anomalies, rapports, baseline figée
.github/      workflow CI
```
Documents
`reports/plan_de_test.md` : exigences, risques, cas de test, critères d'acceptation, traçabilité
`reports/registre_anomalies.md` : anomalies A01 à A11 avec gravité et statut
`reports/rapport_robustesse.md`, `reports/rapport_non_regression.md`, `reports/rapport_performance.md`
`reports/baseline.json` : référence figée (ne pas la modifier sans justification)
Limites connues
Données synthétiques ; jeu de test de 2 000 dossiers ; performance mesurée en local ; aucune limite de taille de requête (A06, ouverte) ; faux négatifs concentrés sur certains profils (A11, ouverte) ; aucune analyse d'équité entre groupes protégés (attributs absents).
