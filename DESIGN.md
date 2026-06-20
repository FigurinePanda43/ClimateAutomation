# Climate Automation — Intégration Home Assistant (HACS)

Réécriture, sous forme d'intégration personnalisée, de l'automatisation YAML
`Chauffage multi-zones programmé - Gestion Tempo et production solaire V7.2`
(conservée pour référence dans `original_automation`).

L'objectif est de **fiabiliser** la logique métier (planification robuste,
anti-court-cycle, convergence d'état, debounce solaire) tout en la rendant
**entièrement configurable par l'interface** Home Assistant, sans `input_*`.

---

## 1. Concepts

### 1.1 Zones (3, indépendantes)

L'installation est découpée en **3 zones de configuration**. Chaque zone :

- regroupe un sous-ensemble des **climatiseurs** (`climate.*`) ;
- possède ses **propres consignes** : températures confort/éco, seuils de
  production solaire, horaires, mode HVAC, mode de ventilation, flux d'air,
  hors-gel, mois actifs ;
- est activable/désactivable globalement.

**Règle importante : une climatisation n'appartient qu'à une seule zone**
(pas de clim partagée → pas d'arbitrage de conflit entre zones nécessaire).

Les 5 climatiseurs actuels servent de base :
`climate.clim_salon_local`, `climate.clim_cesar_local`,
`climate.clim_chambre_bas_2`, `climate.clim_amis_2`,
`climate.clim_chambre_principale`.

### 1.2 Capteurs partagés (globaux)

- **Production solaire** : `sensor.compteur_electricite_power_a` — production
  solaire **en kW** (valeur positive = production disponible).
- **Couleur Tempo (RTE)** : `sensor.tarif_tempo_couleur_aujourd_hui`
  (`bleu` / `blanc` / `rouge`).

### 1.3 Capteur de température par zone (hors-gel)

Chaque zone peut référencer un **capteur de température réel** de la pièce,
utilisé pour le hors-gel.

**Repli si une zone n'a pas de capteur** : on utilise le capteur de la
**première zone qui en possède un** (typiquement la zone 1). Donc si un seul
capteur est configuré, il pilote le hors-gel des 3 zones.

---

## 2. Logique de décision (moteur unifié)

Pour chaque **zone active**, et pour chaque **clim activée** (interrupteur par
clim sur `on`) de cette zone, on calcule un **état désiré** puis on **converge**
vers cet état. L'ordre de priorité des règles :

1. **Hors-gel (priorité absolue)** — si la température réelle de la zone
   (capteur, avec repli zone 1) `< seuil_hors_gel` (défaut **10 °C**), forcer le
   chauffage à la consigne hors-gel. S'applique **même** mois désactivé / hors
   plage horaire.
2. **Mois désactivé** → `off`.
3. **Hors plage horaire** (avant le début applicable / après
   `coucher_soleil − décalage`) → `off`.
4. **Jour Tempo rouge, fenêtre matinale** (`heure_start_rouge_tempo` →
   `heure_stop_rouge_matin`) → **préchauffe ÉCO forcée** (pas d'arbitrage
   solaire). En dehors de cette fenêtre rouge (après la pointe, jusqu'au
   coucher), on repasse en asservissement solaire.
5. **Asservissement solaire** (cas normal, dans la plage) selon les seuils
   **propres à la zone** :
   - `production > seuil_haute` → **CONFORT** (`temp_confort`)
   - `seuil_basse ≤ production ≤ seuil_haute` → **ÉCO** (`temp_eco`)
   - `production < seuil_basse` → `off`

La logique **Tempo** (préchauffe avant pointe + coupure pendant la pointe
matinale rouge) est **identique pour les 3 zones** (mais chaque zone applique
ses propres heures et sa propre température éco).

### 2.1 Convergence d'état

Un état désiré comporte : `hvac_mode`, `temperature`, `fan_mode`,
`flux_horizontal`, `flux_vertical`. On n'envoie une commande à une entité
**que si** la cible diffère de l'état courant **suivi en interne** par
l'intégration (et non relu juste après une écriture → corrige le bug de
lecture d'état asynchrone de l'ancienne version).

---

## 3. Sécurités

| Sécurité | Comportement |
|---|---|
| **Anti-court-cycle** | Délai minimum (défaut **5 min**, configurable) entre deux changements `ON↔OFF` d'une même clim. Un changement bloqué est ré-appliqué au cycle suivant une fois le délai écoulé. |
| **Hors-gel** | Maintien d'un plancher (défaut **10 °C**) basé sur un **capteur de température réel** (repli zone 1), prioritaire sur toutes les autres règles. |
| **Vérification de commande appliquée** | Après envoi d'une commande, re-vérification après un court délai ; en cas d'échec, nouvelle tentative + log d'avertissement (les clims ne sont pas toutes paramétrées de la même façon → certaines ignorent/retardent des ordres). |
| **Debounce solaire** | Les variations rapides du capteur de production sont temporisées : on attend une stabilisation avant de recalculer, pour éviter le flapping autour des seuils. |

---

## 4. Fiabilité — corrections par rapport au YAML

| Défaut d'origine | Correction |
|---|---|
| **A** — déclencheurs `now().strftime(...) == heure` qui peuvent manquer leur minute (redémarrage/lag) | Boucle de réévaluation périodique **toutes les 5 min** qui, entre l'heure de début et de fin, vérifie pour chaque clim : doit-elle être allumée ? l'est-elle ? à la bonne température ? avec les bons paramètres ? + planification native des bascules. |
| **D** — comparaison d'état relue juste après écriture | État désiré **suivi en mémoire** ; convergence sur l'état connu. |
| **Court-cycle** (absent à l'origine) | Verrou anti-court-cycle 5 min. |
| **Pas de hors-gel** | Hors-gel par capteur réel. |

> Note : **B** (`mode: single` + `solar_changed`) — non confirmé comme observé ;
> géré gratuitement par l'architecture (coordinator unique + debounce, pas de
> drop silencieux). **F** (duplication) — non prioritaire, mais résolu de fait
> par le moteur unifié (une seule fonction de décision).

---

## 5. Configuration (interface HA)

### 5.1 Config / Options flow (réglages structurels, peu fréquents)

- **Global** : entité capteur de production solaire, entité capteur Tempo.
- **Par zone** (×3) : nom, liste des `climate.*` rattachés, capteur de
  température de la zone, mapping `flux horizontal`/`flux vertical`
  (`select.*`) par clim, mois actifs.

### 5.2 Entités créées par l'intégration (réglages courants, ajustables en direct)

- **Global** : `number` délai anti-court-cycle.
- **Par zone** (×3) :
  - `switch` zone active
  - `number` : température confort, éco, seuil production haute, seuil
    production basse, seuil hors-gel
  - `select` : mode HVAC (`heat/cool/dry/fan_only/auto`), mode ventilation
    (`auto/low/medium/high/quiet`), flux horizontal, flux vertical
  - `time` : début rouge Tempo, début normal, fin matinée rouge, décalage
    coucher de soleil
- **Par clim** : `switch` d'activation. Activer → la clim converge
  immédiatement vers l'état voulu par sa zone ; désactiver → extinction
  immédiate.
- **Diagnostic** : `sensor` d'état par zone (mode courant calculé : confort /
  éco / off / hors-gel / préchauffe rouge).

---

## 6. Structure du dépôt

```
custom_components/climate_automation/
  __init__.py        # setup de l'entrée + coordinator + plateformes
  manifest.json
  const.py           # constantes, clés de config, valeurs par défaut
  config_flow.py     # config_flow + options_flow
  coordinator.py     # moteur : décision, planification, sécurités
  models.py          # dataclasses (config de zone, état désiré)
  entity.py          # base d'entité liée au coordinator
  number.py
  select.py
  switch.py
  time.py
  sensor.py          # capteur d'état/diagnostic par zone
hacs.json            # métadonnées HACS
```
