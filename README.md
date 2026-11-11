# Climate Automation

Intégration Home Assistant (installable via HACS) qui pilote des climatiseurs
répartis en **3 zones**, en fonction de la **production solaire**, de la
**couleur Tempo** (EDF/RTE), de plages horaires et du coucher du soleil, avec
une protection **hors-gel**.

Tous les réglages se font depuis l'interface de Home Assistant, sans
`input_*` ni YAML.

## Ce que fait l'intégration

Toutes les 5 minutes, et dès que la production solaire, la couleur Tempo ou
un réglage change, elle calcule l'état voulu de chaque climatiseur. Elle ne
lui envoie une commande que si quelque chose doit changer. Les règles s'appliquent dans cet ordre :

1. **Mode manuel** (par zone) : l'intégration ne touche plus du tout aux
   climatiseurs de la zone, hors-gel compris.
2. **Hors-gel** : si la température de la pièce passe sous le seuil, la clim
   est allumée avec une consigne d'au moins ce seuil (dans le mode de
   fonctionnement choisi, normalement « heat »). Ce plancher s'applique
   toujours, même si la zone ou la clim est désactivée, le mois inactif ou
   l'heure en dehors de la plage.
3. **Zone ou clim désactivée** : la clim est éteinte.
4. **Logique solaire uniquement** (option par zone) : mois, horaires et Tempo
   sont ignorés. La zone suit la production solaire 24 h/24 et s'éteint sous
   le seuil bas.
5. **Mois inactif** : la clim est éteinte.
6. **En dehors de la plage horaire** : la plage commence à l'heure de début
   (une heure différente les jours rouges) et se termine au coucher du soleil
   plus un décalage réglable. Juste avant le début et juste après la fin,
   l'intégration éteint la clim ; en pleine nuit, elle la laisse libre.
7. **Jour Tempo rouge, en début de matinée** : préchauffage en température éco.
8. **Production solaire** :
   - au-dessus du seuil haut : température **confort** ;
   - entre les deux seuils : température **éco** ;
   - sous le seuil bas : extinction les jours rouges, température éco les
     autres jours.

Plusieurs sécurités s'ajoutent à ces règles :
- un délai minimum entre deux allumages ou extinctions d'une même clim
  (anti-court-cycle, 5 minutes par défaut) ;
- une vérification que chaque commande a bien été appliquée, avec une
  nouvelle tentative sinon ;
- un temps de stabilisation de la production solaire, pour éviter les
  allers-retours autour des seuils.

## Prérequis

- Home Assistant **2024.4** ou plus récent.
- [HACS](https://hacs.xyz/) pour l'installation.
- Un capteur de **production solaire en kW**.
- Un capteur de **couleur Tempo** du jour (`bleu`, `blanc` ou `rouge`).
- Les climatiseurs (entités `climate.*`).
- Facultatif :
  - un capteur de température par zone, pour le hors-gel ; une zone sans
    capteur utilise celui de la première zone qui en a un ;
  - les entités `select.*` de flux d'air horizontal et vertical de chaque
    climatiseur.

## Installation

1. Dans HACS, ouvrir le menu **⋮** puis **Dépôts personnalisés**.
2. Ajouter `https://github.com/FigurinePanda43/ClimateAutomation` avec le type
   **Intégration**.
3. Rechercher **Climate Automation** dans HACS, le télécharger, puis
   redémarrer Home Assistant.
4. Aller dans **Paramètres → Appareils et services → Ajouter une
   intégration** et choisir **Climate Automation**.

## Configuration

L'assistant d'installation demande, dans l'ordre :

1. les capteurs de production solaire et de couleur Tempo ;
2. pour chacune des 3 zones : son nom, ses climatiseurs et son capteur de
   température. Un climatiseur ne doit appartenir qu'à une seule zone ;
3. les entités de flux d'air de chaque climatiseur (facultatif).

Tout reste modifiable ensuite avec le bouton **Configurer** de l'intégration :
capteurs, composition des zones (ajouter, retirer ou déplacer un
climatiseur, renommer une zone) et flux d'air. Les réglages en cours sont
conservés.

## Entités créées

L'intégration crée un **appareil principal** pour les réglages communs aux
3 zones :
- un interrupteur par mois (chauffage actif ou non) ;
- le mode de fonctionnement et le mode de ventilation ;
- les flux d'air horizontal et vertical, si des entités de flux sont
  associées ;
- le seuil hors-gel ;
- l'heure de début et l'heure de fin de matinée des jours rouges ;
- le délai anti-court-cycle.

Chaque **zone** a son propre appareil, rattaché à l'appareil principal, avec :
- les interrupteurs « Zone active », « Mode manuel » et « Forcer logique
  solaire uniquement » ;
- les températures confort et éco ;
- les seuils de production haut et bas ;
- l'heure de début des jours normaux et le décalage par rapport au coucher
  du soleil (négatif : avant, positif : après) ;
- pour chaque climatiseur, un interrupteur « Activer » et un capteur
  « État calculé » qui indique la décision en cours (confort, éco, off,
  hors-gel, préchauffe rouge, manuel…).

Toutes ces valeurs sont conservées au redémarrage de Home Assistant.

## Mises à jour

Chaque nouvelle version est publiée automatiquement comme
[release GitHub](https://github.com/FigurinePanda43/ClimateAutomation/releases),
et HACS la propose ensuite en mise à jour.

## Pour aller plus loin

[`DESIGN.md`](DESIGN.md) décrit le fonctionnement interne en détail : moteur
de décision, sécurités, structure du code et publication des releases.
