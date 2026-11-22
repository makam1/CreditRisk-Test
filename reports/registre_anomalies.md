# Registre des anomalies

Échelle de gravité : **critique** (décision faussée, fuite), **majeure** (erreur interne ou comportement hors contrat), **mineure** (confort, qualité).

| ID | Anomalie | Gravité | Détectée par | Cause | Correction | Statut |
|---|---|---|---|---|---|---|
| A01 | Un revenu quasi nul (1e-323) est accepté, puis le prétraitement échoue (division qui déborde) | Majeure | Hypothesis, test T12 | Pas de borne basse sur le revenu | `REVENU_MIN = 1 000` et tests | Corrigée |
| A02 | Avertissement de dépréciation : `httpx` avec `starlette.testclient` | Mineure | Résumé des avertissements pytest | Dépendance de test dépréciée | Remplacement par `httpx2` | Corrigée |
| A03 | Un entier JSON de 400 chiffres provoque `OverflowError`, donc un 500 | Majeure | Fuzzing Hypothesis (T44) | `math.isfinite` appliqué à un entier trop grand pour un flottant | Pas de `isfinite` sur les entiers, rejet par la borne maximale | Corrigée |
| A04 | Une ancienneté supérieure à l'âge est acceptée (profil impossible) | Mineure | Scénario R12 | Aucune règle de cohérence entre variables | Règle ancienneté ≤ âge | Corrigée |
| A05 | Un JSON imbriqué sur 100 000 niveaux provoque `RecursionError`, donc une réponse 500 non JSON | Majeure | Test T45 | Exception non capturée dans la lecture du corps | Capture de `RecursionError` et réponse 422 | Corrigée |
| A06 | L'API n'impose aucune taille maximale au corps de requête | Majeure (risque de déni de service) | Revue de sécurité et test `xfail` | Aucun contrôle de taille | Recommandé : limite à 10 Ko avec réponse 413, ou limite au niveau du proxy | **Ouverte** |
| A07 | Au seuil retenu (rappel 0,85), la précision n'est que de 0,24 : environ 3 fausses alertes pour 1 défaut détecté | À arbitrer par le métier | Évaluation sur la validation | Compromis rappel/précision ; données synthétiques bruitées | Seuil réglable (EX14) ; coût des faux positifs et négatifs à fixer avec le métier | **Ouverte** (risque résiduel) |
| A08 | Dépendances de l'API non figées (`fastapi`, `uvicorn`) | Mineure | Revue du dépôt | `requirements.txt` incomplet | Versions figées | Corrigée |
| A09 | Le seuil est arrondi à 6 décimales dans `model_v1.json` : le dossier situé exactement sur le seuil bascule en dessous, le rappel validation du modèle livré est 0,848 (exigence 0,85) alors que le JSON annonce 0,852 | Majeure | Test strict de recalcul sur le modèle sauvegardé (T46), préparé pour la non-régression | `round(seuil, 6)` ; seuil égal à une probabilité observée ; test précédent trop tolérant (±0,03) | Seuil non arrondi, placé au milieu entre la probabilité retenue et la précédente ; tests stricts (T46, T47) | Corrigée |
| A10 | L'intégrité de la référence reposait sur l'empreinte SHA-256 du fichier joblib : un fichier réécrit avec le même modèle (octets différents) faisait échouer 5 tests de non-régression | Mineure | Exécution de la suite complète en local | Une empreinte d'octets dépend de la sérialisation, pas du modèle | Empreinte des paramètres (scaler, coefficients, intercept) et du seuil ; baseline refaite avec `--force` | Corrigée |
| A11 | Les défauts sont manqués en grande partie pour certains profils (durée de 37 à 48 mois : 13 sur 14 ; charge mensuelle de 0,10 à 0,20 : 14 sur 15) alors que le rappel global est de 0,87 | Critique pour un usage décisionnel | Analyse par tranche (EX25), test `xfail` strict | Modèle linéaire unique et seuil global ; exigence initiale portant sur la moyenne | Non corrigée : revue humaine des profils signalés, surveillance par segment, amélioration du modèle | **Ouverte** |

Preuves : captures des échecs avant correction (A01, A03, A04, A05) et des exécutions réussies après correction ; `xfail` strict pour A06.
