## Faux négatifs par profil (jeu de test, modèle de référence)

Global : 35 faux négatifs sur 270 défauts réels, soit un taux de faux négatifs de 13.0% (rappel 87.0%).
Règle : tranche signalée si elle compte au moins 10 défauts et que son taux de faux négatifs dépasse 30%. Intervalle de confiance à 95 % (Wilson).

| Variable | Tranche | Dossiers | Défauts | Faux négatifs | Taux de FN | IC 95 % | Taux d'alerte | Verdict |
|---|---|---|---|---|---|---|---|---|
| age | 18-25 | 293 | 46 | 6 | 13.0% | 6%-26% | 63.5% | ok |
| age | 26-35 | 399 | 56 | 4 | 7.1% | 3%-17% | 59.6% | ok |
| age | 36-50 | 575 | 86 | 15 | 17.4% | 11%-27% | 49.4% | ok |
| age | 51+ | 733 | 82 | 10 | 12.2% | 7%-21% | 41.5% | ok |
| revenu_mensuel | < 100 000 | 117 | 13 | 0 | 0.0% | 0%-23% | 47.9% | ok |
| revenu_mensuel | 100 000-200 000 | 728 | 91 | 14 | 15.4% | 9%-24% | 50.4% | ok |
| revenu_mensuel | 200 000-350 000 | 779 | 107 | 13 | 12.1% | 7%-20% | 50.1% | ok |
| revenu_mensuel | ≥ 350 000 | 376 | 59 | 8 | 13.6% | 7%-25% | 52.9% | ok |
| montant_credit | < 0,75 M | 491 | 21 | 10 | 47.6% | 28%-68% | 21.0% | SIGNALÉE |
| montant_credit | 0,75-1,5 M | 644 | 80 | 13 | 16.2% | 10%-26% | 50.5% | ok |
| montant_credit | 1,5-3 M | 607 | 114 | 8 | 7.0% | 4%-13% | 65.4% | ok |
| montant_credit | ≥ 3 M | 258 | 55 | 4 | 7.3% | 3%-17% | 72.5% | ok |
| duree_mois | 6-12 mois | 671 | 194 | 6 | 3.1% | 1%-7% | 81.5% | ok |
| duree_mois | 13-24 mois | 687 | 44 | 10 | 22.7% | 13%-37% | 51.5% | ok |
| duree_mois | 25-36 mois | 318 | 18 | 6 | 33.3% | 16%-56% | 23.6% | SIGNALÉE |
| duree_mois | 37-48 mois | 324 | 14 | 13 | 92.9% | 69%-99% | 11.1% | SIGNALÉE |
| anciennete_activite | < 2 ans | 365 | 66 | 5 | 7.6% | 3%-17% | 68.5% | ok |
| anciennete_activite | 2-5 ans | 851 | 116 | 17 | 14.7% | 9%-22% | 57.0% | ok |
| anciennete_activite | 5-10 ans | 633 | 75 | 8 | 10.7% | 6%-20% | 38.4% | ok |
| anciennete_activite | ≥ 10 ans | 151 | 13 | 5 | 38.5% | 18%-64% | 22.5% | SIGNALÉE |
| charge_mensuelle | < 0,05 | 65 | 1 | 1 | 100.0% | 21%-100% | 0.0% | non concluant |
| charge_mensuelle | 0,05-0,10 | 182 | 6 | 6 | 100.0% | 61%-100% | 0.0% | non concluant |
| charge_mensuelle | 0,10-0,20 | 414 | 15 | 14 | 93.3% | 70%-99% | 9.9% | SIGNALÉE |
| charge_mensuelle | ≥ 0,20 | 1339 | 248 | 14 | 5.6% | 3%-9% | 72.5% | ok |
