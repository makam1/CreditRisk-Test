# Rapport de performance (Activité 6)

## 1. Objectifs et justification
Le service sert des agents de crédit en agence, qui saisissent un dossier puis attendent le score. Hypothèse pour le pilote : une vingtaine d'agents, environ un dossier par minute chacun, soit moins de 1 requête/s en moyenne, avec des pointes de quelques requêtes par seconde.

| Objectif | Seuil | Justification |
|---|---|---|
| Latence d'inférence (P95) | ≤ 50 ms | Le modèle (régression logistique, 1 ligne) doit être négligeable devant le reste de la chaîne. |
| Temps de réponse de `/predict` (P95), jusqu'à 10 utilisateurs simultanés | ≤ 200 ms | Au-delà, l'attente est perceptible pendant une saisie guidée. On regarde le P95 et non la moyenne : ce sont les pires attentes qui dérangent. |
| Débit à 10 utilisateurs simultanés | ≥ 20 req/s | Plus de 10 fois la pointe estimée du pilote. |
| Erreurs jusqu'à 10 utilisateurs | 0 | Une erreur sur un dossier de crédit n'est pas acceptable. |
Ces seuils sont fixés avant les mesures, dans `scripts/perf.py`.

## 2. Méthode
- `python -m scripts.perf` mesure : (1) la latence de la fonction `predire` (500 appels après échauffement) ; (2) le temps de réponse de l'API en mémoire (`TestClient`, sans réseau) ; (3) une **montée en charge progressive** sur le vrai serveur uvicorn (1 worker) : 1, 2, 5, 10, 20 puis 50 utilisateurs simultanés, 4 secondes par palier, connexions persistantes, 50 dossiers valides différents.
- Pour chaque palier : débit, P50, P95, P99, maximum, erreurs. Le palier à 10 utilisateurs sert aux objectifs ; 20 et 50 servent à repérer le point de saturation.
- Les tests `tests/test_performance.py` rejouent une version courte avec des seuils larges, dans la CI.
- Locust (`locustfile.py`) est fourni à titre facultatif pour un test plus long ; il n'est pas exécuté en CI.

## 3. Configuration
Documentée automatiquement dans `reports/resultats_performance.md` (système, nombre de processeurs, versions de Python et scikit-learn, serveur, client). Résultats bruts : `reports/performance.json`.

## 4. Lecture des résultats
Les tableaux de `reports/resultats_performance.md` donnent les valeurs mesurées. Deux repères : (a) tant que le débit augmente avec le nombre d'utilisateurs, le serveur n'est pas saturé ; (b) une fois le débit plafonné, tout utilisateur de plus allonge la file d'attente, donc la latence augmente sans gain de débit. Ce plafond est la capacité d'un worker.

## 5. Limites
- Client et serveur tournent sur la même machine et se partagent les processeurs : les mesures sont pessimistes sur la capacité du serveur mais n'incluent aucune latence réseau.
- Paliers de 4 secondes : pas de test d'endurance, pas de mesure de la mémoire sur la durée, pas de démarrage à froid mesuré.
- Les valeurs dépendent de la machine ; elles servent de repère relatif et de garde contre une régression grossière, pas de contrat de service.
- Les dossiers sont synthétiques et valides ; les entrées invalides (rejet 422) ne sont pas incluses dans la charge.
- Un seul worker : pas d'évaluation du passage à plusieurs workers ou à plusieurs instances.
