## Candidat `models/candidats/v2_donnees_reduites.joblib` face à la référence v1

**Décision : INVESTIGUER.** Dégradation ou anomalie en zone grise : analyse humaine requise avant décision.

| Contrôle | Référence | Candidat | Écart | Règle | Niveau |
|---|---|---|---|---|---|
| contrat : variables du modèle | 6 variables | 6 variables |  | identiques à celles attendues par l'API | ACCEPTER |
| intégrité : jeu d'évaluation | 9aa5577a5ee0 | 9aa5577a5ee0 |  | empreinte identique à la baseline | ACCEPTER |
| intégrité : fichier du modèle de référence | 5838a23d2da8 | 5838a23d2da8 |  | empreinte identique à la baseline | ACCEPTER |
| intégrité : rappel de la référence rejouée | 0.87037 | 0.87037 | +0 | écart ≤ 0.0001 | ACCEPTER |
| intégrité : precision de la référence rejouée | 0.232213 | 0.232213 | +0 | écart ≤ 0.0001 | ACCEPTER |
| intégrité : f1 de la référence rejouée | 0.366615 | 0.366615 | +0 | écart ≤ 0.0001 | ACCEPTER |
| exigence : rappel sur la validation | 0.85 | 0.851852 |  | ≥ 0.85 | ACCEPTER |
| rappel | 0.87037 | 0.837037 | -0.033333 | baisse ≤ 0.02 accepter ; ≤ 0.05 investiguer ; sinon rejeter | INVESTIGUER |
| f1 | 0.366615 | 0.377926 | +0.011311 | baisse ≤ 0.02 accepter ; ≤ 0.05 investiguer ; sinon rejeter | ACCEPTER |
| precision | 0.232213 | 0.24406 | +0.011847 | baisse ≤ 0.03 accepter ; ≤ 0.08 investiguer ; sinon rejeter | ACCEPTER |
| décisions modifiées | 0 | 0.076 | +0.076 | ≤ 5% accepter ; ≤ 15% investiguer ; sinon rejeter | INVESTIGUER |

Jeu d'évaluation : partition test (20 %, stratifiée) du jeu synthétique, graine 42 (2000 dossiers, taux de défaut 0.135). Baseline créée le 2026-11-22.
