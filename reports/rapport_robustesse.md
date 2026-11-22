# Rapport de robustesse (Activité 4)

**Règle de décision.** Une entrée **invalide** (type incorrect, hors intervalle, champ absent ou en trop, incohérence, non finie) est **rejetée** (422, aucune prédiction). Une entrée **valide mais inhabituelle** (hors du domaine vu à l'entraînement) est **traitée** (200) avec un **avertissement**. Une panne interne produit un 500 générique, sans trace.

| ID | Scénario | Risque visé | Comportement attendu | Résultat observé | Gravité de l'anomalie | Correction |
|---|---|---|---|---|---|---|
| R01 à R07 | Valeur absente, null, texte, booléen, liste ou objet à la place d'un nombre | Calcul sur une donnée absurde | Rejet 422 | Conforme | Aucune | n/a |
| R08 à R10 | Schéma incorrect (noms anglais, liste de dossiers, champ en trop) | Contrat flou, injection de champs | Rejet 422 | Conforme | Aucune | n/a |
| R11 | Âge 17 (juste sous la limite) | Évaluer un mineur | Rejet 422 | Conforme | Aucune | n/a |
| R12 | Ancienneté (30) supérieure à l'âge (20) | Score sur un profil impossible | Rejet 422 | **Avant** : accepté (200) ; **après** : 422 | Mineure (A04) | Règle de cohérence ancienneté ≤ âge |
| R13, R20 | Âge 18 ; ancienneté nulle | Cas limite dans le domaine | Traité, sans avertissement | Conforme | Aucune | n/a |
| R14 à R19 | Limites autorisées hors domaine (âge 100, revenu 1 000 et 1e8, durée 1 et 120, montant 5 Md) | Extrapolation silencieuse du modèle | Traité (200) + avertissement | Conforme | Aucune | n/a |
| R21 | NaN, Infinity, -Infinity dans chaque champ numérique | Propagation de valeurs non finies | Rejet 422 | Conforme | Aucune | n/a |
| R22 | Entier de 400 chiffres | Débordement, erreur interne | Rejet 422 | **Avant** : 500 (`OverflowError`) ; **après** : 422 | Majeure (A03) | Contrôle adapté aux entiers |
| R23 | JSON imbriqué sur 100 000 niveaux | Épuisement de la pile, erreur interne | Rejet 422 | **Avant** : exception non gérée ; **après** : 422 | Majeure (A05) | Capture de `RecursionError` |
| R24 | Corps de 2 Mo | Déni de service | Rejet 413 | Accepté en lecture puis rejeté en 422 | Majeure (A06) | **Ouverte** : limite de taille recommandée |
| R25 | 300 corps JSON aléatoires (fuzzing) | Toute erreur 500 | 200 ou 422 | **Avant** : 500 (A03) ; **après** : conforme | Majeure (A03) | Voir R22 |

**Limites.** Les 300 cas aléatoires et les scénarios choisis ne prouvent pas l'absence d'autres défauts. Les perturbations réalistes des variables (sensibilité du score à un petit bruit) ne sont pas étudiées ici. Les données étant synthétiques, les alertes « hors domaine » dépendent des plages du jeu d'entraînement.
