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

Preuves : captures des échecs avant correction (A01, A03, A04, A05) et des exécutions réussies après correction ; `xfail` strict pour A06.
