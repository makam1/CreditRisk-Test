# Plan de test : CreditRisk-Test

## 1\. Contexte et périmètre

Système testé : prototype d'estimation du risque de défaut de remboursement pour une institution de microfinance. Un agent de crédit envoie les informations d'un demandeur ; le système valide, prétraite, prédit une probabilité de défaut et la restitue via une API.

|Composant|Fichier|Dans le périmètre|
|-|-|-|
|Validation|`app/validation.py`|Oui|
|Prétraitement|`app/preprocessing.py`|Oui|
|Modèle ML|`models/` (pipeline scikit-learn sauvegardé)|Oui : fonctionnement et qualité statistique|
|Prédiction|`app/prediction.py`|Oui|
|API REST|`app/main.py`, `app/schemas.py`|Oui|
|Hors périmètre|Interface web, base de données, authentification, déploiement réel|Non|

**Données :** jeu **synthétique** généré par `scripts/generate\_data.py` (graine 42, 10 000 lignes). Il sert à tester le système et ne démontre pas la performance réelle d'un modèle de crédit.

**Outils :** pytest, pytest-cov, httpx/TestClient FastAPI, Hypothesis, Ruff, psutil, Locust (charge), GitHub Actions.

**Preuves conservées :** sorties pytest, rapport de couverture, rapports de non-régression et de performance, journaux CI, captures, registre des anomalies.

## 2\. Priorités

|Niveau|Signification|Conséquence d'une défaillance|
|-|-|-|
|P1 critique|Décision de crédit faussée, donnée invalide acceptée, fuite d'information|Bloque la qualification|
|P2 majeure|Service dégradé ou comportement non conforme au contrat|À corriger avant le pilote|
|P3 mineure|Confort, documentation, cas rare|Peut rester ouverte, documentée|

## 3\. Contrat de l'API

|Endpoint|Cas|Code HTTP|Contenu|
|-|-|-|-|
|GET /health|Service et modèle prêts|200|`{"status": "ok"}`|
|GET /health|Modèle non chargé|503|`{"status": "indisponible", "modele\_charge": false}`|
|GET /model-info|Normal|200|`version\_modele`, `seuil`, `variables`, `date\_entrainement`, `metriques\_reference`|
|POST /predict|Requête valide|200|`prediction` (0 ou 1), `probabilite\_defaut`, `seuil`, `version\_modele`, `avertissements` (liste)|
|POST /predict|Entrée invalide (type, intervalle, champ absent, champ en trop, non fini, JSON mal formé)|422|`erreur` + liste `details` (champ, message). Aucune prédiction.|
|POST /predict|Modèle non chargé|503|Message générique|
|POST /predict|Erreur interne|500|Message générique, sans trace, chemin ni nom de classe|
|Autre méthode ou route|GET /predict, route inconnue|405 / 404|Erreur standard|

**Règles de validation :** `age` entier de 18 à 100 ; montant\_credit numérique fini strictement positif ; revenu\_mensuel numérique fini entre 1 000 et 100 000 000 FCFA ; `duree\_mois` entier de 1 à 120 ; `anciennete\_activite` numérique fini supérieur ou égal à 0 ; les 5 champs sont obligatoires ; aucun champ supplémentaire ; **pas de conversion silencieuse** (la chaîne "250000" est rejetée, comme les booléens). Bornes de plausibilité : revenu de 1 000 à 100 000 000 FCFA par mois, montant au plus 10 000 000 000 FCFA; ancienneté ≤ âge (cohérence entre variables).

**Entrée inhabituelle mais valide** (hors de la plage d'entraînement : âge supérieur à 70, durée supérieure à 48 mois, etc.) : traitée (200) avec un **avertissement**, pas rejetée.

## 4\. Matrice de traçabilité

|ID|Exigence|Résultat attendu|Risque maîtrisé|Priorité|Cas de test|
|-|-|-|-|-|-|
|EX01|L'âge est dans l'intervalle autorisé (18 à 100)|Hors limites rejeté|Dossier d'un mineur ou aberrant évalué|P1|T01, T02|
|EX02|Revenu et montant sont numériques et strictement positifs|Entrée invalide : erreur contrôlée|Score calculé sur des données absurdes|P1|T03, T04, T05, T06|
|EX03|La durée est un entier entre 1 et 120|Durées invalides rejetées|Conversion silencieuse 12,5 vers 12|P1|T07, T08, T09, T10|
|EX04|La prédiction retourne une probabilité valide|0 à 1, finie, structure complète|Réponse inexploitable pour l'agent|P1|T11, T12|
|EX05|Le modèle est disponible, sinon signalé|503 contrôlé, pas de plantage|Panne silencieuse ou fausse prédiction|P1|T13, T14|
|EX06|Entrée incomplète : réponse d'erreur appropriée|422 qui nomme le champ|Prédiction sur dossier incomplet|P1|T15, T16, T17, T18|
|EX07|Une nouvelle version ne dégrade pas les critères critiques|Contrôle de non-régression exécuté, décision accepter, investiguer ou rejeter|Modèle dégradé mis en service|P1|T19, T20, T21|
|EX08|Les champs supplémentaires sont refusés|422|Injection de champs, contrat flou|P2|T22|
|EX09|Les valeurs extrêmes sont gérées|Bornes dépassées : 422 ; plausible mais inhabituel : 200 + avertissement|Débordement, score extrême non signalé|P2|T23, T24|
|EX10|Les valeurs non finies sont rejetées avant la prédiction|422, le modèle n'est pas appelé|NaN propagé dans le modèle|P1|T25|
|EX11|Une entrée hors domaine d'entraînement est signalée|200 + avertissement|Extrapolation silencieuse du modèle|P2|T26|
|EX12|Les erreurs internes ne révèlent aucune information technique ni donnée personnelle|500 générique, journaux sans valeurs de dossier|Fuite d'information|P1|T27, T28, T29, T30|
|EX13|Les prédictions sont reproductibles et cohérentes après rechargement|Écart inférieur ou égal à 1e-9|Modèle sauvegardé différent du modèle évalué|P1|T31, T32, T33|
|EX14|Le seuil de classification est explicite et configurable|Seuil exposé, valide, effectif|Seuil caché ou modifié sans trace|P2|T34, T35, T36|
|EX15|La latence respecte l'objectif|P95 de /predict inférieur ou égal à 200 ms en local, 0 erreur en charge progressive|Outil inutilisable en entretien client|P2|T37, T38|
|EX16|Le modèle atteint la qualité minimale sans fuite de données|Rappel du défaut supérieur ou égal à 0,85 (validation), cible hors variables d'entrée, scaler ajusté sur l'entraînement|Défauts non détectés, surévaluation|P1|T39, T40|
|EX17|Les endpoints annexes respectent leur contrat|/health, /model-info, 405, 404 conformes|Supervision impossible|P3|T41, T42|
|EX18|Les variables sont cohérentes entre elles (ancienneté ≤ âge) | Dossier incohérent rejeté (422) | Score calculé sur un profil impossible | P2 | T43 |
|EX19|Aucune entrée ne provoque d'erreur interne (500) | Réponse 200 ou 422, jamais 500 | Déni de service, fuite d'information | P1 | T44, T45 |
|EX20|Le modèle sauvegardé reproduit ses métriques enregistrées et respecte le rappel ≥ 0,85 (validation) | Recalcul strict (±1e-4) et rechargement identique | Artefact livré non conforme à l'exigence | P1 | T46, T47, T54 |
|EX21|Une nouvelle version n'est acceptée que sans régression au-delà de tolérances fixées à l'avance | Décision ACCEPTER / INVESTIGUER / REJETER | Dégradation silencieuse, déploiement d'un modèle moins bon | P1 | T48, T49, T50, T51, T52 |
|EX22|La référence est figée et vérifiable | Baseline non écrasable sans --force, empreintes concordantes | Comparaison faite contre une référence qui a bougé | P1 | T53 |
|EX23|Latence et débit tiennent les objectifs du pilote | P95 inférence ≤ 50 ms, P95 API ≤ 200 ms, ≥ 20 req/s à 10 utilisateurs, 0 erreur | Service inutilisable ou erreurs sous charge | P2 | T55, T56, T57 |
|EX24|La CI bloque toute régression avant fusion | Workflow rouge si Ruff, test, couverture < 85 % ou non-régression échouent | Code défectueux fusionné | P1 | T58, T59 |
*Justification des seuils (fixés avant toute mesure) :* le rappel de 0,85 est l'objectif pédagogique de l'énoncé, et non une garantie pour une décision de crédit réelle. Le P95 de 200 ms correspond à un outil utilisé en entretien, où un résultat sous la seconde reste fluide et où l'on garde de la marge pour la validation et le réseau.

## 5\. Cas de test

Préconditions communes : **P1** = API démarrée, modèle v1 chargé ; **P2** = modèle non chargé ; **P3** = référence de non-régression figée. Dossier de référence : `{age: 35, revenu\_mensuel: 250000, montant\_credit: 1000000, duree\_mois: 12, anciennete\_activite: 4}`.

|ID|Exigence|Pré.|Entrée|Résultat attendu|
|-|-|-|-|-|
|T01|EX01|P1|age = 17, 101, -1, 0|422, aucune prédiction|
|T02|EX01|P1|age = 18 et 100|200|
|T03|EX02|P1|revenu = "abc" et "250000" (chaîne), true|422|
|T04|EX02|P1|revenu = 0, -100|422|
|T05|EX02|P1|montant = 0, -1 000 000|422|
|T06|EX02|P1|montant = "1 000 000" (texte)|422|
|T07|EX03|P1|durée = 12.5|422|
|T08|EX03|P1|durée = 0, 121, -6|422|
|T09|EX03|P1|durée = 1 et 120|200|
|T10|EX03|P1|durée = "12" (chaîne)|422|
|T11|EX04|P1|dossier de référence|200, prediction dans {0, 1}, probabilité dans \[0, 1], version\_modele présent|
|T12|EX04|P1|200 dossiers valides générés (Hypothesis)|probabilité finie dans \[0, 1] pour chacun|
|T13|EX05|P2|POST /predict, GET /health, GET /model-info|503, message contrôlé|
|T14|EX05|P2|fichier modèle absent ou corrompu au démarrage|l'application démarre, état indisponible, pas de plantage|
|T15|EX06|P1|dossier privé d'un champ (un test par champ)|422 qui nomme le champ|
|T16|EX06|P1|corps `{}`|422|
|T17|EX06|P1|corps non JSON ou JSON tronqué|422, jamais 500|
|T18|EX06|P1|champ à null|422|
|T19|EX07|P3|métriques de la nouvelle version dans la tolérance|décision ACCEPTER, code de sortie 0|
|T20|EX07|P3|modèle volontairement dégradé|décision REJETER, code de sortie 1|
|T21|EX07|P3|rejeu de la suite fonctionnelle après modification|tous les tests passent|
|T22|EX08|P1|dossier de référence + champ `nom`|422|
|T23|EX09|P1|revenu = 1e308, montant = 1e20|422|
|T24|EX09|P1|montant = 5 000 000 000 (plausible, inhabituel)|200 + avertissement|
|T25|EX10|P1|NaN, Infinity, -Infinity dans revenu ou montant|422, modèle non appelé|
|T26|EX11|P1|age = 90, durée = 100|200 + avertissement « hors domaine »|
|T27|EX12|P1|la prédiction lève une exception (simulée)|500 générique, sans trace ni chemin|
|T28|EX12|P1|le prétraitement lève une erreur (simulée)|500 générique|
|T29|EX12|P1|modèle attendant un nombre de variables différent|erreur contrôlée, sans détail technique|
|T30|EX12|P1|requête valide, puis requête invalide|journaux sans valeur de revenu, montant ni âge|
|T31|EX13|P1|même dossier envoyé 2 fois|probabilités identiques|
|T32|EX13|P1|modèle sauvegardé puis rechargé, 1 000 dossiers|écart maximal inférieur ou égal à 1e-9|
|T33|EX13|P1|entraînement relancé avec la même graine|coefficients et métriques identiques|
|T34|EX14|P1|GET /model-info et POST /predict|seuil exposé et utilisé|
|T35|EX14|P1|seuil modifié par configuration|la classe peut changer, la probabilité reste identique|
|T36|EX14|P1|seuil = 0, 1, -0.2, NaN|rejeté au démarrage|
|T37|EX15|P1|500 requêtes valides en série|P95 inférieur ou égal à 200 ms|
|T38|EX15|P1|charge progressive 1, 5, 10, 20 utilisateurs|0 % d'erreur, latence documentée|
|T39|EX16|P3|évaluation sur la validation|rappel du défaut supérieur ou égal à 0,85|
|T40|EX16|P1|inspection des variables d'entrée et du scaler|`defaut` absent des variables, scaler ajusté sur l'entraînement seul|
|T41|EX17|P1|GET /health, GET /model-info|200 et contenu conforme|
|T42|EX17|P1|GET /predict, GET /inconnu|405, 404|
|T43|EX18|P1|age = 20, anciennete_activite = 30 | 422, champ anciennete_activite |
|T44|EX19|P1|300 corps JSON aléatoires (types, valeurs et structures arbitraires) | 200 ou 422, jamais 500 |
|T45|EX19|P1|entier de 400 chiffres ; JSON imbriqué sur 100 000 niveaux | 422 |
|T46|EX20|P1|rappel recalculé sur la validation avec le modèle sauvegardé | ≥ 0,85 et égal aux métriques enregistrées (±1e-4) |
|T47|EX20|P2|distance entre le seuil et le dossier de validation le plus proche | > 1e-6 (décision stable à l'arrondi) |
|T48|EX21|P1|candidats reconstruit à l'identique et régularisé | ACCEPTER |
|T49|EX21|P1|candidat entraîné sur données réduites | INVESTIGUER (rappel −0,033 ; 7,6 % de décisions modifiées) |
|T50|EX21|P1|candidat avec seuil par défaut 0,5 | REJETER (rappel 0,66) |
|T51|EX21|P1|candidat sans la variable dérivée ; candidat illisible | REJETER |
|T52|EX21|P2|bornes des tolérances (inclusives), pire niveau, gain suspect | niveaux attendus |
|T53|EX22|P1|baseline : refus d'écrasement, empreintes du jeu et du modèle, référence rejouée | conforme |
|T54|EX20|P2|sauvegarde puis rechargement du pipeline | probabilités strictement identiques |
|T55|EX23|P2|500 appels à `predire` | P95 ≤ 50 ms |
|T56|EX23|P2|100 appels HTTP en mémoire à /predict | P95 ≤ 200 ms |
|T57|EX23|P2|3 utilisateurs simultanés pendant 1 s ; paliers 1 à 50 utilisateurs (script) | 0 erreur, débit ≥ 20 req/s |
|T58|EX24|P1|pull request avec un test volontairement faux | workflow en échec (croix rouge) |
|T59|EX24|P1|pull request conforme | workflow vert |

## 6\. Critères d'acceptation et de rejet

**Acceptation pour une phase pilote** (toutes les conditions) :

* 100 % des tests P1 passent ; aucune anomalie critique ouverte ;
* rappel du défaut supérieur ou égal à 0,85 sur la validation, vérifié une fois sur le test ;
* contrôle de non-régression : décision ACCEPTER ;
* P95 de /predict inférieur ou égal à 200 ms et 0 erreur en charge légère ;
* workflow GitHub Actions réussi, échec volontaire détecté ;
* couverture supérieure ou égale à 85 % (garde-fou, pas une preuve de qualité).

**Rejet ou investigation :** un test P1 en échec, une anomalie critique ouverte, une dégradation hors tolérance, ou une trace technique exposée au client.

## 7\. Limites

Données synthétiques : la qualité statistique mesurée ne préjuge pas de la performance réelle. La validation technique ne remplace pas la validation métier, juridique et éthique d'un outil de décision de crédit.

