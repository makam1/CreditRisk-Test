## Candidat `models/candidats/v2_sans_charge.joblib` face à la référence v1

**Décision : REJETER.** Régression au-delà des tolérances ou contrat violé : ne pas déployer ce candidat.

| Contrôle | Référence | Candidat | Écart | Règle | Niveau |
|---|---|---|---|---|---|
| contrat : variables du modèle | 6 variables | 5 variables |  | identiques à celles attendues par l'API | REJETER |

Jeu d'évaluation : partition test (20 %, stratifiée) du jeu synthétique, graine 42 (2000 dossiers, taux de défaut 0.135). Baseline créée le 2026-11-22.
