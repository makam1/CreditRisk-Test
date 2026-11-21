# Données

Jeu de données **synthétique** généré par `scripts/generate_data.py` (graine 42, 10 000 lignes). Il n'est pas versionné : il se régénère à l'identique.

Il sert uniquement à tester le système. Il ne permet pas de démontrer la performance réelle d'un modèle de crédit : la relation entre les variables et le défaut est inventée.

| Variable | Type | Description |
|---|---|---|
| age | entier | 18 à 70 ans |
| revenu_mensuel | réel | FCFA, loi log-normale |
| montant_credit | réel | FCFA, de 1 à 12 fois le revenu |
| duree_mois | entier | 6, 12, 18, 24, 36 ou 48 |
| anciennete_activite | réel | années, toujours inférieure à age - 16 |
| defaut | binaire | cible : 1 = défaut, 0 = remboursé |

Le risque de défaut augmente avec le poids de la mensualité sur le revenu et diminue avec l'ancienneté. Aucune donnée personnelle réelle n'est utilisée.

Régénération : `python scripts/generate_data.py`
