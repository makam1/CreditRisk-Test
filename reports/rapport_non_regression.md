# Rapport de non-régression (Activité 5)

## 1. Méthode
Une version de **référence** (modèle `v1`) est figée dans `reports/baseline.json` avec son empreinte, son seuil, ses métriques, le jeu d'évaluation (partition test de 2 000 dossiers, graine 42, empreinte vérifiée), les versions des bibliothèques et les **tolérances**. Celles-ci sont écrites avant toute comparaison. Un candidat est comparé à cette baseline ; la décision est le pire niveau parmi tous les contrôles : **ACCEPTER**, **INVESTIGUER** (zone grise, analyse humaine) ou **REJETER**. Le script retourne les codes 0, 1 et 2, utilisables en intégration continue.

## 2. Référence figée
| | Rappel | Précision | F1 | Taux d'alerte |
|---|---|---|---|---|
| Test (2 000 dossiers : 235 VP, 35 FN, 777 FP, 953 VN) | 0,870 | 0,232 | 0,367 | 50,6 % |
| Validation | 0,852 | 0,235 | 0,369 | 48,9 % |

## 3. Tolérances (baisse absolue par rapport à la référence)
| Contrôle | Accepter jusqu'à | Investiguer jusqu'à | Au-delà | Justification |
|---|---|---|---|---|
| Rappel | 0,02 | 0,05 | REJETER | Exigence principale : chaque défaut manqué est une perte. Granularité du jeu : 1 défaut = 0,0037. |
| F1 | 0,02 | 0,05 | REJETER | Résume le compromis, mais ne remplace pas le rappel. |
| Précision | 0,03 | 0,08 | REJETER | Elle est déjà basse (0,23) : un point de plus de fausses alertes pèse moins qu'un point de défauts manqués. |
| Décisions modifiées | 5 % | 15 % | REJETER | Un changement massif de décisions doit être expliqué même si les métriques moyennes tiennent. |
| Rappel validation | ≥ 0,85 | | REJETER | Exigence métier, recalculée et non reprise du JSON. |
| Hausse de rappel ou F1 | ≤ 0,10 | | INVESTIGUER | Un gain énorme est suspect (fuite de données, jeu d'évaluation modifié). |
Contrôles supplémentaires : variables identiques à celles de l'API (sinon REJETER) et référence rejouée identique à la baseline (sinon INVESTIGUER).

## 4. Résultats
| Candidat | Rappel test | Précision | F1 | Décisions modifiées | Rappel validation | Décision |
|---|---|---|---|---|---|---|
| `v1_reconstruit` (réentraîné à l'identique) | 0,870 | 0,232 | 0,367 | 0 % | 0,852 | **ACCEPTER** |
| `v2_regularise` (régularisation plus forte) | 0,867 | 0,235 | 0,370 | 3 % | 0,852 | **ACCEPTER** |
| `v2_donnees_reduites` (1 500 dossiers d'entraînement) | 0,837 | 0,244 | 0,378 | 7,6 % | 0,852 | **INVESTIGUER** |
| `v2_seuil_oublie` (seuil par défaut 0,5) | 0,663 | 0,399 | 0,498 | 28 % | 0,696 | **REJETER** |
| `v2_sans_charge` (variable supprimée) | non évalué | | | | | **REJETER** (contrat API) |
Détail de chaque comparaison : `reports/non_regression/*.md`.

## 5. Lecture
- **Le F1 seul aurait trompé.** Pour `v2_seuil_oublie`, le F1 monte (0,367 → 0,498) et la précision aussi, car le modèle alerte moins ; mais il manque un tiers de défauts supplémentaires. Le rappel et l'exigence métier le rejettent.
- **Le cas `v2_donnees_reduites`** montre la zone grise : rappel −0,033, F1 et précision en hausse, 7,6 % de décisions modifiées. Rien n'est catastrophique, mais la décision exige une analyse humaine plutôt qu'un déploiement automatique.
- **Cohérence sauvegarde / rechargement.** Les probabilités du modèle rechargé sont strictement identiques. Ce contrôle a révélé l'anomalie **A09** : le seuil arrondi dans le JSON faisait tomber le rappel validation à 0,848 (< 0,85). Corrigée, avec des tests stricts.

## 6. Limites
- Les données sont synthétiques : les tolérances et résultats ne prouvent rien sur la performance réelle.
- Le jeu de test sert de jeu d'évaluation à chaque comparaison : à force de décisions fondées sur lui, il perd son statut de données jamais vues. Prévoir un jeu de contrôle récent en production.
- Les candidats sont simulés ; les seuils de tolérance sont des choix argumentés, à valider avec le métier.
- Aucune analyse par sous-population : une moyenne stable peut cacher une dégradation sur un profil (voir la question de synthèse).
