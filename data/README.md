Données
Le dossier ne contient aucun fichier de données versionné (`data/*.csv` est ignoré par Git).
Générer le jeu
```bash
python scripts/generate_data.py
```
Crée `data/credit_synthetic.csv` : 10 000 dossiers synthétiques, graine 42 (génération déterministe), taux de défaut 13,5 %.
Colonne	Description	Plage observée
`age`	âge du demandeur (entier)	18 à 70
`revenu_mensuel`	revenu mensuel	50 000 à 1 751 000
`montant_credit`	montant demandé	60 000 à 19 410 000
`duree_mois`	durée du crédit en mois (entier)	6 à 48
`anciennete_activite`	ancienneté de l'activité, en années	0 à 24,9
`defaut`	cible : 1 si défaut de remboursement, 0 sinon	0 ou 1
Avertissements
Les données sont fictives : elles ne décrivent aucun client réel et ne prouvent aucune performance réelle.
Le découpage 60 % / 20 % / 20 % (entraînement, validation, test) est stratifié, avec graine fixe, et se fait avant tout ajustement. Le jeu de test sert d'évaluation fixe à la non-régression.
Les tests n'ont pas besoin du fichier CSV : ils régénèrent le jeu à la volée (même graine).
