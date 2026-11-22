## Résultats des mesures

Configuration : Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.43, 8 processeurs, Python 3.14.4, scikit-learn 1.9.1. uvicorn, 1 worker, 127.0.0.1 (client et serveur sur la même machine) ; http.client, connexions persistantes, 1 thread par utilisateur.

| Mesure | Moyenne (ms) | P50 | P95 | P99 | Max |
|---|---|---|---|---|---|
| Inférence seule (fonction `predire`) | 2.09 | 2.02 | 2.44 | 2.72 | 4.42 |
| API en mémoire (TestClient, sans réseau) | 5.65 | 5.5 | 6.88 | 7.48 | 8.89 |

### Montée en charge progressive (HTTP, `/predict`)

| Utilisateurs simultanés | Requêtes | Débit (req/s) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Erreurs |
|---|---|---|---|---|---|---|---|
| 1 | 1264 | 315.9 | 3.02 | 4.09 | 5.39 | 21.06 | 0 |
| 2 | 1260 | 314.5 | 6.12 | 8.53 | 9.88 | 12.83 | 0 |
| 5 | 1191 | 296.8 | 16.12 | 21.55 | 25.59 | 40.35 | 0 |
| 10 | 1262 | 313.1 | 30.5 | 35.97 | 37.66 | 575.91 | 0 |
| 20 | 1313 | 322.6 | 58.25 | 70.8 | 153.62 | 1337.47 | 0 |
| 50 | 1294 | 312.0 | 154.58 | 180.98 | 195.03 | 232.93 | 0 |

### Objectifs

| Objectif | Mesuré | Seuil | Verdict |
|---|---|---|---|
| Latence d'inférence P95 | 2.44 | 50.0 | tenu |
| API /predict P95 (≤ 10 utilisateurs) | 35.97 | 200.0 | tenu |
| Débit à 10 utilisateurs (req/s) | 313.1 | 20.0 | tenu |
| Erreurs (≤ 10 utilisateurs) | 0 | 0 | tenu |
