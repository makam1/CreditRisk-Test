## Candidat `models/candidats/v2_seuil_oublie.joblib` face à la référence v1

**Décision : REJETER.** Régression au-delà des tolérances ou contrat violé : ne pas déployer ce candidat.

| Contrôle | Référence | Candidat | Écart | Règle | Niveau |
|---|---|---|---|---|---|
| contrat : variables du modèle | 6 variables | 6 variables |  | identiques à celles attendues par l'API | ACCEPTER |
| intégrité : jeu d'évaluation | 9aa5577a5ee0 | 9aa5577a5ee0 |  | empreinte identique à la baseline | ACCEPTER |
| intégrité : fichier du modèle de référence | 5838a23d2da8 | 5838a23d2da8 |  | empreinte identique à la baseline | ACCEPTER |
| intégrité : rappel de la référence rejouée | 0.87037 | 0.87037 | +0 | écart ≤ 0.0001 | ACCEPTER |
| intégrité : precision de la référence rejouée | 0.232213 | 0.232213 | +0 | écart ≤ 0.0001 | ACCEPTER |
| intégrité : f1 de la référence rejouée | 0.366615 | 0.366615 | +0 | écart ≤ 0.0001 | ACCEPTER |
| exigence : rappel sur la validation | 0.85 | 0.696296 |  | ≥ 0.85 | REJETER |
| rappel | 0.87037 | 0.662963 | -0.207407 | baisse ≤ 0.02 accepter ; ≤ 0.05 investiguer ; sinon rejeter | REJETER |
| f1 | 0.366615 | 0.497914 | +0.131299 | baisse ≤ 0.02 accepter ; ≤ 0.05 investiguer ; sinon rejeter | ACCEPTER |
| f1 (hausse suspecte) | 0.366615 | 0.497914 | +0.131299 | hausse ≤ 0.1 (sinon fuite de données possible) | INVESTIGUER |
| precision | 0.232213 | 0.398664 | +0.166451 | baisse ≤ 0.03 accepter ; ≤ 0.08 investiguer ; sinon rejeter | ACCEPTER |
| décisions modifiées | 0 | 0.2815 | +0.2815 | ≤ 5% accepter ; ≤ 15% investiguer ; sinon rejeter | REJETER |

Jeu d'évaluation : partition test (20 %, stratifiée) du jeu synthétique, graine 42 (2000 dossiers, taux de défaut 0.135). Baseline créée le 2026-11-22.
